from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


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


DEFAULT_YOLO_CLASS_MAP = {
    0: "person",
    1: "sports ball",
    32: "sports ball",
}

DEFAULT_MOT_CLASS_MAP = {
    1: "person",
    2: "sports ball",
    -1: "ignored",
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
        self.class_map = class_map or DEFAULT_YOLO_CLASS_MAP
        self.default_width, self.default_height = image_size

    def parse_file(
        self,
        label_file: Path,
        frame_index: int,
        img_width: int | None = None,
        img_height: int | None = None,
    ) -> FrameGroundTruth:
        w = img_width or self.default_width
        h = img_height or self.default_height
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
                            bbox=[round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                        )
                    )

        img_path = None
        if self.images_dir:
            stem = label_file.stem
            for ext in (".jpg", ".png", ".jpeg"):
                candidate = self.images_dir / f"{stem}{ext}"
                if candidate.is_file():
                    img_path = candidate
                    break

        return FrameGroundTruth(
            frame_index=frame_index,
            image_path=img_path,
            width=w,
            height=h,
            annotations=boxes,
        )

    def load_dataset(self) -> list[FrameGroundTruth]:
        label_files = sorted(self.labels_dir.glob("*.txt"))
        dataset: list[FrameGroundTruth] = []
        for idx, label_file in enumerate(label_files):
            dataset.append(self.parse_file(label_file, frame_index=idx))
        return dataset


class MOTChallengeAdapter:
    """
    Adapter for MOTChallenge format datasets (SoccerNet Tracking gt.txt).
    Each line in gt.txt format:
      frame, track_id, bb_left, bb_top, bb_width, bb_height, mark, class_id, visibility
    """

    def __init__(
        self,
        gt_file: Path,
        class_map: dict[int, str] | None = None,
        image_size: tuple[int, int] = (1920, 1080),
    ) -> None:
        self.gt_file = Path(gt_file)
        self.class_map = class_map or DEFAULT_MOT_CLASS_MAP
        self.default_width, self.default_height = image_size

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

            class_id = int(float(parts[7])) if len(parts) >= 8 else 1
            class_name = self.class_map.get(class_id, "person")
            if class_name == "ignored":
                continue

            x1 = max(0.0, bb_left)
            y1 = max(0.0, bb_top)
            x2 = bb_left + bb_width
            y2 = bb_top + bb_height

            box = GroundTruthBox(
                frame_index=frame_idx,
                class_name=class_name,
                bbox=[round(x1, 2), round(y1, 2), round(x2, 2), round(y2, 2)],
                track_id=track_id,
            )

            if frame_idx not in frames_dict:
                frames_dict[frame_idx] = []
            frames_dict[frame_idx].append(box)

        result: dict[int, FrameGroundTruth] = {}
        for f_idx in sorted(frames_dict.keys()):
            result[f_idx] = FrameGroundTruth(
                frame_index=f_idx,
                image_path=None,
                width=self.default_width,
                height=self.default_height,
                annotations=frames_dict[f_idx],
            )
        return result
