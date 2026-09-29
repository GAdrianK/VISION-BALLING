from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from app.video_analysis.detectors import RawDetection
from app.video_analysis.tracking_schemas import PlayerTrackObservation, TrackingState


@dataclass(frozen=True)
class ByteTrackConfig:
    """Explicit, frozen configuration for Player ByteTrack baseline."""

    track_activation_threshold: float = 0.45  # Matches locked canonical person threshold
    low_confidence_threshold: float = 0.10    # Low-confidence threshold for ByteTrack 2nd stage association
    lost_track_buffer: int = 30               # Retain lost tracks for ~1s at 30 fps (or 25 frames at 25 fps)
    minimum_matching_threshold: float = 0.8   # Standard ByteTrack IoU association threshold
    frame_rate: float = 30.0                  # FPS of input sequence
    minimum_consecutive_frames: int = 1       # Confirmation age in consecutive frames
    version: str = "1.1.0"


def filter_detections_for_tracking(
    detections: list[RawDetection],
    *,
    person_min_confidence: float = 0.10,
    ball_min_confidence: float = 0.25,
) -> list[RawDetection]:
    """
    Tracking-specific detection adapter:
    - Exposes person detections with confidence > 0.10 for ByteTrack's 2-stage association.
    - Exposes ball detections with confidence >= 0.25 for BallTrackManager.
    """
    return [
        d
        for d in detections
        if (d.class_name == "person" and d.confidence > person_min_confidence)
        or (d.class_name in ("sports ball", "ball") and d.confidence >= ball_min_confidence)
    ]


class PlayerByteTrack:
    """
    Player tracking baseline using ByteTrack on person detections.
    Treats player tracking strictly independently from ball tracking.
    Preserves original detector confidence values and maintains persistent IDs across occlusions.
    """

    def __init__(self, config: ByteTrackConfig | None = None) -> None:
        self.config = config or ByteTrackConfig()
        try:
            import supervision as sv
        except ImportError as exc:
            raise RuntimeError(
                "Le tracker bytetrack exige le paquet supervision. "
                "Installez backend/requirements-video.txt."
            ) from exc

        self._sv = sv
        self._supervision_version = getattr(sv, "__version__", "unknown")
        self.reset()

    def reset(self) -> None:
        """Resets tracker internal state and track ID counter."""
        self._tracker = self._sv.ByteTrack(
            track_activation_threshold=self.config.track_activation_threshold,
            lost_track_buffer=self.config.lost_track_buffer,
            minimum_matching_threshold=self.config.minimum_matching_threshold,
            frame_rate=self.config.frame_rate,
            minimum_consecutive_frames=self.config.minimum_consecutive_frames,
        )

    def update_tracks(
        self,
        frame_index: int,
        timestamp: float,
        detections: list[RawDetection],
        source_detector: str = "rf-detr-small",
    ) -> list[PlayerTrackObservation]:
        """
        Updates player tracks from raw detections.
        Filters strictly for class_name == 'person' and confidence > low_confidence_threshold.
        Preserves original detector confidences.
        """
        person_indices = [
            i
            for i, d in enumerate(detections)
            if d.class_name == "person" and d.confidence > self.config.low_confidence_threshold
        ]
        if not person_indices:
            # Still invoke tracker with empty detections to advance lost-track buffers
            empty_sv = self._sv.Detections.empty()
            self._tracker.update_with_detections(empty_sv)
            return []


        boxes = np.array([detections[i].bbox for i in person_indices], dtype=float)
        confs = np.array([detections[i].confidence for i in person_indices], dtype=float)
        class_ids = np.ones(len(person_indices), dtype=int)

        sv_detections = self._sv.Detections(
            xyxy=boxes,
            confidence=confs,
            class_id=class_ids,
            data={"source_index": np.array(person_indices)},
        )

        tracked = self._tracker.update_with_detections(sv_detections)
        tracker_ids = tracked.tracker_id if tracked.tracker_id is not None else []
        source_indices = tracked.data.get("source_index", [])

        observations: list[PlayerTrackObservation] = []
        for source_idx, track_id in zip(source_indices, tracker_ids):
            idx = int(source_idx)
            raw = detections[idx]
            obs = PlayerTrackObservation(
                track_id=int(track_id),
                frame_index=frame_index,
                timestamp=timestamp,
                bbox=(float(raw.bbox[0]), float(raw.bbox[1]), float(raw.bbox[2]), float(raw.bbox[3])),
                confidence=float(raw.confidence),
                class_id=1,
                class_name="person",
                source_detector=source_detector,
                tracking_state=TrackingState.CONFIRMED,
            )
            observations.append(obs)

        return observations

    def metadata(self) -> dict[str, Any]:
        """Returns complete, frozen provenance and parameters."""
        data = asdict(self.config)
        data.update({
            "name": "bytetrack_player",
            "supervision_version": self._supervision_version,
            "target_class": "person",
        })
        return data
