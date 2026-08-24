from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.1.0"
PIPELINE_VERSION = "0.2.0"


class JobStatus(str, Enum):
    QUEUED = "queued"
    VALIDATING = "validating"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class BoundingBox(BaseModel):
    x1: int = Field(ge=0)
    y1: int = Field(ge=0)
    x2: int = Field(ge=0)
    y2: int = Field(ge=0)


class Detection(BaseModel):
    frame_index: int = Field(ge=0)
    timestamp_seconds: float = Field(ge=0)
    class_name: str
    football_role: Literal[
        "unknown_player",
        "player_candidate",
        "ball",
        "ball_candidate",
        "referee",
        "unknown",
    ] = "unknown"
    confidence: float = Field(ge=0, le=1)
    bbox: BoundingBox
    track_id: int | None = None
    tracker_name: str | None = None
    model_id: str
    center: dict[str, float] | None = None


class VideoMetadata(BaseModel):
    filename: str
    duration_seconds: float = Field(gt=0)
    fps: float = Field(gt=0)
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    frame_count: int = Field(gt=0)
    container: str | None = None
    codec: str | None = None


class PipelineMetadata(BaseModel):
    version: str = PIPELINE_VERSION
    detector: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    frame_interval: int = Field(ge=1)
    device: str
    detector_name: str | None = None
    detector_version: str | None = None
    tracker_name: str = "none"
    tracker_version: str | None = None
    tracking_enabled: bool = False
    ffmpeg_version: str | None = None
    video_backend: str = "opencv"
    frame_sample_rate: int | None = None


class ArtifactSet(BaseModel):
    annotated_video: str | None = None
    detections_json: str | None = None
    preview_image: str | None = None


class BallTrajectoryPoint(BaseModel):
    frame_index: int = Field(ge=0)
    timestamp_seconds: float = Field(ge=0)
    state: Literal["observed", "predicted"]
    class_name: Literal["sports ball"] = "sports ball"
    confidence: float | None = Field(default=None, ge=0, le=1)
    bbox: BoundingBox
    center: dict[str, float]


class AnalysisResult(BaseModel):
    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    match_id: str
    status: JobStatus
    video: VideoMetadata
    pipeline: PipelineMetadata
    detections: list[Detection] = Field(default_factory=list)
    ball_trajectory: list[BallTrajectoryPoint] = Field(default_factory=list)
    artifacts: ArtifactSet = Field(default_factory=ArtifactSet)
    warnings: list[str] = Field(default_factory=list)
    frames_analyzed: int = 0
    processing_duration_seconds: float = 0
    average_processing_fps: float = 0
    class_summary: dict[str, int | float] = Field(default_factory=dict)
    tracking_summary: dict[str, int | float] = Field(default_factory=dict)


class JobError(BaseModel):
    code: str
    message: str


class AnalysisJob(BaseModel):
    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    match_id: str
    status: JobStatus = JobStatus.QUEUED
    progress_percent: float = Field(default=0, ge=0, le=100)
    current_step: str = "queued"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_sha256: str | None = None
    error: JobError | None = None
    artifacts: ArtifactSet = Field(default_factory=ArtifactSet)
    warnings: list[str] = Field(default_factory=list)
    result_available: bool = False


class AnalysisCreated(BaseModel):
    analysis_id: str
    match_id: str
    status: JobStatus
    reused: bool = False


class ArtifactInfo(BaseModel):
    name: str
    url: str
    media_type: str


class ArtifactList(BaseModel):
    analysis_id: str
    artifacts: list[ArtifactInfo]
