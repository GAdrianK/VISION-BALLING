#!/usr/bin/env python3
"""Update status for a beta analysis request.

Usage:
    python scripts/update_beta_request.py <request_id> <new_status>

Allowed statuses:
    NEW, CONTACTED, VIDEO_RECEIVED, PROCESSING, DELIVERED, FEEDBACK_RECEIVED, DECLINED
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add backend to sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.schemas.beta import ALLOWED_STATUSES  # noqa: E402
from app.services.beta_service import get_beta_service  # noqa: E402


def main() -> int:
    if len(sys.argv) < 3:
        print("Usage: python scripts/update_beta_request.py <request_id> <new_status>")
        print(f"Statuts autorisés: {', '.join(ALLOWED_STATUSES)}")
        return 1

    request_id = sys.argv[1].strip()
    new_status = sys.argv[2].strip().upper()

    if new_status not in ALLOWED_STATUSES:
        print(f"Erreur: Statut '{new_status}' non reconnu.")
        print(f"Statuts autorisés: {', '.join(ALLOWED_STATUSES)}")
        return 1

    service = get_beta_service()
    existing = service.get_request(request_id)
    if not existing:
        print(f"Erreur: Demande '{request_id}' introuvable.")
        return 1

    prev_status = existing.get("status")
    success = service.update_request_status(request_id, new_status)
    if success:
        print(f"Demande {request_id}: statut mis à jour ({prev_status} -> {new_status})")
        return 0
    else:
        print(f"Échec de la mise à jour pour la demande {request_id}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
