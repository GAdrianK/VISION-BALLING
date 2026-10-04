from __future__ import annotations

import hashlib
import json
import secrets
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, settings
from app.core.crypto import decrypt_payload, encrypt_payload
from app.main import app
from app.schemas.publication import ArtifactInfoItem, PublicationManifest
from app.services.evidence_resolver import EvidenceResolver
from app.services.grounded_rag_service import GroundedTacticalRAGService
from app.services.publication_service import PublicationService
from app.services.r2_storage import R2StorageService
from app.video_analysis.schemas import JobStatus


@pytest.fixture
def clean_db(tmp_path: Path):
    db_file = tmp_path / "test_pub.db"
    return f"sqlite:///{db_file}"


@pytest.fixture
def mock_r2(tmp_path: Path):
    storage_dir = tmp_path / "mock_r2"
    return R2StorageService(local_storage_dir=storage_dir)


@pytest.fixture
def pub_service(clean_db: str, mock_r2: R2StorageService):
    return PublicationService(db_target=clean_db, r2_storage=mock_r2)


def test_production_security_enforces_analysis_token():
    """Validates that production mode crashes at startup if REQUIRE_ANALYSIS_TOKEN is False."""
    with pytest.raises(ValueError, match="REQUIRE_ANALYSIS_TOKEN must be True in production mode"):
        Settings(
            APP_ENV="production",
            REQUIRE_ANALYSIS_TOKEN=False,
            ALLOWED_ORIGINS="https://vision-balling.fr",
            PUBLIC_UPLOAD_ENABLED=False,
            DATABASE_URL="postgresql://user:pass@localhost:5432/vballing",
        )


def test_crypto_aes_gcm_encryption_roundtrip():
    """Validates AES-256-GCM authenticated encryption and tamper detection."""
    key = secrets.token_hex(32)
    payload = {"analysis_id": "test_match_01", "coach": "Coach A", "url": "https://test.fr"}

    c_b64, n_b64, t_b64 = encrypt_payload(payload, key)
    decrypted = decrypt_payload(c_b64, n_b64, t_b64, key)
    assert decrypted == payload

    # Tamper detection
    tampered_c = "A" + c_b64[1:]
    with pytest.raises(Exception):
        decrypt_payload(tampered_c, n_b64, t_b64, key)


def test_r2_sigv4_presigned_url_excludes_range_from_signed_headers():
    """Ensures range header is not in SignedHeaders to enable HTTP 206 Range requests."""
    test_settings = Settings(
        R2_ACCOUNT_ID="test_account",
        R2_BUCKET_NAME="test_bucket",
        R2_ACCESS_KEY_ID="test_access_key",
        R2_SECRET_ACCESS_KEY="test_secret_key",
    )
    r2 = R2StorageService(cfg=test_settings)
    url = r2.generate_presigned_url("GET", "analyses/match1/annotated.mp4", expires_in_seconds=300)

    assert "X-Amz-Algorithm=AWS4-HMAC-SHA256" in url
    assert "X-Amz-SignedHeaders=host" in url
    assert "range" not in url.lower().split("x-amz-signedheaders=")[1].split("&")[0]


