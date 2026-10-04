from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.auth_dependencies import verify_operator_token
from app.schemas.publication import (
    AnalysisRevokeRequest,
    PublishFinalizeRequest,
    PublishFinalizeResponse,
    PublishInitiateRequest,
    PublishInitiateResponse,
)
from app.services.publication_service import PublicationService, get_publication_service

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/internal/publications",
    tags=["Operator Publications"],
    dependencies=[Depends(verify_operator_token)],
)


@router.post("/initiate", response_model=PublishInitiateResponse)
def initiate_publication(
    payload: PublishInitiateRequest,
    pub_service: PublicationService = Depends(get_publication_service),
) -> PublishInitiateResponse:
    """Initiates an analysis publication attempt, returns upload targets and fencing token."""
    try:
        return pub_service.initiate_publication(
            analysis_id=payload.analysis_id,
            manifest=payload.manifest,
            request_id=payload.request_id,
            version_id=payload.version_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to initiate publication for '%s'", payload.analysis_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur d'initiation de la publication : {exc}",
        ) from exc


@router.post("/finalize", response_model=PublishFinalizeResponse)
def finalize_publication(
    payload: PublishFinalizeRequest,
    pub_service: PublicationService = Depends(get_publication_service),
) -> PublishFinalizeResponse:
    """Promotes staged artifacts to active publication and creates capability token."""
    try:
        return pub_service.finalize_publication(
            analysis_id=payload.analysis_id,
            version_id=payload.version_id,
            finalization_id=payload.finalization_id,
            fencing_token=payload.fencing_token,
            recipient_email=payload.recipient_email,
            coach_name=payload.coach_name,
            match_name=payload.match_name,
            notify=payload.notify,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to finalize publication for '%s'", payload.analysis_id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de finalisation de la publication : {exc}",
        ) from exc


@router.get("/{analysis_id}")
def get_publication(
    analysis_id: str,
    pub_service: PublicationService = Depends(get_publication_service),
) -> Dict[str, Any]:
    """Retrieves publication status and artifacts metadata for operator inspection."""
    pub = pub_service.get_publication(analysis_id)
    if not pub:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Publication introuvable pour '{analysis_id}'.",
        )
    return pub


@router.post("/{analysis_id}/revoke")
def revoke_publication(
    analysis_id: str,
    payload: AnalysisRevokeRequest,
    pub_service: PublicationService = Depends(get_publication_service),
) -> Dict[str, Any]:
    """Revokes active publication and invalidates all associated coach access grants and sessions."""
    success = pub_service.revoke_publication(analysis_id=analysis_id, reason=payload.reason or "Revocation")
    return {"analysis_id": analysis_id, "status": "REVOKED", "revoked": success}
