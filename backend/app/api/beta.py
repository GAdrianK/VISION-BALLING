from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.schemas.beta import (
    BetaAnalysisRequestCreate,
    BetaAnalysisRequestResponse,
)
from app.services.beta_service import BetaService, get_beta_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/beta-requests", tags=["beta-requests"])


def get_client_ip(request: Request) -> str:
    """Extracts client IP safely, considering X-Forwarded-For if available."""
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        # First IP in the list is the client IP
        ip = forwarded_for.split(",")[0].strip()
        if ip:
            return ip
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


@router.post(
    "",
    response_model=BetaAnalysisRequestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a public beta match analysis request",
)
async def submit_beta_request(
    request: Request,
    payload: BetaAnalysisRequestCreate,
    service: BetaService = Depends(get_beta_service),
) -> BetaAnalysisRequestResponse:
    # 1. Anti-bot honeypot check
    if payload.honeypot and payload.honeypot.strip():
        logger.warning("Beta request rejected by honeypot trigger.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Requête invalide.",
        )

    # 2. Rate limit check
    client_ip = get_client_ip(request)
    if not service.rate_limiter.is_allowed(client_ip):
        logger.warning("Beta request rate limit exceeded for ip=%s", client_ip)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trop de demandes envoyées. Veuillez patienter quelques minutes.",
        )

    # 3. Create request
    try:
        response = service.create_request(payload, client_ip=client_ip)
        return response
    except ValueError as e:
        logger.warning("Validation error in beta request: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e),
        )
    except Exception as e:
        logger.exception("Unexpected error saving beta request: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Impossible d'enregistrer la demande pour le moment.",
        )
