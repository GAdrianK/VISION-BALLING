from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.video_analysis.detectors import RawDetection


@dataclass(frozen=True)
class TrackedDetection:
    detection: RawDetection
    track_id: int | None


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


def create_tracker(enabled: bool, name: str) -> Tracker:
    if not enabled or name.strip().lower() == "none":
        return DisabledTracker()
    if name.strip().lower() == "iou":
        return IoUTracker()
    if name.strip().lower() == "bytetrack":
        return SupervisionByteTrack()
    raise ValueError(f"Tracker vidéo inconnu : {name}")
