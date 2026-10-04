from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage
from typing import Optional

from app.core.config import Settings, settings
from app.schemas.beta import BetaAnalysisRequestCreate

logger = logging.getLogger(__name__)


def build_beta_notification_body(
    req: BetaAnalysisRequestCreate,
    request_id: str,
    created_at_iso: str,
) -> str:
    """Constructs the canonical plain-text notification email body for a new BETA request."""
    objectives_list = req.analysis_objectives if req.analysis_objectives else []
    objectives_formatted = (
        "\n".join(f"  - {obj}" for obj in objectives_list)
        if objectives_list
        else "  (Aucun objectif spécifié)"
    )
    phone_formatted = req.phone.strip() if req.phone and req.phone.strip() else "Non renseigné"
    opponent_formatted = req.opponent.strip() if req.opponent and req.opponent.strip() else "Non renseigné"
    message_formatted = req.message.strip() if req.message and req.message.strip() else "Aucun message complémentaire"

    return f"""Bonjour,

Une nouvelle demande d'accès au pilote BETA VISION-BALLING a été enregistrée.

==================================================
RÉFÉRENCE DE LA DEMANDE
==================================================
ID Demande           : {request_id}
Date / Heure (UTC)   : {created_at_iso}

==================================================
DEMANDEUR & CLUB
==================================================
Nom / Prénom         : {req.name}
Club / Organisation  : {req.club}
Rôle / Fonction      : {req.role}
Courriel             : {req.email}
Téléphone            : {phone_formatted}

==================================================
MATCH & SÉQUENCE VIDÉO
==================================================
Catégorie d'équipe   : {req.team_category}
Niveau de compétition: {req.competition_level}
Adversaire           : {opponent_formatted}
Type de vidéo        : {req.video_type}
Lien vidéo           : {req.video_url}

==================================================
OBJECTIFS D'ANALYSE
==================================================
{objectives_formatted}

==================================================
MESSAGE COMPLÉMENTAIRE
==================================================
{message_formatted}

==================================================
CONSENTEMENTS & ENGAGEMENTS
==================================================
Autorisation droits vidéo confirmée : {'OUI' if req.video_authorization_confirmed else 'NON'}
Consentement stockage temporaire    : {'OUI' if req.temporary_storage_consent else 'NON'}

--
VISION-BALLING — Système de notification
Enregistrement PostgreSQL : validé
"""


def build_analysis_ready_body(
    coach_name: str,
    match_name: str,
    access_url: str,
    video_retention_days: int = 14,
    analysis_retention_days: int = 30,
) -> str:
    """Builds canonical notification body informing coach their private analysis is ready."""
    return f"""Bonjour {coach_name},

Votre analyse tactique VISION-BALLING pour la rencontre « {match_name} » est prête et disponible dans votre espace privé.

==================================================
ACCÈS PRIVÉ À VOTRE ANALYSE
==================================================

Lien direct sécurisé (aucun mot de passe requis) :
{access_url}

Ce lien contient une capacité d'accès exclusive et confidentielle. Ne le partagez qu'avec le staff technique autorisé de votre club.

==================================================
FONCTIONNALITÉS DISPONIBLES
==================================================
- Vidéo annotée avec détections de joueurs, porteur et ballon
- Chronologie tactique ordonnée des phases de jeu
- Fiches de preuves mesurées (pressing, compacité, transitions, contrôle)
- Assistant tactique ancré : posez vos questions sur la rencontre
- Rapport d'analyse tactique imprimable / exportable

==================================================
POLITIQUE DE RÉTENTION DES DONNÉES
==================================================
- Vidéo de match (streaming) : conservée pendant {video_retention_days} jours
- Métriques, chronologie et assistant : conservés pendant {analysis_retention_days} jours

Pour toute question ou remarque méthodologique, vous pouvez répondre directement à ce courriel.

--
L'équipe VISION-BALLING
contact@vision-balling.fr — https://vision-balling.fr
"""


