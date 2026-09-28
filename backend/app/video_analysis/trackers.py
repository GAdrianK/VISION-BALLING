from __future__ import annotations

from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from math import ceil, hypot, isfinite, sqrt
from typing import Any, Literal

import numpy as np

from app.video_analysis.detectors import RawDetection

TEMPORAL_FRAME_CONVERSION_RULE = "ceil(seconds * source_fps)"


@dataclass(frozen=True)
class TrackedDetection:
    detection: RawDetection
    track_id: int | None


@dataclass(frozen=True)
class BallTrackPosition:
    frame_index: int
    bbox: tuple[int, int, int, int]
    center: tuple[float, float]
    state: Literal["observed", "predicted"]
    confidence: float | None
    class_name: Literal["sports ball"] = "sports ball"


@dataclass(frozen=True)
class BallTrackerTiming:
    source_fps: float
    max_missing_seconds: float
    max_missing_frames_effective: int
    trajectory_seconds: float
    trajectory_frames_effective: int
    conversion_rule: str = TEMPORAL_FRAME_CONVERSION_RULE


def seconds_to_source_frames(
    seconds: float, source_fps: float, *, minimum: int = 0
) -> int:
    if not isfinite(seconds) or seconds < 0:
        raise ValueError("seconds doit être fini et supérieur ou égal à 0.")
    if not isfinite(source_fps) or source_fps <= 0:
        raise ValueError("source_fps doit être fini et strictement positif.")
    if minimum < 0:
        raise ValueError("minimum doit être supérieur ou égal à 0.")
    return max(minimum, ceil(seconds * source_fps))


def resolve_ball_tracker_timing(
    *,
    max_missing_seconds: float,
    trajectory_seconds: float,
    source_fps: float,
) -> BallTrackerTiming:
    if trajectory_seconds <= 0:
        raise ValueError("trajectory_seconds doit être strictement positif.")
    return BallTrackerTiming(
        source_fps=source_fps,
        max_missing_seconds=max_missing_seconds,
        max_missing_frames_effective=seconds_to_source_frames(
            max_missing_seconds, source_fps
        ),
        trajectory_seconds=trajectory_seconds,
        trajectory_frames_effective=seconds_to_source_frames(
            trajectory_seconds, source_fps, minimum=1
        ),
    )


