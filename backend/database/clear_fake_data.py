"""
clear_fake_data.py
==================
Purge complète de la collection Qdrant locale et de la base SQLite parent_store.
À exécuter avant chaque ingestion de vraies données pour garantir un index 100% propre.
"""

import os
import sys
import shutil
import sqlite3
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.core.config import settings


def clear_all_data(confirm: bool = False) -> bool:
    """
    Supprime toutes les données vectorielles (Qdrant local) et relationnelles (SQLite).

    Args:
        confirm: Si True, exécute sans demander confirmation interactive.

    Returns:
        True si la purge a été effectuée, False sinon.
    """
    qdrant_path = os.path.join(backend_dir, "data", "qdrant_local")
    sqlite_path = settings.get_sqlite_db_path()
    chunks_path = os.path.join(backend_dir, "data", "processed", "chunks.jsonl")

    print("==================================================")
    print("        PURGE COMPLÈTE DE L'INDEX RAG             ")
    print("==================================================")
    print(f"  Qdrant local  : {qdrant_path}")
    print(f"  SQLite DB     : {sqlite_path}")
    print(f"  Chunks JSONL  : {chunks_path}")
    print("==================================================")

    if not confirm:
        answer = input("Confirmer la suppression ? [oui/non] : ").strip().lower()
        if answer not in ("oui", "o", "yes", "y"):
            print("[ANNULÉ] Aucune donnée supprimée.")
            return False

    # 1. Supprimer le dossier Qdrant local
    if os.path.exists(qdrant_path):
        shutil.rmtree(qdrant_path)
        print(f"  [✓] Qdrant local supprimé : {qdrant_path}")
    else:
        print(f"  [INFO] Qdrant local déjà absent.")

    # 2. Supprimer la base SQLite
    if os.path.exists(sqlite_path):
        os.remove(sqlite_path)
        print(f"  [✓] SQLite supprimé : {sqlite_path}")
    else:
        print(f"  [INFO] SQLite déjà absent.")

    # 3. Supprimer le fichier de chunks JSONL processés
    if os.path.exists(chunks_path):
        os.remove(chunks_path)
        print(f"  [✓] Chunks JSONL supprimé : {chunks_path}")
    else:
        print(f"  [INFO] Chunks JSONL déjà absent.")

    print("==================================================")
    print("  PURGE TERMINÉE. Index réinitialisé à zéro.      ")
    print("==================================================")
    return True


if __name__ == "__main__":
    clear_all_data(confirm=False)
