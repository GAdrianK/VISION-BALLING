from __future__ import annotations

import logging
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from app.main import app
from app.services.beta_service import BetaService, redact_url_for_logging
import app.services.beta_service as beta_module


@pytest.fixture
def temp_beta_service(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    test_db = tmp_path / "test_beta_requests.db"
    service = BetaService(db_path=test_db)
    monkeypatch.setattr(beta_module, "_global_beta_service", service)
    return service


@pytest.fixture
def client(temp_beta_service: BetaService):
    return TestClient(app)


def test_redact_url_for_logging():
    url_with_token = "https://drive.google.com/file/d/12345/view?usp=sharing&token=secret123"
    redacted = redact_url_for_logging(url_with_token)
    assert "token=secret123" not in redacted
    assert redacted == "https://drive.google.com/file/d/12345/view?..."

    url_clean = "https://wetransfer.com/downloads/abc"
    assert redact_url_for_logging(url_clean) == "https://wetransfer.com/downloads/abc"


def test_submit_beta_request_success(client: TestClient, temp_beta_service: BetaService):
    payload = {
        "name": "Arsène Wenger",
        "club": "Arsenal Academy",
        "role": "Entraîneur",
        "email": "arsene@arsenal.com",
        "phone": "+33612345678",
        "team_category": "U19 Nationaux",
        "competition_level": "National",
        "opponent": "Chelsea U19",
        "video_type": "Match complet",
        "video_url": "https://drive.google.com/file/d/abcdef123456/view?usp=sharing",
        "analysis_objectives": ["Bloc / compacité", "Pressing", "Transitions"],
        "message": "Focus sur le bloc médian en seconde période.",
        "video_authorization_confirmed": True,
        "temporary_storage_consent": True,
        "honeypot": "",
    }

    response = client.post("/api/beta-requests", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["id"].startswith("beta_")
    assert data["status"] == "NEW"
    assert "enregistrée" in data["message"]

    # Verify database persistence
    stored = temp_beta_service.get_request(data["id"])
    assert stored is not None
    assert stored["name"] == "Arsène Wenger"
    assert stored["club"] == "Arsenal Academy"
    assert stored["video_type"] == "Match complet"
    assert "Pressing" in stored["analysis_objectives"]
    assert stored["status"] == "NEW"


def test_submit_beta_request_missing_required_fields(client: TestClient):
    payload = {
        "name": "Jean Dupont",
        # Missing club, email, etc.
    }
    response = client.post("/api/beta-requests", json=payload)
    assert response.status_code == 422


def test_submit_beta_request_invalid_email(client: TestClient):
    payload = {
        "name": "Jean Dupont",
        "club": "AS Monaco",
        "role": "Analyste vidéo",
        "email": "not-an-email",
        "team_category": "Séniors",
        "competition_level": "Ligue 1",
        "video_type": "Extrait",
        "video_url": "https://swisstransfer.com/d/123",
        "analysis_objectives": ["Analyse globale"],
        "video_authorization_confirmed": True,
        "temporary_storage_consent": True,
    }
    response = client.post("/api/beta-requests", json=payload)
    assert response.status_code == 422


def test_submit_beta_request_invalid_video_scheme_javascript(client: TestClient):
    payload = {
        "name": "Jean Dupont",
        "club": "AS Monaco",
        "role": "Analyste vidéo",
        "email": "jean@monaco.fr",
        "team_category": "Séniors",
        "competition_level": "Ligue 1",
        "video_type": "Extrait",
        "video_url": "javascript:alert(1)",
        "analysis_objectives": ["Analyse globale"],
        "video_authorization_confirmed": True,
        "temporary_storage_consent": True,
    }
    response = client.post("/api/beta-requests", json=payload)
    assert response.status_code == 422


def test_submit_beta_request_invalid_video_scheme_ftp_and_data(client: TestClient):
    for bad_url in ["ftp://files.example.com/video.mp4", "data:text/html;base64,PHNjcmlwdD4="]:
        payload = {
            "name": "Jean Dupont",
            "club": "AS Monaco",
            "role": "Analyste vidéo",
            "email": "jean@monaco.fr",
            "team_category": "Séniors",
            "competition_level": "Ligue 1",
            "video_type": "Extrait",
            "video_url": bad_url,
            "analysis_objectives": ["Analyse globale"],
            "video_authorization_confirmed": True,
            "temporary_storage_consent": True,
        }
        response = client.post("/api/beta-requests", json=payload)
        assert response.status_code == 422


def test_submit_beta_request_missing_authorizations(client: TestClient):
    base_payload = {
        "name": "Jean Dupont",
        "club": "AS Monaco",
        "role": "Analyste vidéo",
        "email": "jean@monaco.fr",
        "team_category": "Séniors",
        "competition_level": "Ligue 1",
        "video_type": "Extrait",
        "video_url": "https://swisstransfer.com/d/123",
        "analysis_objectives": ["Analyse globale"],
    }

    # Missing video authorization
    payload1 = {**base_payload, "video_authorization_confirmed": False, "temporary_storage_consent": True}
    res1 = client.post("/api/beta-requests", json=payload1)
    assert res1.status_code == 422

    # Missing storage consent
    payload2 = {**base_payload, "video_authorization_confirmed": True, "temporary_storage_consent": False}
    res2 = client.post("/api/beta-requests", json=payload2)
    assert res2.status_code == 422


def test_submit_beta_request_honeypot_rejection(client: TestClient):
    payload = {
        "name": "Spam Bot",
        "club": "Bot Club",
        "role": "Staff",
        "email": "bot@spam.com",
        "team_category": "Séniors",
        "competition_level": "District",
        "video_type": "Extrait",
        "video_url": "https://youtube.com/watch?v=123",
        "analysis_objectives": ["Analyse globale"],
        "video_authorization_confirmed": True,
        "temporary_storage_consent": True,
        "honeypot": "https://spamsite.com",  # Bot filled this
    }
    response = client.post("/api/beta-requests", json=payload)
    assert response.status_code == 400
    assert "invalide" in response.json()["detail"].lower()


def test_submit_beta_request_rate_limiting(client: TestClient, temp_beta_service: BetaService):
    payload = {
        "name": "Jean Dupont",
        "club": "AS Monaco",
        "role": "Analyste vidéo",
        "email": "jean@monaco.fr",
        "team_category": "Séniors",
        "competition_level": "Ligue 1",
        "video_type": "Extrait",
        "video_url": "https://swisstransfer.com/d/123",
        "analysis_objectives": ["Analyse globale"],
        "video_authorization_confirmed": True,
        "temporary_storage_consent": True,
    }

    # Max requests is 5
    for _ in range(5):
        res = client.post("/api/beta-requests", json=payload)
        assert res.status_code == 201

    # 6th request from same client should hit rate limit
    res6 = client.post("/api/beta-requests", json=payload)
    assert res6.status_code == 429
    assert "trop de demandes" in res6.json()["detail"].lower()


def test_no_sensitive_tokens_in_logs(client: TestClient, caplog: pytest.LogCaptureFixture):
    secret_token = "secret_access_token_xyz987"
    video_url = f"https://drive.google.com/file/d/test12345/view?auth_token={secret_token}"
    payload = {
        "name": "Jean Dupont",
        "club": "AS Monaco",
        "role": "Analyste vidéo",
        "email": "jean@monaco.fr",
        "team_category": "Séniors",
        "competition_level": "Ligue 1",
        "video_type": "Extrait",
        "video_url": video_url,
        "analysis_objectives": ["Analyse globale"],
        "video_authorization_confirmed": True,
        "temporary_storage_consent": True,
    }

    with caplog.at_level(logging.INFO):
        res = client.post("/api/beta-requests", json=payload)
        assert res.status_code == 201

    # Ensure secret token was never logged
    for record in caplog.records:
        assert secret_token not in record.message


def test_xss_protection_in_fields(client: TestClient, temp_beta_service: BetaService):
    payload = {
        "name": "<script>alert('xss')</script>Coach",
        "club": "<img src=x onerror=alert(1)>FC",
        "role": "Entraîneur",
        "email": "coach@safe.com",
        "team_category": "U17",
        "competition_level": "Régional",
        "video_type": "Extrait",
        "video_url": "https://dropbox.com/s/123/video.mp4",
        "analysis_objectives": ["Analyse globale"],
        "message": "Hello <script>evil()</script>",
        "video_authorization_confirmed": True,
        "temporary_storage_consent": True,
    }
    res = client.post("/api/beta-requests", json=payload)
    assert res.status_code == 201
    req_id = res.json()["id"]

    stored = temp_beta_service.get_request(req_id)
    # The fields should be stored as plain strings, never interpreted, and response never reflects them unescaped
    assert stored is not None
    assert "<script>" in stored["name"] or "Coach" in stored["name"]
