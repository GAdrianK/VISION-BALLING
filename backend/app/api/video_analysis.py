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
    return FileResponse(path=Path(path), media_type=media_type, filename=filename)
