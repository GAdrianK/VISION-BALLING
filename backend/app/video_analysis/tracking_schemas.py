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


@dataclass(frozen=True)
class FrameTrackingRuntime:
    """Detailed per-stage runtime breakdown for a single processed frame in milliseconds."""

    decode_ms: float = 0.0
    preprocess_ms: float = 0.0
    detector_inference_ms: float = 0.0
    detector_postprocess_ms: float = 0.0
    detector_ms: float = 0.0
    gmc_ms: float = 0.0
    player_tracking_ms: float = 0.0
    ball_tracking_ms: float = 0.0
    rendering_ms: float = 0.0
    encoding_ms: float = 0.0
    output_ms: float = 0.0
    total_ms: float = 0.0

    def to_dict(self) -> dict[str, float]:
        return {
            "decode_ms": round(self.decode_ms, 3),
            "preprocess_ms": round(self.preprocess_ms, 3),
            "detector_inference_ms": round(self.detector_inference_ms, 3),
            "detector_postprocess_ms": round(self.detector_postprocess_ms, 3),
            "detector_ms": round(self.detector_ms, 3),
            "gmc_ms": round(self.gmc_ms, 3),
            "player_tracking_ms": round(self.player_tracking_ms, 3),
            "ball_tracking_ms": round(self.ball_tracking_ms, 3),
            "rendering_ms": round(self.rendering_ms, 3),
            "encoding_ms": round(self.encoding_ms, 3),
            "output_ms": round(self.output_ms, 3),
            "total_ms": round(self.total_ms, 3),
        }


@dataclass(frozen=True)
class FrameTrackingResult:
    """
    Unified common output contract for a single video frame.
    Strictly isolated: no team labels, jersey numbers, pitch coordinates, or actions.
    """

    frame_index: int
    timestamp: float
    players: list[PlayerTrackObservation]
    ball: BallTrackObservation | None
    runtime: FrameTrackingRuntime

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "timestamp": round(self.timestamp, 6),
            "players": [
                {
                    "track_id": p.track_id,
                    "bbox": list(p.bbox),
                    "confidence": round(p.confidence, 4),
                    "tracking_state": p.tracking_state.value,
                }
                for p in self.players
            ],
            "ball": {
                "track_id": self.ball.track_id,
                "bbox": list(self.ball.bbox),
                "center": {"x": round(self.ball.position[0], 2), "y": round(self.ball.position[1], 2)},
                "confidence": round(self.ball.confidence, 4) if self.ball.confidence is not None else None,
                "observation_state": self.ball.observation_state.value,
                "velocity": {
                    "vx": round(self.ball.velocity[0], 2),
                    "vy": round(self.ball.velocity[1], 2),
                }
                if self.ball.velocity
                else None,
            }
            if self.ball is not None
            else None,
            "runtime": self.runtime.to_dict(),
        }
