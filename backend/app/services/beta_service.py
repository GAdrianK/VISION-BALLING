from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import BASE_DIR, settings
from app.schemas.beta import (
    ALLOWED_STATUSES,
    BetaAnalysisRequestCreate,
    BetaAnalysisRequestResponse,
)
from app.services.mail_service import MailService, get_mail_service

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
    """Unified service for beta analysis requests supporting SQLite and PostgreSQL persistent storage."""

    def __init__(
        self,
        db_target: Optional[Path | str] = None,
        db_path: Optional[Path | str] = None,
        mail_service: Optional[MailService] = None,
    ) -> None:
        self.rate_limiter = InMemoryRateLimiter(max_requests=5, window_seconds=600)
        target = db_target if db_target is not None else db_path
        self.db_url = self._resolve_db_url(target)
        self.engine: Engine = self._create_engine(self.db_url)
        self._init_db()
        self.mail_service = mail_service if mail_service is not None else get_mail_service()

    @staticmethod
    def _resolve_db_url(target: Optional[Path | str]) -> str:
        if target:
            target_str = str(target).strip()
            if target_str.startswith("postgres://"):
                target_str = "postgresql://" + target_str[len("postgres://"):]
            if target_str.startswith(("sqlite:", "postgresql:")):
                return target_str
            # Assume file path for SQLite
            path = Path(target_str).resolve()
            path.parent.mkdir(parents=True, exist_ok=True)
            return f"sqlite:///{path}"

        if settings.effective_database_url:
            return settings.effective_database_url

        if settings.APP_ENV == "production":
            raise RuntimeError(
                "Production startup error: DATABASE_URL is mandatory in production mode. "
                "SQLite fallback is forbidden in production."
            )

        DEFAULT_BETA_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{DEFAULT_BETA_DB_PATH.resolve()}"

    @staticmethod
    def _create_engine(db_url: str) -> Engine:
        if db_url.startswith("sqlite"):
            # Ensure SQLite allows multithreaded fastapi requests
            return create_engine(db_url, connect_args={"check_same_thread": False})
        return create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=10)

    def _init_db(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS beta_analysis_requests (
                        id VARCHAR(64) PRIMARY KEY,
                        created_at VARCHAR(64) NOT NULL,
                        name VARCHAR(150) NOT NULL,
                        club VARCHAR(150) NOT NULL,
                        role VARCHAR(100) NOT NULL,
                        email VARCHAR(254) NOT NULL,
                        phone VARCHAR(50),
                        team_category VARCHAR(100) NOT NULL,
                        competition_level VARCHAR(100) NOT NULL,
                        opponent VARCHAR(150),
                        video_type VARCHAR(100) NOT NULL,
                        video_url VARCHAR(2048) NOT NULL,
                        analysis_objectives TEXT NOT NULL,
                        message TEXT,
                        video_authorization_confirmed INTEGER NOT NULL,
                        temporary_storage_consent INTEGER NOT NULL,
                        status VARCHAR(50) NOT NULL DEFAULT 'NEW'
                    );
                    """
                )
            )
            # Safe index creation
            try:
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS idx_beta_created_at ON beta_analysis_requests(created_at);")
                )
                conn.execute(
                    text("CREATE INDEX IF NOT EXISTS idx_beta_status ON beta_analysis_requests(status);")
                )
            except Exception as e:
                logger.debug("Indices creation note: %s", str(e))

    def create_request(
        self, req: BetaAnalysisRequestCreate, client_ip: str = "unknown"
    ) -> BetaAnalysisRequestResponse:
        request_id = f"beta_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()
        objectives_json = json.dumps(req.analysis_objectives, ensure_ascii=False)

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO beta_analysis_requests (
                        id, created_at, name, club, role, email, phone,
                        team_category, competition_level, opponent,
                        video_type, video_url, analysis_objectives, message,
                        video_authorization_confirmed, temporary_storage_consent, status
                    ) VALUES (
                        :id, :created_at, :name, :club, :role, :email, :phone,
                        :team_category, :competition_level, :opponent,
                        :video_type, :video_url, :analysis_objectives, :message,
                        :video_authorization_confirmed, :temporary_storage_consent, :status
                    );
                    """
                ),
                {
                    "id": request_id,
                    "created_at": now_iso,
                    "name": req.name,
                    "club": req.club,
                    "role": req.role,
                    "email": req.email,
                    "phone": req.phone,
                    "team_category": req.team_category,
                    "competition_level": req.competition_level,
                    "opponent": req.opponent,
                    "video_type": req.video_type,
                    "video_url": req.video_url,
                    "analysis_objectives": objectives_json,
                    "message": req.message,
                    "video_authorization_confirmed": 1 if req.video_authorization_confirmed else 0,
                    "temporary_storage_consent": 1 if req.temporary_storage_consent else 0,
                    "status": "NEW",
                },
            )

        redacted_video = redact_url_for_logging(req.video_url)
        logger.info(
            "Beta analysis request created: id=%s, club=%s, email=%s, video=%s, ip=%s",
            request_id,
            req.club,
            req.email,
            redacted_video,
            client_ip,
        )

        # Non-blocking notification delivery: email issues must NEVER fail request creation
        try:
            if self.mail_service:
                self.mail_service.send_beta_request_notification(
                    req=req,
                    request_id=request_id,
                    created_at_iso=now_iso,
                )
        except Exception as e:
            logger.warning(
                "Non-blocking notification delivery failed for beta request %s: %s: %s",
                request_id,
                type(e).__name__,
                str(e),
            )

        return BetaAnalysisRequestResponse(
            id=request_id,
            created_at=now_iso,
            status="NEW",
            message="Votre demande BETA a bien été enregistrée.",
        )

    def list_requests(self) -> List[Dict[str, Any]]:
        with self.engine.connect() as conn:
            cursor = conn.execute(
                text(
                    """
                    SELECT id, created_at, name, club, role, email, phone,
                           team_category, competition_level, opponent,
                           video_type, video_url, analysis_objectives, message,
                           video_authorization_confirmed, temporary_storage_consent, status
                    FROM beta_analysis_requests
                    ORDER BY created_at DESC;
                    """
                )
            )
            rows = cursor.mappings().all()
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
        with self.engine.connect() as conn:
            cursor = conn.execute(
                text(
                    """
                    SELECT id, created_at, name, club, role, email, phone,
                           team_category, competition_level, opponent,
                           video_type, video_url, analysis_objectives, message,
                           video_authorization_confirmed, temporary_storage_consent, status
                    FROM beta_analysis_requests
                    WHERE id = :id;
                    """
                ),
                {"id": request_id},
            )
            row = cursor.mappings().first()
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

        with self.engine.begin() as conn:
            cursor = conn.execute(
                text("UPDATE beta_analysis_requests SET status = :status WHERE id = :id;"),
                {"status": new_status, "id": request_id},
            )
            updated = cursor.rowcount > 0

        if updated:
            logger.info("Beta request %s updated to status %s", request_id, new_status)
        return updated

    def cleanup_expired_requests(self, retention_days: Optional[int] = None) -> int:
        """Purges beta requests older than the configured retention period."""
        days = retention_days if retention_days is not None else settings.BETA_REQUEST_RETENTION_DAYS
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

        with self.engine.begin() as conn:
            cursor = conn.execute(
                text("DELETE FROM beta_analysis_requests WHERE created_at < :cutoff;"),
                {"cutoff": cutoff},
            )
            deleted_count = cursor.rowcount

        logger.info("Retention cleanup: deleted %d expired beta requests (cutoff=%s)", deleted_count, cutoff)
        return deleted_count


_global_beta_service: Optional[BetaService] = None


def get_beta_service() -> BetaService:
    global _global_beta_service
    if _global_beta_service is None:
        _global_beta_service = BetaService()
    return _global_beta_service
