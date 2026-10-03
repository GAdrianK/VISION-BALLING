from __future__ import annotations

from pathlib import Path

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi.responses import FileResponse

from app.core.config import settings
from app.video_analysis.backends import diagnose_video_backend
from app.video_analysis.schemas import (
    AnalysisCreated,
    AnalysisJob,
    AnalysisResult,
    ArtifactInfo,
    ArtifactList,
)
from app.video_analysis.service import VideoAnalysisService
from app.video_analysis.validation import VideoValidationError

router = APIRouter(prefix="/api/video-analysis", tags=["video-analysis"])


@router.get("/diagnostics/backend")
def video_backend_diagnostics() -> dict:
    return diagnose_video_backend().__dict__


_service = VideoAnalysisService(settings)


def get_video_analysis_service() -> VideoAnalysisService:
    return _service


@router.post("", response_model=AnalysisCreated, status_code=202)
async def create_analysis(
    background_tasks: BackgroundTasks,
    video: UploadFile = File(...),
    match_id: str | None = Form(default=None),
    service: VideoAnalysisService = Depends(get_video_analysis_service),
) -> AnalysisCreated:
    try:
        created = await service.create(video, match_id)
    except VideoValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if not created.reused:
        background_tasks.add_task(service.process, created.analysis_id)
    return created


@router.get("/{analysis_id}", response_model=AnalysisJob)
def get_analysis(
    analysis_id: str,
    service: VideoAnalysisService = Depends(get_video_analysis_service),
) -> AnalysisJob:
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
) -> ArtifactList:
    job = get_analysis(analysis_id, service)
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
        path = service.storage.analysis_dir(analysis_id) / filename
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


@router.get("/{analysis_id}/timeline")
def get_video_analysis_timeline(analysis_id: str) -> list:
    """Renvoie la chronologie ordonnée des événements tactiques de la vidéo."""
    store = MatchEvidenceRegistry.get_or_load(analysis_id)
    if not store.is_loaded or not store.timeline:
        raise HTTPException(status_code=404, detail="Chronologie introuvable pour cette analyse.")
    return [e.model_dump() if hasattr(e, "model_dump") else e.__dict__ for e in store.timeline]


@router.get("/{analysis_id}/events")
def get_video_analysis_events(analysis_id: str) -> list:
    """Renvoie l'index complet des événements probants de la vidéo."""
    store = MatchEvidenceRegistry.get_or_load(analysis_id)
    if not store.is_loaded or not store.events_by_id:
        raise HTTPException(status_code=404, detail="Événements introuvables pour cette analyse.")
    return [e.model_dump() if hasattr(e, "model_dump") else e.__dict__ for e in store.events_by_id.values()]


@router.get("/{analysis_id}/summary")
def get_video_analysis_summary(analysis_id: str) -> dict:
    """Renvoie les agrégats tactiques et bandes de fiabilité par équipe."""
    store = MatchEvidenceRegistry.get_or_load(analysis_id)
    if not store.is_loaded or not store.team_summaries:
        raise HTTPException(status_code=404, detail="Résumé tactique introuvable pour cette analyse.")
    return store.team_summaries


@router.post("/{analysis_id}/report", response_model=MatchReportResponse)
def generate_video_analysis_report(analysis_id: str) -> MatchReportResponse:
    """Génère le rapport d'intelligence tactique 100% ancré pour la vidéo."""
    try:
        return _report_generator.generate_report(analysis_id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Erreur de génération du rapport : {exc}") from exc
