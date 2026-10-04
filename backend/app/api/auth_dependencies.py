from __future__ import annotations

import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

from fastapi import Cookie, Depends, Header, HTTPException, Request, status

from app.core.config import settings
from app.services.publication_service import PublicationService, get_publication_service

logger = logging.getLogger(__name__)


def verify_operator_token(
    authorization: Optional[str] = Header(default=None),
) -> None:
    """Authenticates the local GPU workstation operator via constant-time HMAC comparison.
    
    Strictly isolated: Coach tokens or session cookies are NEVER accepted on operator endpoints.
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification opérateur requise.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    raw_token = authorization[7:].strip()
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token opérateur manquant.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    operator_hash = (settings.OPERATOR_TOKEN_HASH or "").strip()
    if not operator_hash:
        if settings.APP_ENV == "production":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Configuration serveur invalide : hash opérateur absent.",
            )
        # Development fallback: allow test operator token if configured or matching dev default
        operator_hash = hashlib.sha256("dev-operator-token".encode("utf-8")).hexdigest()

    candidate_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(candidate_hash, operator_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès opérateur interdit : token invalide.",
        )


def get_authenticated_session(
    analysis_id: str,
    vb_host_session: Optional[str] = Cookie(alias="__Host-vb_session", default=None),
    vb_fallback_session: Optional[str] = Cookie(alias="vb_session", default=None),
    pub_service: PublicationService = Depends(get_publication_service),
) -> Dict[str, Any]:
    """Validates coach session cookie and verifies strict tenancy bound to analysis_id."""
    session_token = vb_host_session or vb_fallback_session
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session d'analyse requise. Veuillez utiliser votre lien d'accès privé.",
        )

    session = pub_service.verify_session(analysis_id=analysis_id, session_token=session_token)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Session invalide, expirée ou révoquée pour cette analyse.",
        )

    return session


def verify_csrf_and_origin(
    request: Request,
    x_csrf_token: Optional[str] = Header(default=None, alias="X-CSRF-Token"),
    session: Dict[str, Any] = Depends(get_authenticated_session),
    pub_service: PublicationService = Depends(get_publication_service),
) -> None:
    """Enforces CORS origin validation and double-submit / session-bound CSRF token."""
    origin = request.headers.get("origin")
    allowed = settings.cors_allowed_origins
    if origin and allowed and "*" not in allowed and origin not in allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Origine non autorisée.",
        )

    if not pub_service.verify_csrf(session, x_csrf_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Jeton CSRF manquant ou invalide.",
        )
