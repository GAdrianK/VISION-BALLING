#!/usr/bin/env python3
"""List beta analysis requests in a clean, human-readable terminal table.

Usage:
    python scripts/list_beta_requests.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to sys.path so we can import app modules
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.services.beta_service import get_beta_service  # noqa: E402


def main() -> int:
    service = get_beta_service()
    requests = service.list_requests()

    if not requests:
        print("Aucune demande BETA enregistrée.")
        return 0

    header = f"{'ID':<18} | {'DATE':<10} | {'CLUB':<25} | {'CONTACT':<30} | {'VIDEO TYPE':<18} | {'STATUS':<15}"
    sep = "-" * len(header)
    print(sep)
    print(header)
    print(sep)

    for req in requests:
        req_id = req.get("id", "")
        created_at = req.get("created_at", "")[:10]
        club = (req.get("club", "") or "")[:25]
        email = (req.get("email", "") or "")[:30]
        video_type = (req.get("video_type", "") or "")[:18]
        status = req.get("status", "")

        print(
            f"{req_id:<18} | {created_at:<10} | {club:<25} | {email:<30} | {video_type:<18} | {status:<15}"
        )

    print(sep)
    print(f"Total: {len(requests)} demande(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
