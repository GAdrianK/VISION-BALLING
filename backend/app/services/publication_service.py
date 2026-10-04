from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import BASE_DIR, settings
from app.core.crypto import encrypt_payload, decrypt_payload
from app.schemas.publication import (
    ALLOWED_ARTIFACT_NAMES,
    ArtifactInfoItem,
    PublicationManifest,
    PublishFinalizeResponse,
    PublishInitiateResponse,
)
from app.services.mail_service import MailService, get_mail_service
from app.services.r2_storage import R2StorageService, get_r2_storage

logger = logging.getLogger(__name__)

DEFAULT_PUBLICATION_DB_PATH = BASE_DIR / "data" / "publications.db"


class PublicationService:
    """Manages cloud publication staging, promotion, grants, sessions, and delivery outbox."""

    def __init__(
        self,
        db_target: Optional[Path | str] = None,
        r2_storage: Optional[R2StorageService] = None,
        mail_service: Optional[MailService] = None,
    ) -> None:
        self.db_url = self._resolve_db_url(db_target)
        self.engine: Engine = self._create_engine(self.db_url)
        self.r2 = r2_storage or get_r2_storage()
        self.mail_service = mail_service or get_mail_service()
        self._init_db()

    @staticmethod
    def _resolve_db_url(target: Optional[Path | str]) -> str:
        if target:
            target_str = str(target).strip()
            if target_str.startswith("postgres://"):
                target_str = "postgresql://" + target_str[len("postgres://"):]
            if target_str.startswith(("sqlite:", "postgresql:")):
                return target_str
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

        DEFAULT_PUBLICATION_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{DEFAULT_PUBLICATION_DB_PATH.resolve()}"

    @staticmethod
    def _create_engine(db_url: str) -> Engine:
        if db_url.startswith("sqlite"):
            return create_engine(db_url, connect_args={"check_same_thread": False})
        return create_engine(db_url, pool_pre_ping=True, pool_size=5, max_overflow=10)

    def _init_db(self) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS analysis_publications (
                        id VARCHAR(64) PRIMARY KEY,
                        analysis_id VARCHAR(64) NOT NULL UNIQUE,
                        version_id VARCHAR(32) NOT NULL DEFAULT 'v1',
                        request_id VARCHAR(64),
                        finalization_id VARCHAR(64) NOT NULL,
                        fencing_token INTEGER NOT NULL DEFAULT 1,
                        status VARCHAR(32) NOT NULL DEFAULT 'STAGED',
                        manifest_json TEXT NOT NULL,
                        created_at VARCHAR(64) NOT NULL,
                        published_at VARCHAR(64),
                        revoked_at VARCHAR(64)
                    );
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS analysis_artifacts (
                        id VARCHAR(64) PRIMARY KEY,
                        publication_id VARCHAR(64) NOT NULL,
                        artifact_type VARCHAR(64) NOT NULL,
                        s3_key VARCHAR(512) NOT NULL,
                        sha256 VARCHAR(64) NOT NULL,
                        size_bytes BIGINT NOT NULL,
                        media_type VARCHAR(64) NOT NULL,
                        created_at VARCHAR(64) NOT NULL
                    );
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS analysis_access_grants (
                        id VARCHAR(64) PRIMARY KEY,
                        analysis_id VARCHAR(64) NOT NULL,
                        grant_token_hash VARCHAR(64) NOT NULL,
                        salt VARCHAR(64) NOT NULL,
                        expires_at VARCHAR(64) NOT NULL,
                        revoked_at VARCHAR(64),
                        created_at VARCHAR(64) NOT NULL
                    );
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS analysis_sessions (
                        id VARCHAR(64) PRIMARY KEY,
                        session_token_hash VARCHAR(64) NOT NULL UNIQUE,
                        analysis_id VARCHAR(64) NOT NULL,
                        grant_id VARCHAR(64) NOT NULL,
                        csrf_token_hash VARCHAR(64) NOT NULL,
                        expires_at VARCHAR(64) NOT NULL,
                        revoked_at VARCHAR(64),
                        created_at VARCHAR(64) NOT NULL,
                        last_seen_at VARCHAR(64) NOT NULL
                    );
                    """
                )
            )
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS delivery_outbox (
                        id VARCHAR(64) PRIMARY KEY,
                        analysis_id VARCHAR(64) NOT NULL,
                        recipient_email VARCHAR(254) NOT NULL,
                        encrypted_payload TEXT NOT NULL,
                        payload_nonce VARCHAR(64) NOT NULL,
                        payload_tag VARCHAR(64) NOT NULL,
                        status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
                        attempts INTEGER NOT NULL DEFAULT 0,
                        error_message TEXT,
                        created_at VARCHAR(64) NOT NULL,
                        dispatched_at VARCHAR(64)
                    );
                    """
                )
            )
            # Safe indices
            try:
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pub_analysis_id ON analysis_publications(analysis_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_artifacts_pub_id ON analysis_artifacts(publication_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_grants_analysis_id ON analysis_access_grants(analysis_id);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_sessions_hash ON analysis_sessions(session_token_hash);"))
                conn.execute(text("CREATE INDEX IF NOT EXISTS idx_outbox_status ON delivery_outbox(status);"))
            except Exception as e:
                logger.debug("Publication DB index note: %s", str(e))

    def initiate_publication(
        self,
        analysis_id: str,
        manifest: PublicationManifest,
        request_id: Optional[str] = None,
        version_id: str = "v1",
    ) -> PublishInitiateResponse:
        """Stages a new publication attempt with an incremented fencing token."""
        now_iso = datetime.now(timezone.utc).isoformat()
        finalization_id = f"fin_{uuid.uuid4().hex[:12]}"

        # Validate artifact names against allowlist
        for name in manifest.artifacts.keys():
            if name not in ALLOWED_ARTIFACT_NAMES:
                raise ValueError(f"Artifact '{name}' is not in the allowed publication artifact list.")

        with self.engine.begin() as conn:
            # Check existing publication
            row = conn.execute(
                text("SELECT id, fencing_token FROM analysis_publications WHERE analysis_id = :aid"),
                {"aid": analysis_id},
            ).fetchone()

            if row:
                pub_id = row[0]
                next_fencing_token = row[1] + 1
                conn.execute(
                    text(
                        """
                        UPDATE analysis_publications
                        SET version_id = :version_id,
                            request_id = :request_id,
                            finalization_id = :finalization_id,
                            fencing_token = :fencing_token,
                            status = 'STAGED',
                            manifest_json = :manifest_json,
                            created_at = :now_iso
                        WHERE id = :id
                        """
                    ),
                    {
                        "id": pub_id,
                        "version_id": version_id,
                        "request_id": request_id,
                        "finalization_id": finalization_id,
                        "fencing_token": next_fencing_token,
                        "manifest_json": manifest.model_dump_json(),
                        "now_iso": now_iso,
                    },
                )
            else:
                pub_id = f"pub_{uuid.uuid4().hex[:12]}"
                next_fencing_token = 1
                conn.execute(
                    text(
                        """
                        INSERT INTO analysis_publications (
                            id, analysis_id, version_id, request_id,
                            finalization_id, fencing_token, status,
                            manifest_json, created_at
                        ) VALUES (
                            :id, :analysis_id, :version_id, :request_id,
                            :finalization_id, :fencing_token, 'STAGED',
                            :manifest_json, :now_iso
                        )
                        """
                    ),
                    {
                        "id": pub_id,
                        "analysis_id": analysis_id,
                        "version_id": version_id,
                        "request_id": request_id,
                        "finalization_id": finalization_id,
                        "fencing_token": next_fencing_token,
                        "manifest_json": manifest.model_dump_json(),
                        "now_iso": now_iso,
                    },
                )

        # Generate target keys and upload URLs for each artifact
        upload_targets: Dict[str, str] = {}
        for name, artifact in manifest.artifacts.items():
            s3_key = f"analyses/{analysis_id}/versions/{version_id}/attempts/{finalization_id}/{name}"
            artifact.s3_key = s3_key
            upload_url = self.r2.generate_presigned_url(
                "PUT", s3_key, expires_in_seconds=900, content_type=artifact.media_type
            )
            upload_targets[name] = upload_url

        return PublishInitiateResponse(
            analysis_id=analysis_id,
            version_id=version_id,
            finalization_id=finalization_id,
            fencing_token=next_fencing_token,
            upload_targets=upload_targets,
        )

    def finalize_publication(
        self,
        analysis_id: str,
        version_id: str,
        finalization_id: str,
        fencing_token: int,
        recipient_email: Optional[str] = None,
        coach_name: Optional[str] = None,
        match_name: Optional[str] = None,
        notify: bool = False,
    ) -> PublishFinalizeResponse:
        """Promotes staged artifacts to active publication and generates capability token."""
        now = datetime.now(timezone.utc)
        now_iso = now.isoformat()

        with self.engine.begin() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT id, finalization_id, fencing_token, manifest_json
                    FROM analysis_publications
                    WHERE analysis_id = :aid
                    """
                ),
                {"aid": analysis_id},
            ).fetchone()

            if not row:
                raise ValueError(f"No publication found for analysis '{analysis_id}'.")

            pub_id, stored_fin_id, stored_fencing, manifest_json = row

            # Fencing check: reject zombie workers / stale attempts
            if stored_fin_id != finalization_id or stored_fencing != fencing_token:
                raise ValueError(
                    f"Publication lease conflict: active finalization_id is '{stored_fin_id}' "
                    f"(token {stored_fencing}), but request submitted '{finalization_id}' (token {fencing_token})."
                )

            manifest_data = json.loads(manifest_json)
            manifest = PublicationManifest.model_validate(manifest_data)

            # Update publication status to PUBLISHED
            conn.execute(
                text(
                    """
                    UPDATE analysis_publications
                    SET status = 'PUBLISHED', published_at = :now_iso
                    WHERE id = :id
                    """
                ),
                {"id": pub_id, "now_iso": now_iso},
            )

            # Clear old promoted artifacts for this publication (if re-publishing)
            conn.execute(
                text("DELETE FROM analysis_artifacts WHERE publication_id = :pub_id"),
                {"pub_id": pub_id},
            )

            # Insert artifacts
            for name, art in manifest.artifacts.items():
                art_id = f"art_{uuid.uuid4().hex[:12]}"
                s3_key = art.s3_key or f"analyses/{analysis_id}/versions/{version_id}/attempts/{finalization_id}/{name}"
                conn.execute(
                    text(
                        """
                        INSERT INTO analysis_artifacts (
                            id, publication_id, artifact_type, s3_key, sha256, size_bytes, media_type, created_at
                        ) VALUES (
                            :id, :pub_id, :atype, :s3_key, :sha256, :size_bytes, :media_type, :created_at
                        )
                        """
                    ),
                    {
                        "id": art_id,
                        "pub_id": pub_id,
                        "atype": name,
                        "s3_key": s3_key,
                        "sha256": art.sha256,
                        "size_bytes": art.size_bytes,
                        "media_type": art.media_type,
                        "created_at": now_iso,
                    },
                )

            # Generate new capability grant
            capability_token = secrets.token_urlsafe(32)
            salt = secrets.token_hex(16)
            token_salted = f"{salt}:{capability_token}"
            grant_hash = hashlib.sha256(token_salted.encode("utf-8")).hexdigest()
            grant_id = f"grant_{uuid.uuid4().hex[:12]}"
            retention_days = settings.BETA_REQUEST_RETENTION_DAYS
            expires_at = (now + timedelta(days=retention_days)).isoformat()

            conn.execute(
                text(
                    """
                    INSERT INTO analysis_access_grants (
                        id, analysis_id, grant_token_hash, salt, expires_at, created_at
                    ) VALUES (
                        :id, :aid, :ghash, :salt, :expires_at, :now_iso
                    )
                    """
                ),
                {
                    "id": grant_id,
                    "aid": analysis_id,
                    "ghash": grant_hash,
                    "salt": salt,
                    "expires_at": expires_at,
                    "now_iso": now_iso,
                },
            )

        access_url = f"https://vision-balling.fr/match/{analysis_id}#access={capability_token}"

        notification_queued = False
        if notify and recipient_email:
            self._enqueue_delivery_notification(
                analysis_id=analysis_id,
                recipient_email=recipient_email,
                coach_name=coach_name or "Entraîneur",
                match_name=match_name or analysis_id,
                access_url=access_url,
            )
            notification_queued = True

        return PublishFinalizeResponse(
            analysis_id=analysis_id,
            version_id=version_id,
            status="PUBLISHED",
            published_at=now_iso,
            capability_token=capability_token,
            access_url=access_url,
            notification_queued=notification_queued,
        )

    def _enqueue_delivery_notification(
        self,
        analysis_id: str,
        recipient_email: str,
        coach_name: str,
        match_name: str,
        access_url: str,
    ) -> None:
        """Stores encrypted delivery payload in outbox and attempts immediate dispatch."""
        key = settings.DELIVERY_OUTBOX_KEY or settings.SESSION_SECRET_KEY or "fallback-outbox-key"
        payload = {
            "analysis_id": analysis_id,
            "recipient_email": recipient_email,
            "coach_name": coach_name,
            "match_name": match_name,
            "access_url": access_url,
        }
        ciphertext, nonce, tag = encrypt_payload(payload, key)
        outbox_id = f"out_{uuid.uuid4().hex[:12]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO delivery_outbox (
                        id, analysis_id, recipient_email, encrypted_payload, payload_nonce, payload_tag,
                        status, attempts, created_at
                    ) VALUES (
                        :id, :aid, :email, :c, :n, :t, 'PENDING', 0, :now_iso
                    )
                    """
                ),
                {
                    "id": outbox_id,
                    "aid": analysis_id,
                    "email": recipient_email,
                    "c": ciphertext,
                    "n": nonce,
                    "t": tag,
                    "now_iso": now_iso,
                },
            )

        # Attempt immediate dispatch if SMTP is configured
        if self.mail_service and self.mail_service.is_configured:
            try:
                sent = self.mail_service.send_analysis_ready_notification(
                    recipient_email=recipient_email,
                    coach_name=coach_name,
                    match_name=match_name,
                    access_url=access_url,
                )
                if sent:
                    # Specs: purge row upon successful delivery to protect privacy
                    with self.engine.begin() as conn:
                        conn.execute(
                            text("DELETE FROM delivery_outbox WHERE id = :id"),
                            {"id": outbox_id},
                        )
            except Exception as exc:
                logger.warning("Immediate outbox dispatch failed: %s", exc)
                with self.engine.begin() as conn:
                    conn.execute(
                        text(
                            """
                            UPDATE delivery_outbox
                            SET attempts = attempts + 1, error_message = :err
                            WHERE id = :id
                            """
                        ),
                        {"id": outbox_id, "err": str(exc)},
                    )

    def authenticate_capability(self, analysis_id: str, capability_token: str) -> Optional[Dict[str, Any]]:
        """Verifies candidate capability token against active grants for analysis_id."""
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            # Check if publication is published and not revoked
            pub_row = conn.execute(
                text(
                    "SELECT status FROM analysis_publications WHERE analysis_id = :aid"
                ),
                {"aid": analysis_id},
            ).fetchone()

            if pub_row and pub_row[0] != "PUBLISHED":
                return None

            grants = conn.execute(
                text(
                    """
                    SELECT id, grant_token_hash, salt, expires_at
                    FROM analysis_access_grants
                    WHERE analysis_id = :aid
                      AND revoked_at IS NULL
                      AND expires_at > :now_iso
                    """
                ),
                {"aid": analysis_id, "now_iso": now_iso},
            ).fetchall()

        matched_grant_id: Optional[str] = None
        for grant_id, stored_hash, salt, _ in grants:
            candidate_raw = f"{salt}:{capability_token}"
            candidate_hash = hashlib.sha256(candidate_raw.encode("utf-8")).hexdigest()
            if hmac.compare_digest(candidate_hash, stored_hash):
                matched_grant_id = grant_id
                break

        if not matched_grant_id:
            return None

        # Create session
        session_secret = secrets.token_urlsafe(32)
        csrf_token = secrets.token_hex(24)

        session_hash = hashlib.sha256(session_secret.encode("utf-8")).hexdigest()
        csrf_hash = hashlib.sha256(csrf_token.encode("utf-8")).hexdigest()

        session_id = f"sess_{uuid.uuid4().hex[:12]}"
        max_age = settings.SESSION_MAX_AGE_SECONDS
        expires_dt = datetime.now(timezone.utc) + timedelta(seconds=max_age)
        expires_iso = expires_dt.isoformat()

        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO analysis_sessions (
                        id, session_token_hash, analysis_id, grant_id, csrf_token_hash,
                        expires_at, created_at, last_seen_at
                    ) VALUES (
                        :id, :shash, :aid, :gid, :chash, :exp, :now, :now
                    )
                    """
                ),
                {
                    "id": session_id,
                    "shash": session_hash,
                    "aid": analysis_id,
                    "gid": matched_grant_id,
                    "chash": csrf_hash,
                    "exp": expires_iso,
                    "now": now_iso,
                },
            )

        return {
            "session_secret": session_secret,
            "csrf_token": csrf_token,
            "max_age": max_age,
            "expires_at_iso": expires_iso,
        }

    def verify_session(self, analysis_id: str, session_token: str) -> Optional[Dict[str, Any]]:
        """Verifies session token is valid, active, and strictly bound to analysis_id."""
        if not session_token:
            return None

        session_hash = hashlib.sha256(session_token.encode("utf-8")).hexdigest()
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT s.id, s.analysis_id, s.csrf_token_hash, s.expires_at, p.status
                    FROM analysis_sessions s
                    JOIN analysis_publications p ON s.analysis_id = p.analysis_id
                    WHERE s.session_token_hash = :shash
                      AND s.analysis_id = :aid
                      AND s.revoked_at IS NULL
                      AND s.expires_at > :now_iso
                      AND p.status = 'PUBLISHED'
                    """
                ),
                {"shash": session_hash, "aid": analysis_id, "now_iso": now_iso},
            ).fetchone()

        if not row:
            return None

        # Update last seen
        with self.engine.begin() as conn:
            conn.execute(
                text("UPDATE analysis_sessions SET last_seen_at = :now WHERE id = :id"),
                {"now": now_iso, "id": row[0]},
            )

        return {
            "session_id": row[0],
            "analysis_id": row[1],
            "csrf_token_hash": row[2],
            "expires_at": row[3],
        }

    def verify_csrf(self, session: Dict[str, Any], csrf_token: Optional[str]) -> bool:
        """Verifies CSRF token against session record."""
        if not csrf_token or "csrf_token_hash" not in session:
            return False
        candidate = hashlib.sha256(csrf_token.encode("utf-8")).hexdigest()
        return hmac.compare_digest(candidate, session["csrf_token_hash"])

    def get_publication(self, analysis_id: str) -> Optional[Dict[str, Any]]:
        """Fetches active publication record with its artifacts."""
        with self.engine.connect() as conn:
            pub_row = conn.execute(
                text(
                    """
                    SELECT id, analysis_id, version_id, request_id, status, manifest_json, published_at
                    FROM analysis_publications
                    WHERE analysis_id = :aid
                    """
                ),
                {"aid": analysis_id},
            ).fetchone()

            if not pub_row:
                return None

            artifacts_rows = conn.execute(
                text(
                    """
                    SELECT artifact_type, s3_key, sha256, size_bytes, media_type
                    FROM analysis_artifacts
                    WHERE publication_id = :pid
                    """
                ),
                {"pid": pub_row[0]},
            ).fetchall()

        artifacts = {
            row[0]: {
                "name": row[0],
                "s3_key": row[1],
                "sha256": row[2],
                "size_bytes": row[3],
                "media_type": row[4],
            }
            for row in artifacts_rows
        }

        return {
            "id": pub_row[0],
            "analysis_id": pub_row[1],
            "version_id": pub_row[2],
            "request_id": pub_row[3],
            "status": pub_row[4],
            "manifest": json.loads(pub_row[5]),
            "published_at": pub_row[6],
            "artifacts": artifacts,
        }

    def revoke_publication(self, analysis_id: str, reason: str = "Operator revocation") -> bool:
        """Revokes publication, access grants, and sessions."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.engine.begin() as conn:
            conn.execute(
                text(
                    """
                    UPDATE analysis_publications
                    SET status = 'REVOKED', revoked_at = :now
                    WHERE analysis_id = :aid
                    """
                ),
                {"now": now_iso, "aid": analysis_id},
            )
            conn.execute(
                text(
                    """
                    UPDATE analysis_access_grants
                    SET revoked_at = :now
                    WHERE analysis_id = :aid
                    """
                ),
                {"now": now_iso, "aid": analysis_id},
            )
            conn.execute(
                text(
                    """
                    UPDATE analysis_sessions
                    SET revoked_at = :now
                    WHERE analysis_id = :aid
                    """
                ),
                {"now": now_iso, "aid": analysis_id},
            )
        return True


_global_publication_service: Optional[PublicationService] = None


def get_publication_service() -> PublicationService:
    global _global_publication_service
    if _global_publication_service is None:
        _global_publication_service = PublicationService()
    return _global_publication_service
