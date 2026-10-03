from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2


@dataclass
class GroundTruthBox:
    frame_index: int
    class_name: str
    bbox: list[float]  # [x1, y1, x2, y2]
    track_id: int | None = None
    confidence: float = 1.0


@dataclass
class FrameGroundTruth:
    frame_index: int
    image_path: Path | None
    width: int | None
    height: int | None
    annotations: list[GroundTruthBox]


SOCCERNET_H250_CLASS_MAP = {
    0: "sports ball",
    1: "person",
}

COCO_CLASS_MAP = {
    0: "person",
    32: "sports ball",
}


class YOLOAdapter:
    """
    Adapter for YOLO format datasets (e.g. SoccerNet-v3 H250 or standard YOLO).
    Reads images and corresponding .txt label files containing:
      class_id center_x center_y width height (all normalized 0..1)
    """

    def __init__(
        self,
        labels_dir: Path,
        images_dir: Path | None = None,
        class_map: dict[int, str] | None = None,
        image_size: tuple[int, int] = (1920, 1080),  # (width, height)
    ) -> None:
        self.labels_dir = Path(labels_dir)
        self.images_dir = Path(images_dir) if images_dir else None
        self.class_map = class_map or SOCCERNET_H250_CLASS_MAP
        self.default_width, self.default_height = image_size

    def _find_image(self, label_file: Path) -> Path | None:
        if self.images_dir is None:
            return None

        relative_parent = label_file.parent.relative_to(self.labels_dir)
        candidate_parents = (
            self.images_dir / relative_parent,
            self.images_dir,
        )
        for parent in candidate_parents:
            for ext in (".jpg", ".jpeg", ".png"):
                candidate = parent / f"{label_file.stem}{ext}"
                if candidate.is_file():
                    return candidate
        return None

    def parse_file(
        self,
        label_file: Path,
        frame_index: int,
        img_width: int | None = None,
        img_height: int | None = None,
    ) -> FrameGroundTruth:
        image_path = self._find_image(label_file)
        if image_path and (img_width is None or img_height is None):
            image = cv2.imread(str(image_path))
            if image is None:
                raise ValueError(f"Image illisible : {image_path}")
            detected_height, detected_width = image.shape[:2]
        else:
            detected_width, detected_height = self.default_width, self.default_height

        w = img_width or detected_width
        h = img_height or detected_height
        boxes: list[GroundTruthBox] = []

        if label_file.is_file():
            content = label_file.read_text(encoding="utf-8").strip()
            if content:
                for line in content.splitlines():
                    parts = line.strip().split()
                    if len(parts) < 5:
                        continue
                    class_id = int(parts[0])
                    cx, cy, bw, bh = (float(p) for p in parts[1:5])
                    class_name = self.class_map.get(class_id, f"class_{class_id}")
                    if class_name == "ignored":
                        continue

                    x1 = max(0.0, (cx - bw / 2.0) * w)
                    y1 = max(0.0, (cy - bh / 2.0) * h)
                    x2 = min(float(w), (cx + bw / 2.0) * w)
                    y2 = min(float(h), (cy + bh / 2.0) * h)

                    boxes.append(
                        GroundTruthBox(
                            frame_index=frame_index,
                            class_name=class_name,
                            bbox=[
                                round(x1, 2),
                                round(y1, 2),
                                round(x2, 2),
                                round(y2, 2),
                            ],
                        )
                    )

        return FrameGroundTruth(
            frame_index=frame_index,
            image_path=image_path,
            width=w,
            height=h,
            annotations=boxes,
        )

    def load_dataset(self) -> list[FrameGroundTruth]:
        label_files = sorted(self.labels_dir.rglob("*.txt"))
        dataset: list[FrameGroundTruth] = []
        for idx, label_file in enumerate(label_files):
            dataset.append(self.parse_file(label_file, frame_index=idx))
        return dataset


class MOTChallengeAdapter:
    """
    Adapter for MOTChallenge format datasets (SoccerNet Tracking gt.txt).
    SoccerNet uses ten MOTChallenge-compatible columns:
      frame, track_id, bb_left, bb_top, bb_width, bb_height,
      confidence, -1, -1, -1

    SoccerNet Tracking does not expose an object class in these files.
    """

    def __init__(
        self,
        gt_file: Path,
        frames_dir: Path | None = None,
        default_class_name: str = "tracked_object",
        image_size: tuple[int, int] = (1920, 1080),
    ) -> None:
        self.gt_file = Path(gt_file)
        self.frames_dir = Path(frames_dir) if frames_dir else None
        self.default_class_name = default_class_name
        self.default_width, self.default_height = image_size

    def _find_frame(self, frame_index: int) -> Path | None:
        if self.frames_dir is None:
            return None
        stems = (
            str(frame_index),
            f"{frame_index:06d}",
            f"{frame_index:08d}",
        )
        for stem in stems:
            for ext in (".jpg", ".jpeg", ".png"):
                candidate = self.frames_dir / f"{stem}{ext}"
                if candidate.is_file():
                    return candidate
        return None

    def load_dataset(self) -> dict[int, FrameGroundTruth]:
        frames_dict: dict[int, list[GroundTruthBox]] = {}
        if not self.gt_file.is_file():
            return {}

        content = self.gt_file.read_text(encoding="utf-8").strip()
        if not content:
            return {}

        for line in content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.replace(";", ",").split(",") if p.strip()]
            if len(parts) < 6:
                continue

            frame_idx = int(float(parts[0]))
            track_id = int(float(parts[1]))
            bb_left = float(parts[2])
            bb_top = float(parts[3])
            bb_width = float(parts[4])
            bb_height = float(parts[5])

            confidence = float(parts[6]) if len(parts) >= 7 else 1.0
            if confidence <= 0:
                continue

            x1 = max(0.0, bb_left)
            y1 = max(0.0, bb_top)
            x2 = bb_left + bb_width
            y2 = bb_top + bb_height

            box = GroundTruthBox(
                frame_index=frame_idx,
                class_name=self.default_class_name,
                bbox=[round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                track_id=track_id,
                confidence=confidence,
            )

            if frame_idx not in frames_dict:
                frames_dict[frame_idx] = []
            frames_dict[frame_idx].append(box)

        result: dict[int, FrameGroundTruth] = {}
        for f_idx in sorted(frames_dict.keys()):
            image_path = self._find_frame(f_idx)
            width, height = self.default_width, self.default_height
            if image_path:
                image = cv2.imread(str(image_path))
                if image is None:
                    raise ValueError(f"Frame illisible : {image_path}")
                height, width = image.shape[:2]
            result[f_idx] = FrameGroundTruth(
                frame_index=f_idx,
                image_path=image_path,
                width=width,
                height=height,
                annotations=frames_dict[f_idx],
            )
        return result