def test_publication_fencing_token_and_staging_lifecycle(pub_service: PublicationService):
    """Tests staging, fencing lease protection against zombie workers, and promotion."""
    manifest = PublicationManifest(
        schema_version="1.0",
        analysis_id="match_fence_01",
        version_id="v1",
        match_id="Nantes vs Rennes",
        created_at_utc="2026-10-04T20:00:00Z",
        video_duration_seconds=45.2,
        fps=25.0,
        frame_count=1130,
        artifacts={
            "annotated.mp4": ArtifactInfoItem(
                name="annotated.mp4",
                sha256="a" * 64,
                size_bytes=1024,
                media_type="video/mp4",
            ),
            "tactical_events.json": ArtifactInfoItem(
                name="tactical_events.json",
                sha256="b" * 64,
                size_bytes=512,
                media_type="application/json",
            ),
        },
    )

    # 1. Initiate attempt 1
    init1 = pub_service.initiate_publication("match_fence_01", manifest)
    assert init1.fencing_token == 1
    assert "annotated.mp4" in init1.upload_targets

    # 2. Initiate attempt 2 (e.g. retry from another worker)
    init2 = pub_service.initiate_publication("match_fence_01", manifest)
    assert init2.fencing_token == 2

    # 3. Attempt 1 tries to finalize -> MUST FAIL with lease conflict!
    with pytest.raises(ValueError, match="Publication lease conflict"):
        pub_service.finalize_publication(
            analysis_id="match_fence_01",
            version_id="v1",
            finalization_id=init1.finalization_id,
            fencing_token=init1.fencing_token,
        )

    # 4. Attempt 2 finalizes -> SUCCESS
    fin = pub_service.finalize_publication(
        analysis_id="match_fence_01",
        version_id="v1",
        finalization_id=init2.finalization_id,
        fencing_token=init2.fencing_token,
        recipient_email="coach@test.fr",
        notify=False,
    )
    assert fin.status == "PUBLISHED"
    assert fin.capability_token
    assert f"https://vision-balling.fr/match/match_fence_01#access={fin.capability_token}" == fin.access_url


def test_operator_token_constant_time_authentication(pub_service: PublicationService):
    """Verifies that operator endpoints enforce HMAC constant-time authentication."""
    raw_op_token = "secret_operator_token_9876543210"
    op_hash = hashlib.sha256(raw_op_token.encode("utf-8")).hexdigest()

    test_settings = Settings(
        APP_ENV="development",
        OPERATOR_TOKEN_HASH=op_hash,
    )

    from app.api.auth_dependencies import verify_operator_token
    from fastapi import HTTPException

    # 1. No token -> 401
    with pytest.raises(HTTPException) as exc:
        verify_operator_token(authorization=None)
    assert exc.value.status_code == 401

    # 2. Wrong token -> 403
    with pytest.raises(HTTPException) as exc:
        verify_operator_token(authorization="Bearer wrong_token")
    assert exc.value.status_code == 403


def test_watertight_coach_and_operator_isolation(pub_service: PublicationService, tmp_path: Path):
    """Verifies that coach credentials are strictly rejected on operator routes and vice-versa."""
    raw_op_token = "op_token_12345678901234567890"
    op_hash = hashlib.sha256(raw_op_token.encode("utf-8")).hexdigest()

    from app.api.admin_publications import get_publication_service as get_admin_pub
    from app.api.video_analysis import get_publication_service as get_analysis_pub
    from app.core.config import settings as global_settings

    global_settings.OPERATOR_TOKEN_HASH = op_hash

    app.dependency_overrides[get_admin_pub] = lambda: pub_service
    app.dependency_overrides[get_analysis_pub] = lambda: pub_service

    try:
        manifest = PublicationManifest(
            schema_version="1.0",
            analysis_id="match_isolate_01",
            version_id="v1",
            match_id="Match A",
            created_at_utc="2026-10-04T20:00:00Z",
            video_duration_seconds=30.0,
            fps=25.0,
            frame_count=750,
            artifacts={
                "annotated.mp4": ArtifactInfoItem(
                    name="annotated.mp4",
                    sha256="c" * 64,
                    size_bytes=2048,
                    media_type="video/mp4",
                ),
            },
        )
        init = pub_service.initiate_publication("match_isolate_01", manifest)
        fin = pub_service.finalize_publication(
            analysis_id="match_isolate_01",
            version_id="v1",
            finalization_id=init.finalization_id,
            fencing_token=init.fencing_token,
        )
        coach_token = fin.capability_token

        with TestClient(app) as client:
            # 1. Coach token tried on operator endpoint -> 403
            resp = client.post(
                "/api/internal/publications/initiate",
                headers={"Authorization": f"Bearer {coach_token}"},
                json={"analysis_id": "hack", "manifest": manifest.model_dump()},
            )
            assert resp.status_code == 403

            # 2. Operator token used to exchange coach capability -> 403
            resp2 = client.post(
                "/api/video-analysis/match_isolate_01/access/exchange",
                json={"capability_token": raw_op_token},
            )
            assert resp2.status_code == 403

            # 3. Legitimate coach exchange -> 200 with Host cookie
            resp3 = client.post(
                "/api/video-analysis/match_isolate_01/access/exchange",
                json={"capability_token": coach_token},
            )
            assert resp3.status_code == 200
            assert "csrf_token" in resp3.json()
            assert "__Host-vb_session" in resp3.cookies or "vb_session" in resp3.cookies

            # 4. Valid session accesses video stream url
            resp4 = client.get(
                "/api/video-analysis/match_isolate_01/video-stream-url",
                cookies=resp3.cookies,
            )
            assert resp4.status_code == 200
            assert "stream_url" in resp4.json()

            # 5. Same session tried on a different match -> 403
            resp5 = client.get(
                "/api/video-analysis/different_match_99/video-stream-url",
                cookies=resp3.cookies,
            )
            assert resp5.status_code in (401, 403, 404)
    finally:
        app.dependency_overrides.clear()


