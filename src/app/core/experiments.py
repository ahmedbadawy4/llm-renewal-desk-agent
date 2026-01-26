from __future__ import annotations

import hashlib
import logging
import random
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..storage.postgres import get_connection
from .config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass
class ExperimentVariant:
    id: int
    name: str
    config: Dict[str, Any]
    traffic_percentage: float
    is_control: bool


@dataclass
class Experiment:
    id: int
    name: str
    status: str
    variants: List[ExperimentVariant]


class ExperimentTracker:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._cache: Dict[str, Experiment] = {}

    def get_active_experiment(self, experiment_name: str) -> Optional[Experiment]:
        if experiment_name in self._cache:
            exp = self._cache[experiment_name]
            if exp.status == "active":
                return exp
            else:
                del self._cache[experiment_name]

        try:
            with get_connection(self.settings) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT id, name, status
                        FROM experiments
                        WHERE name = %s AND status = 'active'
                        """,
                        (experiment_name,),
                    )
                    row = cur.fetchone()
                    if not row:
                        return None

                    exp_id = row[0]

                    cur.execute(
                        """
                        SELECT id, name, config, traffic_percentage, is_control
                        FROM experiment_variants
                        WHERE experiment_id = %s
                        ORDER BY is_control DESC, id
                        """,
                        (exp_id,),
                    )

                    variants = [
                        ExperimentVariant(
                            id=r[0],
                            name=r[1],
                            config=r[2],
                            traffic_percentage=r[3],
                            is_control=r[4],
                        )
                        for r in cur.fetchall()
                    ]

                    experiment = Experiment(id=exp_id, name=row[1], status=row[2], variants=variants)
                    self._cache[experiment_name] = experiment
                    return experiment
        except Exception as e:
            logger.warning(f"Failed to load experiment {experiment_name}: {e}")
            return None

    def assign_variant(
        self,
        experiment: Experiment,
        request_id: str,
        vendor_id: Optional[str] = None,
    ) -> Optional[ExperimentVariant]:
        if not experiment.variants:
            return None

        assignment_hash = self._hash_assignment(experiment.name, request_id, vendor_id)
        random.seed(assignment_hash)
        rand_val = random.random() * 100

        cumulative = 0.0
        for variant in experiment.variants:
            cumulative += variant.traffic_percentage
            if rand_val <= cumulative:
                self._record_assignment(experiment.id, variant.id, request_id, vendor_id)
                return variant

        return experiment.variants[0]

    def _hash_assignment(self, experiment_name: str, request_id: str, vendor_id: Optional[str]) -> int:
        key = f"{experiment_name}:{request_id}:{vendor_id or ''}"
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def _record_assignment(
        self,
        experiment_id: int,
        variant_id: int,
        request_id: str,
        vendor_id: Optional[str],
    ) -> None:
        try:
            with get_connection(self.settings) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO experiment_assignments 
                        (experiment_id, variant_id, request_id, vendor_id)
                        VALUES (%s, %s, %s, %s)
                        ON CONFLICT DO NOTHING
                        """,
                        (experiment_id, variant_id, request_id, vendor_id),
                    )
        except Exception as e:
            logger.warning(f"Failed to record assignment: {e}")

    def record_metric(
        self,
        experiment_id: int,
        variant_id: int,
        request_id: str,
        metric_name: str,
        metric_value: float,
    ) -> None:
        try:
            with get_connection(self.settings) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO experiment_metrics
                        (experiment_id, variant_id, request_id, metric_name, metric_value)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (experiment_id, variant_id, request_id, metric_name, metric_value),
                    )
        except Exception as e:
            logger.warning(f"Failed to record metric: {e}")

    def get_variant_metrics(
        self,
        experiment_id: int,
        variant_id: int,
        metric_name: str,
    ) -> Dict[str, Any]:
        try:
            with get_connection(self.settings) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT 
                            COUNT(*) as count,
                            AVG(metric_value) as mean,
                            STDDEV(metric_value) as stddev,
                            MIN(metric_value) as min_val,
                            MAX(metric_value) as max_val
                        FROM experiment_metrics
                        WHERE experiment_id = %s AND variant_id = %s AND metric_name = %s
                        """,
                        (experiment_id, variant_id, metric_name),
                    )
                    row = cur.fetchone()
                    if row and row[0]:
                        return {
                            "count": row[0],
                            "mean": float(row[1]) if row[1] else 0.0,
                            "stddev": float(row[2]) if row[2] else 0.0,
                            "min": float(row[3]) if row[3] else 0.0,
                            "max": float(row[4]) if row[4] else 0.0,
                        }
        except Exception as e:
            logger.warning(f"Failed to get variant metrics: {e}")

        return {"count": 0, "mean": 0.0, "stddev": 0.0, "min": 0.0, "max": 0.0}

    def test_significance(
        self,
        experiment_id: int,
        control_variant_id: int,
        treatment_variant_id: int,
        metric_name: str,
        alpha: float = 0.05,
    ) -> Dict[str, Any]:
        control_metrics = self.get_variant_metrics(experiment_id, control_variant_id, metric_name)
        treatment_metrics = self.get_variant_metrics(experiment_id, treatment_variant_id, metric_name)

        if control_metrics["count"] < 30 or treatment_metrics["count"] < 30:
            return {
                "significant": False,
                "reason": "insufficient_sample_size",
                "control_count": control_metrics["count"],
                "treatment_count": treatment_metrics["count"],
            }

        control_mean = control_metrics["mean"]
        treatment_mean = treatment_metrics["mean"]
        control_std = control_metrics["stddev"]
        treatment_std = treatment_metrics["stddev"]

        pooled_std = (
            ((control_metrics["count"] - 1) * control_std**2 + (treatment_metrics["count"] - 1) * treatment_std**2)
            / (control_metrics["count"] + treatment_metrics["count"] - 2)
        ) ** 0.5

        if pooled_std == 0:
            return {"significant": False, "reason": "zero_variance"}

        se = pooled_std * (1 / control_metrics["count"] + 1 / treatment_metrics["count"]) ** 0.5
        t_stat = (treatment_mean - control_mean) / se if se > 0 else 0

        from scipy import stats  # type: ignore[import-untyped]

        df = control_metrics["count"] + treatment_metrics["count"] - 2
        p_value = 2 * (1 - stats.t.cdf(abs(t_stat), df))

        significant = p_value < alpha
        improvement_pct = ((treatment_mean - control_mean) / control_mean * 100) if control_mean > 0 else 0.0

        return {
            "significant": significant,
            "p_value": p_value,
            "alpha": alpha,
            "t_statistic": t_stat,
            "control_mean": control_mean,
            "treatment_mean": treatment_mean,
            "improvement_pct": improvement_pct,
            "control_count": control_metrics["count"],
            "treatment_count": treatment_metrics["count"],
        }


_global_tracker: Optional[ExperimentTracker] = None


def get_experiment_tracker(settings: Settings | None = None) -> ExperimentTracker:
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = ExperimentTracker(settings)
    return _global_tracker
