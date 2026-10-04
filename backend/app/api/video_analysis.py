from __future__ import annotations

import hashlib
import hmac
from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    UploadFile,
)
from fastapi.responses import FileResponse

from app.core.config import Settings, settings
from app.video_analysis.backends import diagnose_video_backend
from app.video_analysis.canonical_modes import check_environment_preflight
from app.video_analysis.schemas import (
    AnalysisCreated,
    AnalysisJob,
    AnalysisResult,
    ArtifactInfo,
    ArtifactList,
)
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.video_analysis.service import VideoAnalysisService

from app.video_analysis.validation import VideoValidationError

router = APIRouter(prefix="/api/video-analysis", tags=["video-analysis"])

_service: Any = None


def get_video_analysis_service():
    global _service
    if _service is None:
        from app.video_analysis.service import VideoAnalysisService

        _service = VideoAnalysisService(settings)
    return _service


DEMO_ANALYSIS_IDS = {
    "SNMOT-068",
    "SNMOT-069",
    "DEMO_SNMOT068",
    "DEMO_SNMOT069",
    "DEMO-068",
    "DEMO-069",
    "GOLDEN-01-BROADCAST",
}


def is_demo_analysis(analysis_id: str) -> bool:
    """Checks whether an analysis ID refers to an immutable public demo sequence."""
    return analysis_id.strip().upper() in DEMO_ANALYSIS_IDS


def verify_analysis_access(
    analysis_id: str,
    authorization: str | None = Header(default=None),
    x_analysis_token: str | None = Header(default=None),
    token: str | None = Query(default=None),
    service: VideoAnalysisService = Depends(get_video_analysis_service),
) -> AnalysisJob | None:
    """Enforces capability-based authorization for video analyses.

    Public demo sequences are accessible without credentials.
    Real uploaded analyses require the matching bearer token or header.
    """
    if is_demo_analysis(analysis_id):
        return None

    try:
        job = service.storage.load_job(analysis_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Analyse introuvable.") from exc

    if job is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable.")

    if not settings.REQUIRE_ANALYSIS_TOKEN:
        return job

    if job.access_token_hash:
        provided = None
        if authorization and authorization.lower().startswith("bearer "):
            provided = authorization[7:].strip()
        elif x_analysis_token:
            provided = x_analysis_token.strip()
        elif token:
            provided = token.strip()

        if not provided:
            raise HTTPException(
                status_code=401,
                detail="Accès refusé : token d'autorisation requis pour cette analyse.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        candidate_hash = hashlib.sha256(provided.encode("utf-8")).hexdigest()
        if not hmac.compare_digest(candidate_hash, job.access_token_hash):
            raise HTTPException(
                status_code=403,
                detail="Accès interdit : token d'autorisation invalide pour cette analyse.",
            )

    return job


@router.get("/diagnostics/backend")
def video_backend_diagnostics() -> dict:
    if settings.APP_ENV == "production":
        raise HTTPException(
            status_code=404,
            detail="Diagnostics internes désactivés en environnement de production.",
        )
    return diagnose_video_backend().__dict__


def get_analysis_settings() -> Settings:
    return settings


def verify_public_upload_allowed(
    current_settings: Settings = Depends(get_analysis_settings),
) -> None:
    if current_settings.APP_ENV == "production" or not current_settings.PUBLIC_UPLOAD_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Public video upload and GPU analysis are disabled on this deployment. Submit a request via /beta.",
        )


@router.post(
    "",
    response_model=AnalysisCreated,
    status_code=202,
    dependencies=[Depends(verify_public_upload_allowed)],
)
async def create_analysis(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    match_id: str | None = Form(default=None),
    mode: str = Form(default="QUALITY"),
    service: VideoAnalysisService = Depends(get_video_analysis_service),
) -> AnalysisCreated:
    mode_upper = mode.strip().upper()
    if mode_upper not in ("QUALITY", "LOW_LATENCY"):
        raise HTTPException(
            status_code=422,
            detail=f"Mode inconnu '{mode}'. Modes autorisés : 'QUALITY', 'LOW_LATENCY'.",
        )
    try:
        check_environment_preflight(mode_upper)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Erreur de prévol environnement : {exc}"
        ) from exc

    try:
        created = await service.create(video, match_id=match_id, mode=mode_upper)
    except VideoValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not created.reused:
        background_tasks.add_task(service.process, created.analysis_id)
    return created


