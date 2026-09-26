from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, ClassVar

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

    COCO_FOOTBALL_CLASS_MAP: ClassVar[dict[int, str]] = {
        0: "person",
        32: "sports ball",
    }
    H250_FOOTBALL_CLASS_MAP: ClassVar[dict[int, str]] = {
        0: "sports ball",
        1: "person",
    }
    MODEL_PROFILES: ClassVar[dict[str, dict[int, str]]] = {
        "coco": COCO_FOOTBALL_CLASS_MAP,
        "h250": H250_FOOTBALL_CLASS_MAP,
    }

    def __init__(
        self,
        model_path: str,
        device: str = "cpu",
        person_threshold: float = 0.45,
        ball_threshold: float = 0.25,
        class_map: dict[int, str] | None = None,
        model_profile: str = "coco",
    ) -> None:
        normalized_profile = model_profile.strip().lower()
        if normalized_profile not in self.MODEL_PROFILES:
            accepted = ", ".join(sorted(self.MODEL_PROFILES))
            raise ValueError(
                f"Profil de modèle YOLO inconnu : {model_profile!r}. "
                f"Valeurs acceptées : {accepted}."
            )
        self.model_path = model_path
        self.model_id = model_path.replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]
        self.device = device
        self.person_threshold = person_threshold
        self.ball_threshold = ball_threshold
        self.model_profile = normalized_profile
        selected_map = (
            class_map
            if class_map is not None
            else self.MODEL_PROFILES[normalized_profile]
        )
        self.class_map = dict(selected_map)
        self._model: Any = None
        try:
            self._version = metadata.version("ultralytics")
        except metadata.PackageNotFoundError:
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
            classes=sorted(self.class_map),
            verbose=False,
        )
        detections: list[RawDetection] = []
        for result in results:
            for box in result.boxes:
                class_id = int(box.cls.item())
                confidence = float(box.conf.item())
                class_name = self.class_map.get(class_id)
                if class_name not in {"person", "sports ball"}:
                    continue
                if class_name == "person":
                    role, threshold = "player_candidate", self.person_threshold
                else:
                    role, threshold = "ball_candidate", self.ball_threshold
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
            "model_id": self.model_id,
            "provider": "Ultralytics",
            "device": self.device,
            "classes": ["person", "sports ball"],
            "class_map": self.class_map,
            "football_specific": self.class_map != self.COCO_FOOTBALL_CLASS_MAP,
            "ball_detection": True,
        }


class RFDETRDetector(ObjectDetector):
    """Adaptateur RF-DETR pour l'évaluation canonique et l'inférence VISION-BALLING."""

    H250_FOOTBALL_CLASS_MAP: ClassVar[dict[int, str]] = {
        0: "sports ball",
        1: "person",
    }

    def __init__(
        self,
        model_path: str,
        device: str = "cuda",
        resolution: int = 960,
        person_threshold: float = 0.45,
        ball_threshold: float = 0.25,
        class_map: dict[int, str] | None = None,
        optimize_inference: bool = True,
    ) -> None:
        self.model_path = model_path
        self.model_id = Path(model_path).name
        self.device = device
        self.resolution = resolution
        self.person_threshold = person_threshold
        self.ball_threshold = ball_threshold
        self.class_map = dict(class_map or self.H250_FOOTBALL_CLASS_MAP)
        self.optimize_inference = optimize_inference
        self._model: Any = None
        self._version: str = "unknown"

    def load(self) -> None:
        try:
            import importlib.metadata
            import torch
            import rfdetr
            from rfdetr import RFDETRSmall
        except ImportError as exc:
            raise RuntimeError(
                "Le détecteur rfdetr exige le paquet optionnel rfdetr. "
                "Activez l'environnement .venv-rfdetr."
            ) from exc

        try:
            self._version = importlib.metadata.version("rfdetr")
        except Exception:
            self._version = getattr(rfdetr, "__version__", "unknown")

        ckpt_path = Path(self.model_path)
        if not ckpt_path.is_file():
            raise FileNotFoundError(f"Checkpoint RF-DETR introuvable : {ckpt_path}")

        self._model = RFDETRSmall.from_checkpoint(str(ckpt_path), resolution=self.resolution)
        if self.optimize_inference and torch.cuda.is_available() and self.device in ("0", "cuda", "cuda:0"):
            try:
                self._model.inference(compile=False, dtype=torch.float16)
            except Exception:
                pass

    def detect(self, frame: np.ndarray) -> list[RawDetection]:
        if self._model is None:
            raise RuntimeError("Le détecteur RF-DETR doit être chargé avant detect().")

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB) if frame.ndim == 3 else frame
        min_thresh = min(self.person_threshold, self.ball_threshold)

        dets = self._model.predict(
            rgb_frame,
            threshold=min_thresh,
            include_source_image=False,
        )

        detections: list[RawDetection] = []
        if len(dets) == 0:
            return detections

        for xyxy, conf, cls_id in zip(dets.xyxy, dets.confidence, dets.class_id):
            cid = int(cls_id)
            c_conf = float(conf)
            class_name = self.class_map.get(cid)
            if class_name not in {"person", "sports ball", "ball"}:
                continue

            if class_name == "person":
                role, threshold = "player_candidate", self.person_threshold
            else:
                role, threshold = "ball_candidate", self.ball_threshold

            if c_conf < threshold:
                continue

            x1, y1, x2, y2 = (int(round(v)) for v in xyxy)
            canonical_name = "sports ball" if class_name in ("sports ball", "ball") else "person"
            detections.append(
                RawDetection(
                    class_name=canonical_name,
                    football_role=role,
                    confidence=c_conf,
                    bbox=(x1, y1, x2, y2),
                )
            )
        return detections

    def metadata(self) -> dict[str, Any]:
        return {
            "name": "rfdetr",
            "version": self._version,
            "model_id": self.model_id,
            "provider": "RF-DETR",
            "device": self.device,
            "resolution": self.resolution,
            "classes": ["person", "sports ball"],
            "class_map": self.class_map,
            "football_specific": True,
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
    class_map: dict[int, str] | None = None,
    model_profile: str = "coco",
    resolution: int = 960,
) -> ObjectDetector:
    normalized = name.strip().lower()
    if normalized in {"hog", "opencv-hog", "opencv-hog-default-people-detector"}:
        return OpenCVHOGPersonDetector(confidence_threshold)
    if normalized in {"yolo", "ultralytics"}:
        return UltralyticsYOLODetector(
            model_path=model_path,
            device=device,
            person_threshold=person_threshold,
            ball_threshold=ball_threshold,
            class_map=class_map,
            model_profile=model_profile,
        )
    if normalized in {"rfdetr", "rf-detr", "rfdetr_small", "rf-detr-small"}:
        return RFDETRDetector(
            model_path=model_path,
            device=device,
            resolution=resolution,
            person_threshold=person_threshold,
            ball_threshold=ball_threshold,
            class_map=class_map,
        )
    raise ValueError(f"Détecteur vidéo inconnu : {name}")
