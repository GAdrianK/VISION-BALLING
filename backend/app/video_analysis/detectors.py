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
                    football_role="unknown_player",
                    confidence=confidence,
                    bbox=(int(x), int(y), int(x + width), int(y + height)),
                )
            )
        return detections

    def metadata(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "provider": "OpenCV",
            "device": "cpu",
            "classes": ["person"],
            "football_specific": False,
            "ball_detection": False,
        }

