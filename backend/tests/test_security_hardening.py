import io
import pytest
from pathlib import Path
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.main import app
from app.api.video_analysis import get_video_analysis_service
from app.video_analysis.schemas import AnalysisCreated, AnalysisJob, JobStatus
from app.video_analysis.service import VideoAnalysisService
from app.video_analysis.detectors import ObjectDetector, RawDetection
from app.video_analysis.validation import VideoValidationError, validate_video_magic_bytes


class DummyDetector(ObjectDetector):
    def load(self) -> None:
        pass

    def detect(self, frame, **kwargs):
        return []

    def metadata(self):
        return {"detector": "dummy", "model_id": "dummy-v1"}


def test_production_fails_closed_on_wildcard_cors():
    with pytest.raises(ValidationError) as exc:
        Settings(APP_ENV="production", ALLOWED_ORIGINS="*")
    assert "ALLOWED_ORIGINS cannot be '*'" in str(exc.value)

    with pytest.raises(ValidationError) as exc:
        Settings(APP_ENV="production", ALLOWED_ORIGINS="")
    assert "ALLOWED_ORIGINS" in str(exc.value)


def test_diagnostics_gated_in_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    with TestClient(app) as client:
        resp = client.get("/api/video-analysis/diagnostics/backend")
        assert resp.status_code == 404
        assert "désactivés" in resp.json()["detail"] or "disabled" in resp.json()["detail"].lower()


def test_security_headers_present_in_responses():
    with TestClient(app) as client:
        resp = client.get("/api/video-analysis/SNMOT-068/summary")
        assert resp.headers.get("x-content-type-options") == "nosniff"
        assert resp.headers.get("x-frame-options") == "DENY"
        assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_demo_analysis_publicly_accessible_without_token():
    with TestClient(app) as client:
        resp = client.get("/api/video-analysis/SNMOT-068/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert "TEAM_0" in data or "SNMOT-068" in str(data)


def test_real_upload_requires_capability_token(tmp_path: Path):
    test_settings = Settings(
        APP_ENV="development",
        REQUIRE_ANALYSIS_TOKEN=True,
        VIDEO_UPLOAD_DIR=str(tmp_path / "uploads"),
        VIDEO_RESULT_DIR=str(tmp_path / "results"),
        VIDEO_MODEL_PATH="",
    )
    service = VideoAnalysisService(test_settings, detector=DummyDetector())
    app.dependency_overrides[get_video_analysis_service] = lambda: service

    try:
        # Create a mock real analysis with token
        raw_token = "secure_secret_token_1234567890"
        import hashlib
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        job = AnalysisJob(
            analysis_id="analysis_sec1234567890abcdef",
            match_id="match_test",
            status=JobStatus.COMPLETED,
            mode="QUALITY",
            analysis_source="REAL_UPLOAD",
            evidence_origin="REAL_VIDEO_PIPELINE",
            access_token_hash=token_hash,
        )
        service.storage.create_job(job)

        with TestClient(app) as client:
            # 1. No token -> 401
            r_no_auth = client.get("/api/video-analysis/analysis_sec1234567890abcdef")
            assert r_no_auth.status_code == 401

            # 2. Invalid token -> 403
            r_bad_auth = client.get(
                "/api/video-analysis/analysis_sec1234567890abcdef",
                headers={"Authorization": "Bearer wrong_token"},
            )
            assert r_bad_auth.status_code == 403

            # 3. Valid bearer token -> 200
            r_valid = client.get(
                "/api/video-analysis/analysis_sec1234567890abcdef",
                headers={"Authorization": f"Bearer {raw_token}"},
            )
            assert r_valid.status_code == 200
            assert r_valid.json()["analysis_id"] == "analysis_sec1234567890abcdef"

            # 4. Valid query token parameter -> 200
            r_query = client.get(
                f"/api/video-analysis/analysis_sec1234567890abcdef?token={raw_token}"
            )
            assert r_query.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_missing_evidence_fails_closed_never_falls_back_to_demo(tmp_path: Path):
    test_settings = Settings(
        APP_ENV="development",
        REQUIRE_ANALYSIS_TOKEN=False,
        VIDEO_UPLOAD_DIR=str(tmp_path / "uploads"),
        VIDEO_RESULT_DIR=str(tmp_path / "results"),
        VIDEO_MODEL_PATH="",
    )
    service = VideoAnalysisService(test_settings, detector=DummyDetector())
    app.dependency_overrides[get_video_analysis_service] = lambda: service

    try:
        job = AnalysisJob(
            analysis_id="analysis_empty_evidence_test",
            match_id="match_test",
            status=JobStatus.COMPLETED,
            mode="QUALITY",
            analysis_source="REAL_UPLOAD",
            evidence_origin="REAL_VIDEO_PIPELINE",
        )
        service.storage.create_job(job)

        with TestClient(app) as client:
            # Timeline must fail closed with 404, NOT return demo SNMOT-068 evidence!
            resp = client.get("/api/video-analysis/analysis_empty_evidence_test/timeline")
            assert resp.status_code == 404
            assert "preuves tactiques ne sont pas disponibles" in resp.json()["detail"]
    finally:
        app.dependency_overrides.clear()


def test_magic_bytes_rejects_disguised_file(tmp_path: Path):
    fake_mp4 = tmp_path / "malicious.mp4"
    fake_mp4.write_text("<?php echo 'malicious shell'; ?>", encoding="utf-8")

    with pytest.raises(VideoValidationError) as exc:
        validate_video_magic_bytes(fake_mp4)
    assert "magic bytes invalides" in str(exc.value)


def test_legacy_sql_gated_in_production(monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "ENABLE_LEGACY_SQL_API", False)
    with TestClient(app) as client:
        resp = client.post(
            "/api/analyze",
            json={"prompt": "Qui est le meilleur joueur ?", "season": "2024_2025"},
        )
        assert resp.status_code == 403
        assert "disabled in production" in resp.json()["detail"]


def test_concurrency_limit_enforced(tmp_path: Path):
    test_settings = Settings(
        APP_ENV="development",
        MAX_CONCURRENT_ANALYSES=1,
        VIDEO_UPLOAD_DIR=str(tmp_path / "uploads"),
        VIDEO_RESULT_DIR=str(tmp_path / "results"),
        VIDEO_MODEL_PATH="",
    )
    service = VideoAnalysisService(test_settings, detector=DummyDetector())
    # Simulate an active ongoing job
    with service._active_lock:
        service._active_analyses.add("analysis_busy_now")

    upload_file = MagicMock()
    upload_file.filename = "test.mp4"

    import asyncio

    async def try_create():
        await service.create(upload_file)

    with pytest.raises(VideoValidationError) as exc:
        asyncio.run(try_create())
    assert "nombre maximal d'analyses simultanées" in str(exc.value)
