from __future__ import annotations

import logging
import smtplib
from unittest.mock import MagicMock, patch

import pytest
from app.core.config import Settings
from app.schemas.beta import BetaAnalysisRequestCreate
from app.services.mail_service import MailService, build_beta_notification_body


@pytest.fixture
def sample_beta_request() -> BetaAnalysisRequestCreate:
    return BetaAnalysisRequestCreate(
        name="Thierry Henry",
        club="AS Monaco",
        role="Entraîneur",
        email="thierry@monaco.fr",
        phone="+33600000000",
        team_category="Séniors",
        competition_level="Ligue 1",
        opponent="OGC Nice",
        video_type="Match complet",
        video_url="https://drive.google.com/file/d/test1234/view?usp=sharing",
        analysis_objectives=["Pressing", "Transitions"],
        message="Analyse de la transition défensive en 1ère mi-temps.",
        video_authorization_confirmed=True,
        temporary_storage_consent=True,
    )


def test_build_beta_notification_body(sample_beta_request: BetaAnalysisRequestCreate):
    body = build_beta_notification_body(
        sample_beta_request,
        request_id="beta_abc123",
        created_at_iso="2026-10-04T19:00:00Z",
    )
    assert "beta_abc123" in body
    assert "2026-10-04T19:00:00Z" in body
    assert "Thierry Henry" in body
    assert "AS Monaco" in body
    assert "thierry@monaco.fr" in body
    assert "+33600000000" in body
    assert "Séniors" in body
    assert "Ligue 1" in body
    assert "OGC Nice" in body
    assert "Match complet" in body
    assert "https://drive.google.com/file/d/test1234/view?usp=sharing" in body
    assert "Pressing" in body
    assert "Transitions" in body
    assert "Analyse de la transition défensive" in body
    assert "Autorisation droits vidéo confirmée : OUI" in body
    assert "Consentement stockage temporaire    : OUI" in body


def test_mail_service_unconfigured_skips_safely(sample_beta_request: BetaAnalysisRequestCreate):
    cfg = Settings(SMTP_HOST="", SMTP_PORT=587)
    service = MailService(settings_override=cfg)
    assert not service.is_configured
    assert service.send_beta_request_notification(sample_beta_request, "beta_123", "2026-10-04T19:00:00Z") is False


def test_mail_service_success_smtp_587(sample_beta_request: BetaAnalysisRequestCreate):
    cfg = Settings(
        SMTP_HOST="mail.test.example",
        SMTP_PORT=587,
        SMTP_USERNAME="test-sender@example.invalid",
        SMTP_PASSWORD="DUMMY-MOCK-TEST-AUTH-PASS",
        SMTP_USE_TLS=True,
        BETA_NOTIFICATION_EMAIL="contact@vision-balling.fr",
    )
    service = MailService(settings_override=cfg)
    assert service.is_configured

    with patch("smtplib.SMTP") as mock_smtp_cls:
        mock_server = MagicMock()
        mock_smtp_cls.return_value.__enter__.return_value = mock_server

        success = service.send_beta_request_notification(
            sample_beta_request,
            request_id="beta_987",
            created_at_iso="2026-10-04T19:00:00Z",
        )

        assert success is True
        mock_smtp_cls.assert_called_once_with("mail.test.example", 587, timeout=10.0)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("test-sender@example.invalid", "DUMMY-MOCK-TEST-AUTH-PASS")
        mock_server.send_message.assert_called_once()

        sent_msg = mock_server.send_message.call_args[0][0]
        assert sent_msg["Subject"] == "[VISION-BALLING] Nouvelle demande BETA — AS Monaco"
        assert sent_msg["To"] == "contact@vision-balling.fr"
        assert sent_msg["From"] == "test-sender@example.invalid"
        content = sent_msg.get_content()
        assert "Thierry Henry" in content
        assert "AS Monaco" in content


def test_mail_service_success_ssl_465(sample_beta_request: BetaAnalysisRequestCreate):
    cfg = Settings(
        SMTP_HOST="ssl.test.example",
        SMTP_PORT=465,
        SMTP_USERNAME="test-sender@example.invalid",
        SMTP_PASSWORD="DUMMY-MOCK-TEST-AUTH-PASS",
        BETA_NOTIFICATION_EMAIL="contact@vision-balling.fr",
    )
    service = MailService(settings_override=cfg)

    with patch("smtplib.SMTP_SSL") as mock_ssl_cls:
        mock_server = MagicMock()
        mock_ssl_cls.return_value.__enter__.return_value = mock_server

        success = service.send_beta_request_notification(
            sample_beta_request,
            request_id="beta_465",
            created_at_iso="2026-10-04T19:00:00Z",
        )

        assert success is True
        mock_ssl_cls.assert_called_once()
        mock_server.login.assert_called_once_with("test-sender@example.invalid", "DUMMY-MOCK-TEST-AUTH-PASS")
        mock_server.send_message.assert_called_once()


def test_mail_service_failure_returns_false_and_does_not_raise(sample_beta_request: BetaAnalysisRequestCreate):
    cfg = Settings(
        SMTP_HOST="mail.test.example",
        SMTP_PORT=587,
        SMTP_USERNAME="test-sender@example.invalid",
        SMTP_PASSWORD="DUMMY-MOCK-FAIL-AUTH-PASS",
    )
    service = MailService(settings_override=cfg)

    with patch("smtplib.SMTP", side_effect=smtplib.SMTPConnectError(421, b"Connection refused")):
        success = service.send_beta_request_notification(
            sample_beta_request,
            request_id="beta_fail",
            created_at_iso="2026-10-04T19:00:00Z",
        )
        assert success is False


def test_mail_service_secrets_never_logged(
    sample_beta_request: BetaAnalysisRequestCreate,
    caplog: pytest.LogCaptureFixture,
):
    secret_pass = "DUMMY-CLASSIFIED-SECRET-XYZ-987"
    cfg = Settings(
        SMTP_HOST="mail.test.example",
        SMTP_PORT=587,
        SMTP_USERNAME="test-sender@example.invalid",
        SMTP_PASSWORD=secret_pass,
    )
    service = MailService(settings_override=cfg)

    with patch("smtplib.SMTP", side_effect=smtplib.SMTPAuthenticationError(535, b"Auth failed")):
        with caplog.at_level(logging.DEBUG):
            service.send_beta_request_notification(
                sample_beta_request,
                request_id="beta_safe_log",
                created_at_iso="2026-10-04T19:00:00Z",
            )

    assert secret_pass not in caplog.text
