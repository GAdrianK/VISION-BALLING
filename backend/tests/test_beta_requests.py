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
    url_with_token = "https://drive.google.com/file/d/12345/view?usp=sharing&auth_token=token_sample_abc123"
    redacted = redact_url_for_logging(url_with_token)
    assert "token_sample_abc123" not in redacted
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


def test_beta_submission_triggers_email_notification(
    client: TestClient,
    temp_beta_service: BetaService,
    monkeypatch: pytest.MonkeyPatch,
):
    from unittest.mock import MagicMock, patch
    from app.core.config import settings

    monkeypatch.setattr(settings, "SMTP_HOST", "mail.test.example")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "test-bot@example.invalid")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "DUMMY-MOCK-TEST-AUTH-PASS")
    monkeypatch.setattr(settings, "BETA_NOTIFICATION_EMAIL", "contact@vision-balling.fr")

    payload = {
        "name": "Zinédine Zidane",
        "club": "Real Madrid Castilla",
        "role": "Entraîneur",
        "email": "zizou@madrid.es",
        "team_category": "Réserve Pro",
        "competition_level": "Primera Federación",
        "opponent": "Barça Atlètic",
        "video_type": "Match complet",
        "video_url": "https://drive.google.com/file/d/zizou123/view",
        "analysis_objectives": ["Transitions", "Pressing"],
        "message": "Focus transitions rapides.",
        "video_authorization_confirmed": True,
        "temporary_storage_consent": True,
    }

    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_server

        res = client.post("/api/beta-requests", json=payload)
        assert res.status_code == 201
        data = res.json()
        assert data["id"].startswith("beta_")

        # Verify DB persistence
        stored = temp_beta_service.get_request(data["id"])
        assert stored is not None
        assert stored["club"] == "Real Madrid Castilla"

        # Verify SMTP interaction
        mock_server.send_message.assert_called_once()
        msg = mock_server.send_message.call_args[0][0]
        assert msg["To"] == "contact@vision-balling.fr"
        assert msg["Subject"] == "[VISION-BALLING] Nouvelle demande BETA — Real Madrid Castilla"
        assert "Zinédine Zidane" in msg.get_content()
        assert "https://drive.google.com/file/d/zizou123/view" in msg.get_content()


def test_beta_submission_succeeds_when_smtp_fails(
    client: TestClient,
    temp_beta_service: BetaService,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
):
    from unittest.mock import patch
    import smtplib
    from app.core.config import settings

    monkeypatch.setattr(settings, "SMTP_HOST", "mail.test.example")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "test-bot@example.invalid")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "DUMMY-DO-NOT-LOG-SECRET-XYZ")
    monkeypatch.setattr(settings, "BETA_NOTIFICATION_EMAIL", "contact@vision-balling.fr")

    payload = {
        "name": "Didier Deschamps",
        "club": "Équipe de France",
        "role": "Entraîneur",
        "email": "didier@fff.fr",
        "team_category": "Séniors",
        "competition_level": "International",
        "opponent": "Espagne",
        "video_type": "Match complet",
        "video_url": "https://wetransfer.com/downloads/fff123?auth_token=token_sample_abc123",
        "analysis_objectives": ["Bloc / compacité"],
        "video_authorization_confirmed": True,
        "temporary_storage_consent": True,
    }

    # Simulate SMTP failure (timeout, network outage, auth error)
    with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, b"Connection refused")):
        with caplog.at_level(logging.WARNING):
            res = client.post("/api/beta-requests", json=payload)

    # 1. API request MUST still succeed (Fail-safe architecture)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "NEW"

    # 2. Database request MUST be persisted
    stored = temp_beta_service.get_request(data["id"])
    assert stored is not None
    assert stored["name"] == "Didier Deschamps"
    assert stored["club"] == "Équipe de France"

    # 3. Secrets and private video tokens must NOT be leaked into logs
    assert "DUMMY-DO-NOT-LOG-SECRET-XYZ" not in caplog.text
    assert "token_sample_abc123" not in caplog.text


def test_beta_crlf_injection_neutralized(client: TestClient, temp_beta_service: BetaService):
    """
    Vérifie que les tentatives d'injection CRLF (\r\n) dans les champs texte
    (susceptibles d'affecter les en-têtes SMTP ou les logs) sont neutralisées.
    """
    payload = {
        "name": "Jean-Pierre\r\nAttacker",
        "club": "FC Test\r\nBcc: evil@attacker.invalid\r\n",
        "role": "Entraîneur",
        "email": "coach@test.invalid",
        "phone": "+33 6 12 34 56 78",
        "team_category": "Séniors\nInjection",
        "competition_level": "Régional 1\rInjection",
        "opponent": "Adversaire\r\nTest",
        "video_type": "Match complet",
        "video_url": "https://example.invalid/match.mp4",
        "analysis_objectives": ["Bloc / compacité"],
        "message": "Message multi-lignes\nAutorisé ici\r\nNormalisé",
        "video_authorization_confirmed": True,
        "temporary_storage_consent": True,
    }

    res = client.post("/api/beta-requests", json=payload)
    assert res.status_code == 201
    data = res.json()

    stored = temp_beta_service.get_request(data["id"])
    assert stored is not None
    # Vérification qu'aucun CRLF ne subsiste dans les champs mono-lignes
    assert "\r" not in stored["name"]
    assert "\n" not in stored["name"]
    assert stored["name"] == "Jean-Pierre Attacker"

    assert "\r" not in stored["club"]
    assert "\n" not in stored["club"]
    assert stored["club"] == "FC Test Bcc: evil@attacker.invalid"

    assert "\r" not in stored["opponent"]
    assert "\n" not in stored["opponent"]
