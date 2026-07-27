from __future__ import annotations

import argparse
import json
from pathlib import Path

import cv2


def extract(video: Path, count: int, output: Path) -> dict:
    output.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video))
    total = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = capture.get(cv2.CAP_PROP_FPS)
    indices = sorted(
        {round(index * max(total - 1, 0) / max(count - 1, 1)) for index in range(count)}
    )
    candidates = []
    try:
        for frame_index in indices:
            capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
            ok, frame = capture.read()
            if not ok:
                continue
            filename = f"frame_{frame_index:08d}.jpg"
            cv2.imwrite(str(output / filename), frame)
            candidates.append(
                {
                    "frame_index": frame_index,
                    "timestamp_seconds": round(frame_index / fps, 6),
                    "image": filename,
                    "annotations": [],
                }
            )
    finally:
        capture.release()
    template = {
        "format_version": "1.0",
        "source_video_private": video.name,
        "classes": ["person", "sports ball"],
        "frames": candidates,
    }
    (output / "annotations.template.json").write_text(
        json.dumps(template, indent=2), encoding="utf-8"
    )
    return template


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    extract(args.video, args.count, args.output)


if __name__ == "__main__":
    main()
