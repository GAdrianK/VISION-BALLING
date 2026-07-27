from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np


@dataclass(frozen=True)
class RawDetection:
    class_name: str
    football_role: str
    confidence: float
    bbox: tuple[int, int, int, int]


class ObjectDetector(ABC):
    @abstractmethod
    def load(self) -> None:
        """Charge les ressources du détecteur."""

    @abstractmethod
    def detect(self, frame: np.ndarray) -> list[RawDetection]:
        """Retourne uniquement les objets effectivement détectés."""

    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Décrit précisément la baseline utilisée."""


class OpenCVHOGPersonDetector(ObjectDetector):
    """Baseline générique OpenCV, CPU, limitée à la classe personne."""

    model_id = "opencv-hog-default-people-detector"

    def __init__(self, confidence_threshold: float = 0.45) -> None:
        self.confidence_threshold = confidence_threshold
        self._hog: cv2.HOGDescriptor | None = None

    def load(self) -> None:
        hog = cv2.HOGDescriptor()
        hog.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        self._hog = hog

    def detect(self, frame: np.ndarray) -> list[RawDetection]:
        if self._hog is None:
            raise RuntimeError("Le détecteur doit être chargé avant detect().")
        boxes, weights = self._hog.detectMultiScale(
            frame, winStride=(8, 8), padding=(8, 8), scale=1.05
        )
        detections: list[RawDetection] = []
        for (x, y, width, height), weight in zip(boxes, weights):
            confidence = max(0.0, min(1.0, float(weight)))
            if confidence < self.confidence_threshold:
                continue
            detections.append(
                RawDetection(
                    class_name="person",
                    football_role="player_candidate",
                    confidence=confidence,
                    bbox=(int(x), int(y), int(x + width), int(y + height)),
                )
            )
        return detections

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "hog",
            "version": cv2.__version__,
            "model_id": self.model_id,
            "provider": "OpenCV",
            "device": "cpu",
            "classes": ["person"],
            "football_specific": False,
            "ball_detection": False,
        }


class UltralyticsYOLODetector(ObjectDetector):
    """Adaptateur optionnel : le code métier ne dépend pas d'Ultralytics."""

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        person_threshold: float = 0.45,
        ball_threshold: float = 0.25,
    ) -> None:
        self.model_path = model_path
        self.device = device
        self.person_threshold = person_threshold
        self.ball_threshold = ball_threshold
        self._model: Any = None
        self._version = "unknown"

    def load(self) -> None:
        try:
            import ultralytics
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Le détecteur yolo exige le paquet optionnel ultralytics. "
                "Installez backend/requirements-video.txt."
            ) from exc
        self._version = getattr(ultralytics, "__version__", "unknown")
        self._model = YOLO(self.model_path)

    def detect(self, frame: np.ndarray) -> list[RawDetection]:
        if self._model is None:
            raise RuntimeError("Le détecteur doit être chargé avant detect().")
        results = self._model.predict(
            source=frame,
            device=self.device,
            conf=min(self.person_threshold, self.ball_threshold),
            classes=[0, 32],
            verbose=False,
        )
        detections: list[RawDetection] = []
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls.item())
                confidence = float(box.conf.item())
                if class_id == 0:
                    class_name, role, threshold = (
                        "person",
                        "player_candidate",
                        self.person_threshold,
                    )
                elif class_id == 32:
                    class_name, role, threshold = (
                        "sports ball",
                        "ball_candidate",
                        self.ball_threshold,
                    )
                else:
                    continue
                if confidence < threshold:
                    continue
                x1, y1, x2, y2 = (int(value) for value in box.xyxy[0].tolist())
                detections.append(
                    RawDetection(class_name, role, confidence, (x1, y1, x2, y2))
                )
        return detections

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "yolo",
            "version": self._version,
            "model_id": self.model_path,
            "provider": "Ultralytics",
            "device": self.device,
            "classes": ["person", "sports ball"],
            "football_specific": False,
            "ball_detection": True,
        }


def create_detector(
    name: str,
    *,
    model_path: str = "yolo11n.pt",
    device: str = "cpu",
    confidence_threshold: float = 0.45,
    person_threshold: float = 0.45,
    ball_threshold: float = 0.25,
) -> ObjectDetector:
    normalized = name.strip().lower()
    if normalized in {"hog", "opencv-hog", "opencv-hog-default-people-detector"}:
        return OpenCVHOGPersonDetector(confidence_threshold)
    if normalized in {"yolo", "ultralytics"}:
        return UltralyticsYOLODetector(
            model_path, device, person_threshold, ball_threshold
        )
    raise ValueError(f"Détecteur vidéo inconnu : {name}")