def test_revocation_invalidates_grants_and_sessions(pub_service: PublicationService):
    """Verifies that revoking a publication immediately cuts off active sessions."""
    manifest = PublicationManifest(
        schema_version="1.0",
        analysis_id="match_revoke_01",
        version_id="v1",
        match_id="Match Revoke",
        created_at_utc="2026-10-04T20:00:00Z",
        video_duration_seconds=30.0,
        fps=25.0,
        frame_count=750,
        artifacts={},
    )
    init = pub_service.initiate_publication("match_revoke_01", manifest)
    fin = pub_service.finalize_publication(
        analysis_id="match_revoke_01",
        version_id="v1",
        finalization_id=init.finalization_id,
        fencing_token=init.fencing_token,
    )

    # Coach authenticates
    sess = pub_service.authenticate_capability("match_revoke_01", fin.capability_token)
    assert sess is not None

    # Active verification works
    v = pub_service.verify_session("match_revoke_01", sess["session_secret"])
    assert v is not None

    # Operator revokes publication
    pub_service.revoke_publication("match_revoke_01", reason="Match rights disputed")

    # Immediate rejection
    v_after = pub_service.verify_session("match_revoke_01", sess["session_secret"])
    assert v_after is None

    # New capability exchange rejected
    sess_after = pub_service.authenticate_capability("match_revoke_01", fin.capability_token)
    assert sess_after is None


def test_grounded_assistant_strict_abstention_and_structured_blocks(tmp_path: Path):
    """Verifies that GroundedTacticalRAGService produces 4 structured blocks and abstains on unsupported queries."""
    from app.schemas.grounded_rag import QueryScope

    rag_service = GroundedTacticalRAGService(
        evidence_dir=Path("docs/experiments/exp25_outputs"),
        openai_api_key="mock-key",
    )

    # 1. Unsupported query (score/xG) -> Fast abstention
    ans_unsupported = rag_service.query("Quel est le score final et le xG du match ?", "SNMOT-068")
    assert ans_unsupported.is_abstention is True
    assert ans_unsupported.query_scope == QueryScope.UNSUPPORTED
    assert "ne permettent pas d'établir cette information" in ans_unsupported.answer

    # 2. Match fact query -> Structured response
    ans_fact = rag_service.query(
        "Quelles sont les phases de pressing observées dans ce match ?",
        "SNMOT-068",
        force_offline_fallback=True,
    )
    assert ans_fact.is_abstention is False
    assert len(ans_fact.observations_du_match) > 0 or len(ans_fact.interpretations_tactiques) > 0
    assert isinstance(ans_fact.connaissances_generales, list)
    assert isinstance(ans_fact.limites, list)