class BallTracker:
    """Suivi cinématique léger d'un unique ballon principal."""

    def __init__(
        self,
        max_missing_frames: int = 5,
        max_distance_ratio: float = 0.15,
        trajectory_length: int = 12,
    ) -> None:
        if max_missing_frames < 0:
            raise ValueError("max_missing_frames doit être supérieur ou égal à 0.")
        if trajectory_length < 1:
            raise ValueError("trajectory_length doit être supérieur ou égal à 1.")
        if not 0 < max_distance_ratio <= 1:
            raise ValueError(
                "max_distance_ratio doit être supérieur à 0 et inférieur ou égal à 1."
            )
        self.max_missing_frames = max_missing_frames
        self.max_distance_ratio = max_distance_ratio
        self.trajectory_length = trajectory_length
        self.reset()

    def reset(self) -> None:
        self._reset_count = 0
        self._clear_track()

    def _clear_track(self) -> None:
        self._previous_observed: BallTrackPosition | None = None
        self._last_observed: BallTrackPosition | None = None
        self._trajectory: deque[BallTrackPosition] = deque(
            maxlen=self.trajectory_length
        )

    def _reset_track(self) -> None:
        if self._last_observed is not None or self._trajectory:
            self._reset_count += 1
        self._clear_track()

    @property
    def trajectory(self) -> tuple[BallTrackPosition, ...]:
        return tuple(self._trajectory)

    @property
    def reset_count(self) -> int:
        return self._reset_count

    def update(
        self,
        frame_index: int,
        frame: np.ndarray,
        detections: list[RawDetection],
    ) -> BallTrackPosition | None:
        if not self._valid_frame_size(frame):
            self._reset_track()
            return None

        if self._last_observed is not None:
            missing_between = frame_index - self._last_observed.frame_index - 1
            if frame_index <= self._last_observed.frame_index or (
                missing_between > self.max_missing_frames
            ):
                self._reset_track()

        candidates = [
            detection
            for detection in detections
            if detection.class_name == "sports ball"
        ]
        if candidates:
            selected = self._select_candidate(frame_index, frame, candidates)
            if selected is None:
                self._reset_track()
                selected = max(candidates, key=lambda item: item.confidence)
            return self._record_observation(frame_index, selected)

        return self._predict(frame_index, frame)

    def _select_candidate(
        self,
        frame_index: int,
        frame: np.ndarray,
        candidates: list[RawDetection],
    ) -> RawDetection | None:
        if self._last_observed is None:
            return max(candidates, key=lambda item: item.confidence)

        expected_x, expected_y = self._expected_center(frame_index)
        height, width = frame.shape[:2]
        elapsed = max(1, frame_index - self._last_observed.frame_index)
        max_distance = max(
            1.0,
            hypot(width, height) * self.max_distance_ratio * sqrt(elapsed),
        )
        scored: list[tuple[float, float, float, RawDetection]] = []
        for candidate in candidates:
            center_x, center_y = self._bbox_center(candidate.bbox)
            distance = hypot(center_x - expected_x, center_y - expected_y)
            if distance > max_distance:
                continue
            proximity = 1.0 - distance / max_distance
            score = 0.7 * proximity + 0.3 * candidate.confidence
            scored.append((score, candidate.confidence, -distance, candidate))
        if not scored:
            return None
        return max(scored, key=lambda item: item[:3])[3]

    def _record_observation(
        self, frame_index: int, detection: RawDetection
    ) -> BallTrackPosition:
        position = BallTrackPosition(
            frame_index=frame_index,
            bbox=detection.bbox,
            center=self._bbox_center(detection.bbox),
            state="observed",
            confidence=detection.confidence,
        )
        self._previous_observed = self._last_observed
        self._last_observed = position
        self._trajectory.append(position)
        return position

    def _predict(
        self, frame_index: int, frame: np.ndarray
    ) -> BallTrackPosition | None:
        if self._last_observed is None:
            return None
        elapsed = frame_index - self._last_observed.frame_index
        if elapsed <= 0 or elapsed > self.max_missing_frames:
            self._reset_track()
            return None

        center = self._expected_center(frame_index)
        bbox = self._bbox_at_center(self._last_observed.bbox, center, frame.shape)
        position = BallTrackPosition(
            frame_index=frame_index,
            bbox=bbox,
            center=self._bbox_center(bbox),
            state="predicted",
            confidence=None,
        )
        self._trajectory.append(position)
        return position

    def _expected_center(self, frame_index: int) -> tuple[float, float]:
        assert self._last_observed is not None
        if self._previous_observed is None:
            return self._last_observed.center
        observed_delta = max(
            1,
            self._last_observed.frame_index - self._previous_observed.frame_index,
        )
        velocity_x = (
            self._last_observed.center[0] - self._previous_observed.center[0]
        ) / observed_delta
        velocity_y = (
            self._last_observed.center[1] - self._previous_observed.center[1]
        ) / observed_delta
        elapsed = frame_index - self._last_observed.frame_index
        return (
            self._last_observed.center[0] + velocity_x * elapsed,
            self._last_observed.center[1] + velocity_y * elapsed,
        )

    @staticmethod
    def _bbox_center(bbox: tuple[int, int, int, int]) -> tuple[float, float]:
        x1, y1, x2, y2 = bbox
        return ((x1 + x2) / 2, (y1 + y2) / 2)

    @staticmethod
    def _valid_frame_size(frame: np.ndarray) -> bool:
        return frame.ndim >= 2 and frame.shape[0] > 0 and frame.shape[1] > 0

    @staticmethod
    def _bbox_at_center(
        reference: tuple[int, int, int, int],
        center: tuple[float, float],
        frame_shape: tuple[int, ...],
    ) -> tuple[int, int, int, int]:
        frame_height, frame_width = frame_shape[:2]
        box_width = max(1, reference[2] - reference[0])
        box_height = max(1, reference[3] - reference[1])
        x1 = max(0, min(frame_width - 1, round(center[0] - box_width / 2)))
        y1 = max(0, min(frame_height - 1, round(center[1] - box_height / 2)))
        x2 = max(x1 + 1, min(frame_width, x1 + box_width))
        y2 = max(y1 + 1, min(frame_height, y1 + box_height))
        return (x1, y1, x2, y2)


class Tracker(ABC):
    @abstractmethod
    def reset(self) -> None: ...

    @abstractmethod
    def update(
        self, frame: np.ndarray, detections: list[RawDetection]
    ) -> list[TrackedDetection]: ...

    @abstractmethod
    def metadata(self) -> dict[str, Any]: ...


class DisabledTracker(Tracker):
    def reset(self) -> None:
        pass

    def update(
        self, frame: np.ndarray, detections: list[RawDetection]
    ) -> list[TrackedDetection]:
        return [TrackedDetection(item, None) for item in detections]

    def metadata(self) -> dict[str, Any]:
        return {"enabled": False, "name": "none", "version": "1"}


