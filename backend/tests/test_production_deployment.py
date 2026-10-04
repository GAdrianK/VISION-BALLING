"""Unit and Integration Tests for Production Deployment Configuration.

Tests:
1. DATABASE_URL requirement & rejection of SQLite in production.
2. PostgreSQL URL scheme normalization (postgres:// -> postgresql://).
3. Public upload gate (fail-closed 403 Forbidden in production or when disabled).
4. Health check endpoint behaviour (200 OK vs 503 on database failure in production).
5. Deployment configuration artifacts (railway.json, Procfile, Dockerfile, .dockerignore, _redirects).
6. Production .env examples integrity (no secrets, no local user paths).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import Settings, settings as app_settings
from app.main import app


def test_production_requires_database_url():
    """APP_ENV=production must fail validation if DATABASE_URL is not set."""
    with pytest.raises(ValidationError, match="DATABASE_URL is mandatory in production mode"):
        Settings(
            APP_ENV="production",
            DATABASE_URL="",
            ALLOWED_ORIGINS="https://vision-balling.pages.dev",
            PUBLIC_UPLOAD_ENABLED=False,
        )


def test_production_forbids_sqlite():
    """APP_ENV=production must fail validation if DATABASE_URL is SQLite."""
    with pytest.raises(ValidationError, match="SQLite cannot be used in production mode"):
        Settings(
            APP_ENV="production",
            DATABASE_URL="sqlite:///./data/prod.db",
            ALLOWED_ORIGINS="https://vision-balling.pages.dev",
            PUBLIC_UPLOAD_ENABLED=False,
        )


def test_production_accepts_postgresql():
    """APP_ENV=production succeeds validation with valid PostgreSQL DATABASE_URL."""
    s = Settings(
        APP_ENV="production",
        DATABASE_URL="postgresql://user:pass@host:5432/dbname",
        ALLOWED_ORIGINS="https://vision-balling.pages.dev",
        PUBLIC_UPLOAD_ENABLED=False,
    )
    assert s.APP_ENV == "production"
    assert s.effective_database_url.startswith("postgresql://")


def test_effective_database_url_normalization():
    """postgres:// scheme must be converted to postgresql:// for modern SQLAlchemy."""
    s1 = Settings(DATABASE_URL="postgres://user:password@localhost:5432/vball")
    assert s1.effective_database_url.startswith("postgresql://")

    s2 = Settings(DATABASE_URL="postgresql://user:password@localhost:5432/vball")
    assert s2.effective_database_url.startswith("postgresql://")


def test_upload_gate_403_when_disabled():
    """POST /api/video-analysis must return 403 Forbidden when PUBLIC_UPLOAD_ENABLED=False."""
    client = TestClient(app)
    with patch.object(app_settings, "PUBLIC_UPLOAD_ENABLED", False), \
         patch.object(app_settings, "APP_ENV", "development"):
        response = client.post("/api/video-analysis")
        assert response.status_code == 403
        assert "Public video upload and GPU analysis are disabled" in response.json()["detail"]


def test_upload_gate_403_in_production_even_if_flag_true():
    """POST /api/video-analysis must return 403 Forbidden in production regardless of flag."""
    client = TestClient(app)
    with patch.object(app_settings, "PUBLIC_UPLOAD_ENABLED", True), \
         patch.object(app_settings, "APP_ENV", "production"):
        response = client.post("/api/video-analysis")
        assert response.status_code == 403
        assert "Public video upload and GPU analysis are disabled" in response.json()["detail"]


def test_health_check_production_db_probe_success():
    """In production, /health returns 200 if DB probe succeeds."""
    client = TestClient(app)
    mock_conn = MagicMock()
    mock_conn.execute.return_value = None
    mock_engine = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_svc = MagicMock()
    mock_svc.engine = mock_engine

    with patch.object(app_settings, "APP_ENV", "production"), \
         patch("app.services.beta_service.get_beta_service", return_value=mock_svc):
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


def test_health_check_production_db_probe_failure():
    """In production, /health returns 503 if DB probe fails."""
    client = TestClient(app)
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("Connection refused to PostgreSQL")
    mock_svc = MagicMock()
    mock_svc.engine = mock_engine

    with patch.object(app_settings, "APP_ENV", "production"), \
         patch("app.services.beta_service.get_beta_service", return_value=mock_svc):
        response = client.get("/health")
        assert response.status_code == 503
        assert "Service Unavailable" in response.json()["detail"]


def test_deployment_artifacts_exist():
    """Deployment configuration files must exist and contain valid directives."""
    project_root = Path(__file__).resolve().parents[2]

    # Cloudflare Pages SPA redirects
    cf_redirects = project_root / "frontend" / "public" / "_redirects"
    assert cf_redirects.exists(), "frontend/public/_redirects must exist for Cloudflare Pages"
    redirects_content = cf_redirects.read_text(encoding="utf-8")
    assert "/*" in redirects_content and "/index.html" in redirects_content and "200" in redirects_content

    # Railway configuration files
    railway_json = project_root / "railway.json"
    assert railway_json.exists(), "railway.json must exist"
    assert "uvicorn" in railway_json.read_text(encoding="utf-8")

    procfile = project_root / "Procfile"
    assert procfile.exists(), "Procfile must exist"
    assert "web:" in procfile.read_text(encoding="utf-8")

    dockerfile = project_root / "Dockerfile"
    assert dockerfile.exists(), "Dockerfile must exist"
    df_content = dockerfile.read_text(encoding="utf-8")
    assert "FROM python:3.12-slim" in df_content

    dockerignore = project_root / ".dockerignore"
    assert dockerignore.exists(), ".dockerignore must exist"
    di_content = dockerignore.read_text(encoding="utf-8")
    assert "*.pth" in di_content or "weights" in di_content or "*.pt" in di_content


def test_production_env_examples_contain_no_secrets():
    """Production .env examples must not leak real credentials or personal paths."""
    project_root = Path(__file__).resolve().parents[2]

    backend_example = project_root / "backend" / ".env.production.example"
    assert backend_example.exists()
    b_text = backend_example.read_text(encoding="utf-8")
    assert "localhost" not in b_text
    assert "/media/adriano" not in b_text
    assert "/home/adriano" not in b_text

    frontend_example = project_root / "frontend" / ".env.production.example"
    assert frontend_example.exists()
    f_text = frontend_example.read_text(encoding="utf-8")
    assert "localhost" not in f_text
    assert "127.0.0.1" not in f_text


def test_postgresql_drivers_declared():
    """Ensure both psycopg v3 and psycopg2 are present in backend requirements for Railway."""
    project_root = Path(__file__).resolve().parents[2]
    reqs = (project_root / "backend" / "requirements.txt").read_text(encoding="utf-8")
    assert "psycopg" in reqs
    assert "psycopg2" in reqs
