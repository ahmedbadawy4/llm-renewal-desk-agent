from __future__ import annotations

from typing import List


class HybridSearcher:
    def __init__(self) -> None:
        self.enabled = True

    def search(self, vendor_id: str, query: str, source: str) -> List[dict[str, str]]:
        # Placeholder: returns stub result illustrating interface.
        return [
            {
                "doc_id": f"{source}/{vendor_id}",
                "score": 0.42,
                "snippet": "Sample snippet",
            }
        ]
