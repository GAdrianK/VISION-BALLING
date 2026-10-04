from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from app.video_analysis.schemas import (
    ArtifactSet,
    JobError,
    JobStatus,
    PipelineMetadata,
    SCHEMA_VERSION,
)


class AccessExchangeRequest(BaseModel):
    """Payload to exchange a single-use or scoped capability token for a session cookie."""
    capability_token: str = Field(
        ...,
        min_length=16,
        max_length=128,
        description="Private capability token extracted from URL fragment #access=...",
    )


class AccessExchangeResponse(BaseModel):
    """Response returned upon successful capability token exchange."""
    analysis_id: str
    csrf_token: str
    expires_in_seconds: int
    session_expires_at: str


class VideoStreamUrlResponse(BaseModel):
    """Response containing an ephemeral presigned streaming URL for video playback."""
    analysis_id: str
    stream_url: str
    expires_in_seconds: int = 300
    video_retention_expires_at: Optional[str] = None


class AnalysisJobCoachDTO(BaseModel):
    """Sanitized public DTO for coach / portal consumption.
    
    Strictly omits access_token_hash, access_token_hashes, source_sha256,
    and internal analysis_key.
    """
    schema_version: str = SCHEMA_VERSION
    analysis_id: str
    match_id: str
    status: JobStatus = JobStatus.QUEUED
    mode: str = "QUALITY"
    analysis_source: str = "REAL_UPLOAD"
    evidence_origin: str = "REAL_VIDEO_PIPELINE"
    progress_percent: float = Field(default=0, ge=0, le=100)
    current_step: str = "queued"
    created_at: datetime
    updated_at: datetime
    pipeline: Optional[PipelineMetadata] = None
    error: Optional[JobError] = None
    artifacts: ArtifactSet = Field(default_factory=ArtifactSet)
    warnings: List[str] = Field(default_factory=list)
    result_available: bool = False
