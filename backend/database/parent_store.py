import sqlite3
import os
import logging
from typing import Optional, Tuple
from app.core.config import settings

logger = logging.getLogger(__name__)

class ParentStoreManager:
    """
    Gestionnaire pour le stockage des documents parents complets avec SQLite.
    Gère la persistance locale des textes complets indexés par parent_id.
    """
    def __init__(self):
        self.db_path = settings.get_sqlite_db_path()
        # S'assurer que le dossier parent existe
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
            
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """
        Crée la table des documents parents si elle n'existe pas.
        """
        logger.info(f"Initialisation de la base SQLite à : {self.db_path}")
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS parent_documents (
                    parent_id TEXT PRIMARY KEY,
                    source_name TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_parent(self, parent_id: str, source_name: str, content: str) -> bool:
        """
        Enregistre un document parent dans SQLite. 
        Utilise INSERT OR REPLACE pour mettre à jour si le document change.
        """
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO parent_documents (parent_id, source_name, content) VALUES (?, ?, ?)",
                    (parent_id, source_name, content)
                )
                conn.commit()
            logger.info(f"Document parent '{source_name}' enregistré avec ID: {parent_id}")
            return True
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde du document parent {source_name} : {e}")
            return False

    def get_parent(self, parent_id: str) -> Optional[Tuple[str, str]]:
        """
        Récupère le document parent sous forme de tuple (source_name, content) par son ID.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT source_name, content FROM parent_documents WHERE parent_id = ?",
                    (parent_id,)
                )
                row = cursor.fetchone()
                if row:
                    return row["source_name"], row["content"]
            return None
        except Exception as e:
            logger.error(f"Erreur lors de la récupération du document parent {parent_id} : {e}")
            return None

    def exists(self, parent_id: str) -> bool:
        """
        Vérifie si un document parent existe déjà dans la base.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT 1 FROM parent_documents WHERE parent_id = ?",
                    (parent_id,)
                )
                return cursor.fetchone() is not None
        except Exception as e:
            logger.error(f"Erreur lors de la vérification d'existence du parent {parent_id} : {e}")
            return False
