#!/usr/bin/env python3
"""Placeholder migration runner."""
from __future__ import annotations

import sys


def main() -> None:
    print("Apply database migrations here (Alembic or SQL files).")
    print("For now, ensure pgvector extension + tables exist via manual SQL.")
    sys.exit(0)


if __name__ == "__main__":
    main()
