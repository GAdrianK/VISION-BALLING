from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class TrackingState(str, Enum):
    NEW = "NEW"
    CONFIRMED = "CONFIRMED"
    LOST = "LOST"
    REMOVED = "REMOVED"


class BallObservationState(str, Enum):
    DETECTED = "DETECTED"
    PREDICTED = "PREDICTED"
    INTERPOLATED = "INTERPOLATED"
    LOST = "LOST"


@dataclass(frozen=True)
class PlayerTrackObservation:
    """Unified common schema for a player track observation at a specific frame."""

    track_id: int
    frame_index: int
    timestamp: float
    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2)
    confidence: float
    class_id: int = 1
    class_name: str = "person"
    source_detector: str = "rf-detr-small"
    tracking_state: TrackingState = TrackingState.CONFIRMED

    def to_dict(self) -> dict[str, Any]:
        return {
            "track_id": self.track_id,
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
            "bbox": list(self.bbox),
            "confidence": self.confidence,
            "class_id": self.class_id,
            "class_name": self.class_name,
            "source_detector": self.source_detector,
            "tracking_state": self.tracking_state.value,
        }


class BallLifecycleState(str, Enum):
    ACTIVE = "ACTIVE"
    LOST = "LOST"
    TERMINATED = "TERMINATED"


@dataclass(frozen=True)
class BallTrackObservation:
    """Unified common schema for a ball track observation at a specific frame."""

    frame_index: int
    timestamp: float
    bbox: tuple[float, float, float, float]  # (x1, y1, x2, y2)
    position: tuple[float, float]  # (center_x, center_y)
    velocity: tuple[float, float] | None  # (vx, vy) in pixels/frame
    observation_state: BallObservationState
    gap_length: int = 0
    confidence: float | None = None
    source_detector: str | None = None
    source_frame_detections: tuple[int, ...] = ()
    track_id: int | None = None
    lifecycle_state: BallLifecycleState = BallLifecycleState.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "timestamp": self.timestamp,
            "bbox": list(self.bbox),
            "position": {"x": self.position[0], "y": self.position[1]},
            "velocity": {"vx": self.velocity[0], "vy": self.velocity[1]}
            if self.velocity
            else None,
            "observation_state": self.observation_state.value,
            "gap_length": self.gap_length,
            "confidence": self.confidence,
            "source_detector": self.source_detector,
            "source_frame_detections": list(self.source_frame_detections),
            "track_id": self.track_id,
            "lifecycle_state": self.lifecycle_state.value,
        }
