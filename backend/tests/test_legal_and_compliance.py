from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings, BASE_DIR
from app.main import app
from app.schemas.beta import BetaAnalysisRequestCreate
from app.services.beta_service import BetaService
import app.services.beta_service as beta_module


@pytest.fixture
def temp_beta_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_db = tmp_path / "test_compliance_beta.db"
    service = BetaService(db_target=test_db)
    monkeypatch.setattr(beta_module, "_global_beta_service", service)
    return service


@pytest.fixture
def client(temp_beta_service: BetaService):
    return TestClient(app)


def test_production_settings_enforces_no_wildcard_cors():
    with pytest.raises(ValueError, match=r"ALLOWED_ORIGINS cannot be '\*' or empty"):
        Settings(APP_ENV="production", ALLOWED_ORIGINS="*")


def test_production_settings_enforces_public_upload_disabled():
    with pytest.raises(ValueError, match="PUBLIC_UPLOAD_ENABLED must be False in production mode"):
        Settings(
            APP_ENV="production",
            ALLOWED_ORIGINS="https://app.vision-balling.fr",
            PUBLIC_UPLOAD_ENABLED=True,
        )


def test_production_settings_valid_configuration():
    cfg = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql://user:pass@ep-prod.railway.internal:5432/railway",
        ALLOWED_ORIGINS="https://app.vision-balling.fr",
        PUBLIC_UPLOAD_ENABLED=False,
    )
    assert cfg.APP_ENV == "production"
    assert cfg.ALLOWED_ORIGINS == "https://app.vision-balling.fr"
    assert cfg.PUBLIC_UPLOAD_ENABLED is False


def test_retention_defaults_configured():
    cfg = Settings(APP_ENV="development")
    assert cfg.BETA_REQUEST_RETENTION_DAYS >= 1
    assert cfg.VIDEO_RETENTION_DAYS >= 1
    assert cfg.ANALYSIS_RESULT_RETENTION_DAYS >= 1


def test_retention_cleanup_deletes_expired_requests(temp_beta_service: BetaService):
    now = datetime.now(timezone.utc)
    old_time = (now - timedelta(days=200)).isoformat()
    recent_time = (now - timedelta(days=10)).isoformat()

    with temp_beta_service.engine.begin() as conn:
        from sqlalchemy import text
        # Insert old request
        conn.execute(
            text(
                """
                INSERT INTO beta_analysis_requests (
                    id, created_at, name, club, role, email, phone, team_category,
                    competition_level, opponent, video_type, video_url,
                    analysis_objectives, message, video_authorization_confirmed,
                    temporary_storage_consent, status
                ) VALUES (
                    'beta_old1', :created_at, 'Old Coach', 'Old Club', 'Entraîneur',
                    'old@club.fr', NULL, 'U19', 'R1', NULL, 'Extrait',
                    'https://swisstransfer.com/d/old', '[]', NULL, 1, 1, 'NEW'
                );
                """
            ),
            {"created_at": old_time},
        )
        # Insert recent request
        conn.execute(
            text(
                """
                INSERT INTO beta_analysis_requests (
                    id, created_at, name, club, role, email, phone, team_category,
                    competition_level, opponent, video_type, video_url,
                    analysis_objectives, message, video_authorization_confirmed,
                    temporary_storage_consent, status
                ) VALUES (
                    'beta_recent1', :created_at, 'Recent Coach', 'Recent Club', 'Entraîneur',
                    'recent@club.fr', NULL, 'U19', 'R1', NULL, 'Extrait',
                    'https://swisstransfer.com/d/recent', '[]', NULL, 1, 1, 'NEW'
                );
                """
            ),
            {"created_at": recent_time},
        )

    # Clean up with retention = 180 days
    deleted = temp_beta_service.cleanup_expired_requests(retention_days=180)
    assert deleted == 1

    # Only recent should remain
    assert temp_beta_service.get_request("beta_old1") is None
    assert temp_beta_service.get_request("beta_recent1") is not None


def test_database_url_resolution():
    # SQLite direct string
    url_sqlite = BetaService._resolve_db_url("sqlite:////tmp/test.db")
    assert url_sqlite == "sqlite:////tmp/test.db"

    # PostgreSQL string
    url_pg = BetaService._resolve_db_url("postgresql://user:pass@localhost:5432/db")
    assert url_pg == "postgresql://user:pass@localhost:5432/db"

    # Path to file
    p = Path("/tmp/my_beta.db")
    url_path = BetaService._resolve_db_url(p)
    assert url_path.startswith("sqlite:///")


def test_strengthened_video_authorization_validation():
    base_data = {
        "name": "Didier Deschamps",
        "club": "FFF",
        "role": "Entraîneur",
        "email": "didier@fff.fr",
        "team_category": "Équipe A",
        "competition_level": "International",
        "video_type": "Match complet",
        "video_url": "https://swisstransfer.com/d/didier",
        "analysis_objectives": ["Transitions"],
        "temporary_storage_consent": True,
    }

    # When video_authorization_confirmed is False
    with pytest.raises(ValueError, match="droits et autorisations nécessaires"):
        BetaAnalysisRequestCreate(**base_data, video_authorization_confirmed=False)

    # When video_authorization_confirmed is True
    valid = BetaAnalysisRequestCreate(**base_data, video_authorization_confirmed=True)
    assert valid.video_authorization_confirmed is True


def test_public_upload_disabled_in_production():
    import asyncio
    from unittest.mock import MagicMock
    from app.video_analysis.service import VideoAnalysisService
    from app.video_analysis.validation import VideoValidationError

    prod_settings = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql://user:pass@ep-prod.railway.internal:5432/railway",
        ALLOWED_ORIGINS="https://app.vision-balling.fr",
        PUBLIC_UPLOAD_ENABLED=False,
    )
    service = VideoAnalysisService(settings=prod_settings)
    dummy_upload = MagicMock()
    dummy_upload.filename = "match.mp4"

    with pytest.raises(VideoValidationError, match="Public video uploads are disabled"):
        asyncio.run(service.create(dummy_upload))


def test_frontend_legal_and_compliance_pages_exist():
    repo_root = BASE_DIR.parent
    frontend_components = repo_root / "frontend" / "src" / "components"

    expected_files = [
        "LegalPage.jsx",
        "PrivacyPage.jsx",
        "BetaTermsPage.jsx",
        "CookiesPage.jsx",
        "LicensesPage.jsx",
    ]

    for fname in expected_files:
        fpath = frontend_components / fname
        assert fpath.is_file(), f"Missing compliance component: {fname}"
        content = fpath.read_text(encoding="utf-8")
        assert len(content) > 200

    # Ensure LegalPage or legalConfig contains mandatory LCEN placeholders
    legal_content = (frontend_components / "LegalPage.jsx").read_text(encoding="utf-8")
    config_file = frontend_components.parent / "config" / "legalConfig.js"
    combined_content = legal_content + (("\n" + config_file.read_text(encoding="utf-8")) if config_file.is_file() else "")
    for placeholder in ["[LEGAL_NAME]", "[PROFESSIONAL_ADDRESS]", "[EMAIL]", "[HOST_NAME]", "[NAME]"]:
        assert placeholder in combined_content, f"Missing placeholder in LegalPage / legalConfig: {placeholder}"

    # Ensure App.jsx wires all routes
    app_content = (repo_root / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    for route in ["/legal", "/privacy", "/cookies", "/beta-terms", "/licenses"]:
        assert route in app_content, f"Route {route} not wired in App.jsx"
