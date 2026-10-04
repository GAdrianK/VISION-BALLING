from __future__ import annotations

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

ALLOWED_ARTIFACT_NAMES = {
    "tactical_events.json",
    "match_timeline.jsonl",
    "team_summary.json",
    "event_graph.json",
    "match_report.md",
    "runtime.json",
    "annotated.mp4",
}


class ArtifactInfoItem(BaseModel):
    """Metadata describing a published analysis artifact."""
    name: str
    sha256: str = Field(..., min_length=64, max_length=64)
    size_bytes: int = Field(..., ge=0)
    media_type: str
    s3_key: Optional[str] = None


class PublicationManifest(BaseModel):
    """Canonical manifest describing an analysis release."""
    schema_version: str = "1.0"
    analysis_id: str
    version_id: str = "v1"
    match_id: str
    request_id: Optional[str] = None
    created_at_utc: str
    video_duration_seconds: float = Field(..., ge=0)
    fps: float = Field(..., ge=0)
    frame_count: int = Field(..., ge=0)
    artifacts: Dict[str, ArtifactInfoItem]
    sanitized_runtime: Dict[str, Any] = Field(default_factory=dict)


class PublishInitiateRequest(BaseModel):
    """Payload sent by the operator GPU workstation to initiate publication staging."""
    analysis_id: str
    request_id: Optional[str] = None
    version_id: str = "v1"
    manifest: PublicationManifest


class PublishInitiateResponse(BaseModel):
    """Returned to operator with fencing token and presigned upload targets."""
    analysis_id: str
    version_id: str
    finalization_id: str
    fencing_token: int
    upload_targets: Dict[str, str] = Field(default_factory=dict)


class PublishFinalizeRequest(BaseModel):
    """Payload sent to finalize and promote staged artifacts to active publication."""
    analysis_id: str
    version_id: str
    finalization_id: str
    fencing_token: int
    recipient_email: Optional[str] = None
    coach_name: Optional[str] = None
    match_name: Optional[str] = None
    notify: bool = False


class PublishFinalizeResponse(BaseModel):
    """Returned upon successful publication promotion and capability generation."""
    analysis_id: str
    version_id: str
    status: str = "PUBLISHED"
    published_at: str
    capability_token: str
    access_url: str
    notification_queued: bool = False


class AnalysisRevokeRequest(BaseModel):
    """Payload to revoke access to an existing publication."""
    reason: Optional[str] = "Operator revocation"