class MailService:
    """Standard SMTP mail service for application notifications."""

    def __init__(self, settings_override: Optional[Settings] = None) -> None:
        self._cfg = settings_override or settings

    @property
    def host(self) -> str:
        return self._cfg.SMTP_HOST.strip()

    @property
    def port(self) -> int:
        return self._cfg.SMTP_PORT

    @property
    def username(self) -> str:
        return self._cfg.SMTP_USERNAME.strip()

    @property
    def password(self) -> str:
        return self._cfg.SMTP_PASSWORD.strip()

    @property
    def use_tls(self) -> bool:
        return self._cfg.SMTP_USE_TLS

    @property
    def timeout(self) -> float:
        return self._cfg.SMTP_TIMEOUT_SECONDS

    @property
    def from_email(self) -> str:
        return self._cfg.effective_smtp_from_email

    @property
    def beta_recipient(self) -> str:
        return self._cfg.BETA_NOTIFICATION_EMAIL.strip() or "contact@vision-balling.fr"

    @property
    def is_configured(self) -> bool:
        return bool(self.host)

    def send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        from_email: Optional[str] = None,
    ) -> bool:
        """Sends a plain-text email via SMTP.

        Fails gracefully and never leaks passwords or secrets in logs.
        Returns True on success, False on failure or when unconfigured.
        """
        if not self.is_configured:
            if self._cfg.APP_ENV == "production":
                logger.warning(
                    "BETA notification email skipped: SMTP_HOST is not configured in production environment. "
                    "Configure SMTP_HOST, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD in Railway variables."
                )
            else:
                logger.info(
                    "BETA notification email skipped: SMTP is not configured (APP_ENV=%s).",
                    self._cfg.APP_ENV,
                )
            return False

        sender = (from_email or self.from_email).strip()
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        msg.set_content(body)

        try:
            if self.port == 465:
                # SSL / SMTPS direct wrapper
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(self.host, self.port, context=context, timeout=self.timeout) as server:
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.send_message(msg)
            else:
                # Standard SMTP with optional STARTTLS (e.g. port 587 or 25)
                with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                    server.ehlo()
                    if self.use_tls:
                        context = ssl.create_default_context()
                        server.starttls(context=context)
                        server.ehlo()
                    if self.username and self.password:
                        server.login(self.username, self.password)
                    server.send_message(msg)

            logger.info("Notification email successfully sent to %s (subject='%s')", to_email, subject)
            return True
        except Exception as e:
            # Crucial: Never log passwords or secrets
            logger.warning(
                "Failed to send notification email to %s (host=%s, port=%d): %s: %s",
                to_email,
                self.host,
                self.port,
                type(e).__name__,
                str(e),
            )
            return False

    def send_beta_request_notification(
        self,
        req: BetaAnalysisRequestCreate,
        request_id: str,
        created_at_iso: str,
    ) -> bool:
        """Constructs and delivers notification for a newly stored BETA request."""
        club_display = req.club.strip() if req.club and req.club.strip() else "Club non précisé"
        subject = f"[VISION-BALLING] Nouvelle demande BETA — {club_display}"
        body = build_beta_notification_body(req, request_id, created_at_iso)
        recipient = self.beta_recipient
        return self.send_email(to_email=recipient, subject=subject, body=body)

    def send_analysis_ready_notification(
        self,
        recipient_email: str,
        coach_name: str,
        match_name: str,
        access_url: str,
        video_retention_days: int = 14,
        analysis_retention_days: int = 30,
    ) -> bool:
        """Constructs and delivers notification to coach informing their private analysis is ready."""
        subject = f"[VISION-BALLING] Votre analyse tactique est prête — {match_name}"
        body = build_analysis_ready_body(
            coach_name=coach_name,
            match_name=match_name,
            access_url=access_url,
            video_retention_days=video_retention_days,
            analysis_retention_days=analysis_retention_days,
        )
        return self.send_email(to_email=recipient_email, subject=subject, body=body)


_global_mail_service: Optional[MailService] = None


def get_mail_service() -> MailService:
    global _global_mail_service
    if _global_mail_service is None:
        _global_mail_service = MailService()
    return _global_mail_service