class IoUTracker(Tracker):
    """Tracker CPU minimal et déterministe, utile comme fallback sans dépendance."""

    def __init__(self, iou_threshold: float = 0.3, max_missed: int = 6) -> None:
        self.iou_threshold = iou_threshold
        self.max_missed = max_missed
        self.reset()

    def reset(self) -> None:
        self._next_id = 1
        self._tracks: dict[int, tuple[tuple[int, int, int, int], str, int]] = {}

    @staticmethod
    def _iou(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> float:
        x1, y1 = max(a[0], b[0]), max(a[1], b[1])
        x2, y2 = min(a[2], b[2]), min(a[3], b[3])
        intersection = max(0, x2 - x1) * max(0, y2 - y1)
        area_a = max(0, a[2] - a[0]) * max(0, a[3] - a[1])
        area_b = max(0, b[2] - b[0]) * max(0, b[3] - b[1])
        union = area_a + area_b - intersection
        return intersection / union if union else 0

    def update(
        self, frame: np.ndarray, detections: list[RawDetection]
    ) -> list[TrackedDetection]:
        del frame
        available = set(self._tracks)
        assigned: list[TrackedDetection] = []
        updated: dict[int, tuple[tuple[int, int, int, int], str, int]] = {}
        for detection in detections:
            # Le ballon reste non tracké dans cette baseline : pas d'identité artificielle.
            if detection.class_name != "person":
                assigned.append(TrackedDetection(detection, None))
                continue
            candidates = [
                (self._iou(detection.bbox, self._tracks[track_id][0]), track_id)
                for track_id in available
                if self._tracks[track_id][1] == detection.class_name
            ]
            score, track_id = max(candidates, default=(0.0, -1))
            if score < self.iou_threshold:
                track_id = self._next_id
                self._next_id += 1
            else:
                available.remove(track_id)
            updated[track_id] = (detection.bbox, detection.class_name, 0)
            assigned.append(TrackedDetection(detection, track_id))
        for track_id in available:
            bbox, class_name, missed = self._tracks[track_id]
            if missed + 1 <= self.max_missed:
                updated[track_id] = (bbox, class_name, missed + 1)
        self._tracks = updated
        return assigned

    def metadata(self) -> dict[str, Any]:
        return {"enabled": True, "name": "iou", "version": "1.0"}


class SupervisionByteTrack(Tracker):
    """Adaptateur optionnel vers Supervision, isolé du pipeline métier."""

    def __init__(self) -> None:
        try:
            import supervision as sv
        except ImportError as exc:
            raise RuntimeError(
                "Le tracker bytetrack exige le paquet optionnel supervision. "
                "Installez backend/requirements-video.txt."
            ) from exc
        self._sv = sv
        self._version = getattr(sv, "__version__", "unknown")
        self.reset()

    def reset(self) -> None:
        self._tracker = self._sv.ByteTrack()

    def update(
        self, frame: np.ndarray, detections: list[RawDetection]
    ) -> list[TrackedDetection]:
        del frame
        person_indices = [
            index
            for index, item in enumerate(detections)
            if item.class_name == "person"
        ]
        result = [TrackedDetection(item, None) for item in detections]
        if not person_indices:
            return result
        sv_detections = self._sv.Detections(
            xyxy=np.array(
                [detections[index].bbox for index in person_indices], dtype=float
            ),
            confidence=np.array(
                [detections[index].confidence for index in person_indices], dtype=float
            ),
            class_id=np.zeros(len(person_indices), dtype=int),
            data={"source_index": np.array(person_indices)},
        )
        tracked = self._tracker.update_with_detections(sv_detections)
        tracker_ids = tracked.tracker_id if tracked.tracker_id is not None else []
        source_indices = tracked.data.get("source_index", [])
        for source_index, track_id in zip(source_indices, tracker_ids):
            index = int(source_index)
            result[index] = TrackedDetection(detections[index], int(track_id))
        return result

    def metadata(self) -> dict[str, Any]:
        return {"enabled": True, "name": "bytetrack", "version": self._version}


# Chapter 5 Unified Re-exports
from app.video_analysis.ball_tracker import BallTrackConfig, BallTrackManager
from app.video_analysis.player_tracker import ByteTrackConfig, PlayerByteTrack
from app.video_analysis.tracking_diagnostics import (
    BallTrackingDiagnostics,
    compute_ball_diagnostics,
)
from app.video_analysis.tracking_schemas import (
    BallObservationState,
    BallTrackObservation,
    PlayerTrackObservation,
    TrackingState,
)
from app.video_analysis.tracking_visualizer import (
    draw_ball_track,
    draw_player_tracks,
    visualize_frame_tracks,
)


def create_tracker(enabled: bool, name: str) -> Tracker:
    if not enabled or name.strip().lower() == "none":
        return DisabledTracker()
    if name.strip().lower() == "iou":
        return IoUTracker()
    if name.strip().lower() in ("bytetrack", "bytetrack_player"):
        return SupervisionByteTrack()
    raise ValueError(f"Tracker vidéo inconnu : {name}")
