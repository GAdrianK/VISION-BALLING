#!/usr/bin/env python3
"""Cleanup expired beta requests according to configured data retention policy.

Usage:
    python scripts/cleanup_expired_beta_data.py [--days N]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add backend to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings  # noqa: E402
from app.services.beta_service import get_beta_service  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Purge expired beta pilot requests.")
    parser.add_argument(
        "--days",
        type=int,
        default=settings.BETA_REQUEST_RETENTION_DAYS,
        help=f"Retention period in days (default: {settings.BETA_REQUEST_RETENTION_DAYS} from config)",
    )
    args = parser.parse_args()

    service = get_beta_service()
    deleted = service.cleanup_expired_requests(retention_days=args.days)
    print(f"Purge terminée : {deleted} demande(s) expirée(s) supprimée(s) (rétention: {args.days} jours).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