@router.get("/{analysis_id}", response_model=AnalysisJob)
def get_analysis(
    analysis_id: str,
    service: VideoAnalysisService = Depends(get_video_analysis_service),
    _access: AnalysisJob | None = Depends(verify_analysis_access),
) -> AnalysisJob:
    if _access is not None:
        return _access
    try:
        job = service.storage.load_job(analysis_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Analyse introuvable.") from exc
    if job is None:
        raise HTTPException(status_code=404, detail="Analyse introuvable.")
    return job


@router.get("/{analysis_id}/detections", response_model=AnalysisResult)
def get_detections(
    analysis_id: str,
    service: VideoAnalysisService = Depends(get_video_analysis_service),
    _access: AnalysisJob | None = Depends(verify_analysis_access),
) -> AnalysisResult:
    try:
        result = service.storage.load_result(analysis_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Résultats introuvables.") from exc
    if result is None:
        raise HTTPException(
            status_code=409, detail="Les détections ne sont pas encore disponibles."
        )
    return result


@router.get("/{analysis_id}/artifacts", response_model=ArtifactList)
def list_artifacts(
    analysis_id: str,
    service: VideoAnalysisService = Depends(get_video_analysis_service),
    _access: AnalysisJob | None = Depends(verify_analysis_access),
) -> ArtifactList:
    job = _access or get_analysis(analysis_id, service, _access)
    mapping = {
        "annotated_video": ("video/mp4", job.artifacts.annotated_video),
        "detections_json": ("application/json", job.artifacts.detections_json),
        "preview_image": ("image/jpeg", job.artifacts.preview_image),
    }
    return ArtifactList(
        analysis_id=analysis_id,
        artifacts=[
            ArtifactInfo(name=name, media_type=media_type, url=url)
            for name, (media_type, url) in mapping.items()
            if url
        ],
    )


@router.get("/{analysis_id}/artifacts/{artifact_name}", include_in_schema=False)
def download_artifact(
    analysis_id: str,
    artifact_name: str,
    service: VideoAnalysisService = Depends(get_video_analysis_service),
    _access: AnalysisJob | None = Depends(verify_analysis_access),
) -> FileResponse:
    filenames = {
        "annotated_video": ("annotated.mp4", "video/mp4"),
        "detections_json": ("detections.json", "application/json"),
        "preview_image": ("preview.jpg", "image/jpeg"),
    }
    if artifact_name not in filenames:
        raise HTTPException(status_code=404, detail="Artefact inconnu.")
    filename, media_type = filenames[artifact_name]
    try:
        session_dir = service.storage.analysis_dir(analysis_id)
        path = (session_dir / filename).resolve()
        if not str(path).startswith(str(session_dir.resolve())):
            raise HTTPException(status_code=403, detail="Accès interdit.")
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Artefact introuvable.") from exc
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artefact introuvable.")
    return FileResponse(
        path=Path(path),
        media_type=media_type,
        filename=filename,
        content_disposition_type=(
            "inline" if artifact_name == "annotated_video" else "attachment"
        ),
    )


# ==============================================================================
# GROUNDED MULTIMODAL TACTICAL RAG & REPORT ENDPOINTS (EXP-26 / Chapter 8)
# ==============================================================================

from app.schemas.grounded_rag import (
    GroundedMatchAnswer,
    MatchReportResponse,
    VideoAnalysisQueryRequest,
)
from app.services.grounded_rag_service import GroundedTacticalRAGService
from app.services.match_evidence_store import MatchEvidenceRegistry
from app.services.match_report_generator import MatchReportGenerator

_report_generator = MatchReportGenerator()


def get_grounded_rag_service() -> GroundedTacticalRAGService:
    try:
        from app.main import rag_engine
    except ImportError:
        rag_engine = None
    return GroundedTacticalRAGService(
        rag_engine=rag_engine,
        openai_api_key=settings.OPENAI_API_KEY,
        openrouter_api_key=settings.openrouter_key,
    )


@router.post("/{analysis_id}/query", response_model=GroundedMatchAnswer)
def query_video_analysis(
    analysis_id: str,
    payload: VideoAnalysisQueryRequest,
    rag_service: GroundedTacticalRAGService = Depends(get_grounded_rag_service),
    _access: AnalysisJob | None = Depends(verify_analysis_access),
) -> GroundedMatchAnswer:
    """Interroge les évidences tactiques validées de la vidéo analysée avec ancrage strict."""
    try:
        return rag_service.query(
            query_text=payload.query,
            analysis_id=analysis_id,
            max_evidence_events=payload.max_evidence_events,
            include_knowledge_base=payload.include_knowledge_base,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur d'interrogation vidéo : {exc}") from exc


def _resolve_evidence_dir(analysis_id: str, service: VideoAnalysisService) -> Path:
    if is_demo_analysis(analysis_id):
        return Path("docs/experiments/exp25_outputs")

    try:
        session_dir = service.storage.analysis_dir(analysis_id)
        if (session_dir / "tactical_events.json").is_file():
            return session_dir
    except Exception:
        pass

    # FAIL CLOSED: Never fallback to demo data for a real uploaded analysis!
    raise HTTPException(
        status_code=404,
        detail=f"Les preuves tactiques ne sont pas disponibles pour l'analyse '{analysis_id}'. "
               f"Le traitement est peut-être encore en cours ou a échoué.",
    )


@router.get("/{analysis_id}/timeline")
def get_video_analysis_timeline(
    analysis_id: str,
    service: VideoAnalysisService = Depends(get_video_analysis_service),
    _access: AnalysisJob | None = Depends(verify_analysis_access),
) -> list:
    """Renvoie la chronologie ordonnée des événements tactiques de la vidéo."""
    ev_dir = _resolve_evidence_dir(analysis_id, service)
    store = MatchEvidenceRegistry.get_or_load(analysis_id, evidence_dir=ev_dir)
    if not store.is_loaded or not store.timeline:
        raise HTTPException(status_code=404, detail="Chronologie introuvable pour cette analyse.")
    return [e.model_dump() if hasattr(e, "model_dump") else e.__dict__ for e in store.timeline]


@router.get("/{analysis_id}/events")
def get_video_analysis_events(
    analysis_id: str,
    service: VideoAnalysisService = Depends(get_video_analysis_service),
    _access: AnalysisJob | None = Depends(verify_analysis_access),
) -> list:
    """Renvoie l'index complet des événements probants de la vidéo."""
    ev_dir = _resolve_evidence_dir(analysis_id, service)
    store = MatchEvidenceRegistry.get_or_load(analysis_id, evidence_dir=ev_dir)
    if not store.is_loaded or not store.events_by_id:
        raise HTTPException(status_code=404, detail="Événements introuvables pour cette analyse.")
    return [e.model_dump() if hasattr(e, "model_dump") else e.__dict__ for e in store.events_by_id.values()]


@router.get("/{analysis_id}/summary")
def get_video_analysis_summary(
    analysis_id: str,
    service: VideoAnalysisService = Depends(get_video_analysis_service),
    _access: AnalysisJob | None = Depends(verify_analysis_access),
) -> dict:
    """Renvoie les agrégats tactiques et bandes de fiabilité par équipe."""
    ev_dir = _resolve_evidence_dir(analysis_id, service)
    store = MatchEvidenceRegistry.get_or_load(analysis_id, evidence_dir=ev_dir)
    if not store.is_loaded or not store.team_summaries:
        raise HTTPException(status_code=404, detail="Résumé tactique introuvable pour cette analyse.")
    return store.team_summaries


@router.get("/{analysis_id}/report", response_model=MatchReportResponse)
@router.post("/{analysis_id}/report", response_model=MatchReportResponse)
def generate_video_analysis_report(
    analysis_id: str,
    service: VideoAnalysisService = Depends(get_video_analysis_service),
    _access: AnalysisJob | None = Depends(verify_analysis_access),
) -> MatchReportResponse:
    """Génère le rapport d'intelligence tactique 100% ancré pour la vidéo."""
    try:
        ev_dir = _resolve_evidence_dir(analysis_id, service)
        generator = MatchReportGenerator(evidence_dir=ev_dir)
        return generator.generate_report(analysis_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur de génération du rapport : {exc}") from exc

