from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import APIKeyHeader, HTTPBearer
from pydantic import BaseModel

from ..storage.postgres import get_connection
from .config import Settings, get_settings

logger = logging.getLogger(__name__)

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


class User(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    roles: list[str]


def hash_api_key(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()


def generate_api_key() -> str:
    return f"rd_{secrets.token_urlsafe(32)}"


def verify_api_key(api_key: str, settings: Settings) -> Optional[User]:
    if not api_key:
        return None

    key_hash = hash_api_key(api_key)

    try:
        with get_connection(settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ak.id, ak.user_id, ak.name, u.email, u.full_name
                    FROM api_keys ak
                    JOIN users u ON ak.user_id = u.id
                    WHERE ak.key_hash = %s AND ak.is_active = true AND u.is_active = true
                    """,
                    (key_hash,),
                )
                row = cur.fetchone()
                if not row:
                    return None

                cur.execute(
                    """
                    UPDATE api_keys SET last_used_at = NOW() WHERE id = %s
                    """,
                    (row[0],),
                )

                cur.execute(
                    """
                    SELECT r.name
                    FROM user_roles ur
                    JOIN roles r ON ur.role_id = r.id
                    WHERE ur.user_id = %s
                    """,
                    (row[1],),
                )
                roles = [r[0] for r in cur.fetchall()]

                return User(
                    id=row[1],
                    email=row[3],
                    full_name=row[4],
                    roles=roles,
                )
    except Exception as e:
        logger.warning(f"API key verification failed: {e}")
        return None


def get_current_user(
    api_key: Optional[str] = Depends(api_key_header),
    settings: Settings = Depends(get_settings),
) -> User:
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    user = verify_api_key(api_key, settings)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return user


def require_role(required_role: str):
    def role_checker(user: User = Depends(get_current_user)) -> User:
        if required_role not in user.roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{required_role}' required",
            )
        return user

    return role_checker


def check_vendor_access(user: User, vendor_id: str, settings: Settings) -> bool:
    if "admin" in user.roles:
        return True

    try:
        with get_connection(settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1 FROM vendor_access WHERE user_id = %s AND vendor_id = %s
                    """,
                    (user.id, vendor_id),
                )
                return cur.fetchone() is not None
    except Exception:
        return False


def log_audit(
    user_id: Optional[int],
    api_key_id: Optional[int],
    action: str,
    resource_type: Optional[str],
    resource_id: Optional[str],
    ip_address: Optional[str],
    settings: Settings,
) -> None:
    try:
        with get_connection(settings) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs 
                    (user_id, api_key_id, action, resource_type, resource_id, ip_address)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (user_id, api_key_id, action, resource_type, resource_id, ip_address),
                )
    except Exception as e:
        logger.warning(f"Audit logging failed: {e}")
