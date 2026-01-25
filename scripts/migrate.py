#!/usr/bin/env python3
"""Database migration runner using Alembic."""
from __future__ import annotations

import sys

from alembic import command
from alembic.config import Config


def main() -> None:
    alembic_cfg = Config("alembic.ini")
    command.upgrade(alembic_cfg, "head")
    print("Database migrations applied successfully.")


if __name__ == "__main__":
    main()
