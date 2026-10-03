from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.core.config import BASE_DIR
from app.schemas.beta import (
    ALLOWED_STATUSES,
    BetaAnalysisRequestCreate,
    BetaAnalysisRequestResponse,
)

logger = logging.getLogger(__name__)

DEFAULT_BETA_DB_PATH = BASE_DIR / "data" / "beta_requests.db"


def redact_url_for_logging(url: str) -> str:
    """Redacts query parameters and fragments from URLs to avoid logging sensitive access tokens."""
    if not url:
        return ""
    base = url.split("?")[0].split("#")[0]
    return f"{base}?..." if "?" in url else base


class InMemoryRateLimiter:
    """Sliding-window in-memory rate limiter per IP address."""

    def __init__(self, max_requests: int = 5, window_seconds: int = 600) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._history: Dict[str, List[float]] = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        timestamps = self._history.setdefault(client_ip, [])
        # Prune old records
        self._history[client_ip] = [t for t in timestamps if t > cutoff]
        if len(self._history[client_ip]) >= self.max_requests:
            return False
        self._history[client_ip].append(now)
        return True

    def reset(self) -> None:
        self._history.clear()


class BetaService:
    def __init__(self, db_path: Path | str = DEFAULT_BETA_DB_PATH) -> None:
        self.db_path = Path(db_path)
        self.rate_limiter = InMemoryRateLimiter(max_requests=5, window_seconds=600)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS beta_analysis_requests (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    name TEXT NOT NULL,
                    club TEXT NOT NULL,
                    role TEXT NOT NULL,
                    email TEXT NOT NULL,
                    phone TEXT,
                    team_category TEXT NOT NULL,
                    competition_level TEXT NOT NULL,
                    opponent TEXT,
                    video_type TEXT NOT NULL,
                    video_url TEXT NOT NULL,
                    analysis_objectives TEXT NOT NULL,
                    message TEXT,
                    video_authorization_confirmed INTEGER NOT NULL,
                    temporary_storage_consent INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'NEW'
                );
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_beta_created_at ON beta_analysis_requests(created_at);"
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_beta_status ON beta_analysis_requests(status);"
            )
            conn.commit()

    def create_request(
        self, req: BetaAnalysisRequestCreate, client_ip: str = "unknown"
    ) -> BetaAnalysisRequestResponse:
        request_id = f"beta_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        objectives_json = json.dumps(req.analysis_objectives, ensure_ascii=False)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO beta_analysis_requests (
                    id, created_at, name, club, role, email, phone,
                    team_category, competition_level, opponent,
                    video_type, video_url, analysis_objectives, message,
                    video_authorization_confirmed, temporary_storage_consent, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (
                    request_id,
                    now_iso,
                    req.name,
                    req.club,
                    req.role,
                    req.email,
                    req.phone,
                    req.team_category,
                    req.competition_level,
                    req.opponent,
                    req.video_type,
                    req.video_url,
                    objectives_json,
                    req.message,
                    1 if req.video_authorization_confirmed else 0,
                    1 if req.temporary_storage_consent else 0,
                    "NEW",
                ),
            )
            conn.commit()

        redacted_video = redact_url_for_logging(req.video_url)
        logger.info(
            "Beta analysis request created: id=%s, club=%s, email=%s, video=%s, ip=%s",
            request_id,
            req.club,
            req.email,
            redacted_video,
            client_ip,
        )

        return BetaAnalysisRequestResponse(
            id=request_id,
            created_at=now_iso,
            status="NEW",
            message="Votre demande BETA a bien été enregistrée.",
        )

    def list_requests(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, created_at, name, club, role, email, phone,
                       team_category, competition_level, opponent,
                       video_type, video_url, analysis_objectives, message,
                       video_authorization_confirmed, temporary_storage_consent, status
                FROM beta_analysis_requests
                ORDER BY created_at DESC;
                """
            )
            rows = cursor.fetchall()
            results = []
            for r in rows:
                item = dict(r)
                try:
                    item["analysis_objectives"] = json.loads(item["analysis_objectives"])
                except Exception:
                    item["analysis_objectives"] = []
                results.append(item)
            return results

    def get_request(self, request_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT id, created_at, name, club, role, email, phone,
                       team_category, competition_level, opponent,
                       video_type, video_url, analysis_objectives, message,
                       video_authorization_confirmed, temporary_storage_consent, status
                FROM beta_analysis_requests
                WHERE id = ?;
                """,
                (request_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            item = dict(row)
            try:
                item["analysis_objectives"] = json.loads(item["analysis_objectives"])
            except Exception:
                item["analysis_objectives"] = []
            return item

    def update_request_status(self, request_id: str, new_status: str) -> bool:
        if new_status not in ALLOWED_STATUSES:
            raise ValueError(
                f"Statut '{new_status}' non valide. Valeurs autorisées: {', '.join(ALLOWED_STATUSES)}"
            )

        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE beta_analysis_requests SET status = ? WHERE id = ?;",
                (new_status, request_id),
            )
            conn.commit()
            updated = cursor.rowcount > 0

        if updated:
            logger.info("Beta request %s updated to status %s", request_id, new_status)
        return updated


_global_beta_service: Optional[BetaService] = None


def get_beta_service() -> BetaService:
    global _global_beta_service
    if _global_beta_service is None:
        _global_beta_service = BetaService()
    return _global_beta_service
