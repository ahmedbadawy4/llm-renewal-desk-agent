from __future__ import annotations

from typing import List


class VectorStore:
    def __init__(self) -> None:
        self.enabled = False

    def upsert(self, vectors: List[tuple[str, list[float]]]) -> None:
        raise NotImplementedError("Connect to pgvector or a managed vector DB")

    def query(self, embedding: list[float], k: int = 5) -> list[dict[str, float]]:
        raise NotImplementedError
