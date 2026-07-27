from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.video_analysis.detectors import create_detector


def benchmark(video: Path, detector_name: str, sample_rate: int) -> dict:
    detector = create_detector(detector_name)
    detector.load()
    capture = cv2.VideoCapture(str(video))
    started = time.monotonic()
    frame_index = analyzed = persons = balls = 0
    frames_with_ball = 0
    confidences: list[float] = []
    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            if frame_index % max(1, sample_rate) == 0:
                detected = detector.detect(frame)
                analyzed += 1
                persons += sum(item.class_name == "person" for item in detected)
                frame_balls = [
                    item for item in detected if item.class_name == "sports ball"
                ]
                balls += len(frame_balls)
                frames_with_ball += bool(frame_balls)
                confidences.extend(item.confidence for item in detected)
            frame_index += 1
    finally:
        capture.release()
    duration = time.monotonic() - started
    return {
        "detector": detector_name,
        "technical_performance": {
            "total_seconds": round(duration, 3),
            "frames_analyzed": analyzed,
            "processing_fps": round(analyzed / duration, 3) if duration else 0,
        },
        "detection_volume": {
            "person_detections": persons,
            "ball_detections": balls,
            "frames_with_ball": frames_with_ball,
            "average_confidence": (
                round(sum(confidences) / len(confidences), 6) if confidences else 0
            ),
        },
        "precision": None,
        "warnings": [
            "Le volume de détections ne mesure pas la précision sans vérité terrain."
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", required=True, type=Path)
    parser.add_argument("--detectors", default="hog,yolo")
    parser.add_argument("--sample-rate", type=int, default=10)
    parser.add_argument("--output", type=Path, default=Path("benchmark_report.json"))
    args = parser.parse_args()
    report = {
        "video": str(args.video),
        "results": [
            benchmark(args.video, name.strip(), args.sample_rate)
            for name in args.detectors.split(",")
            if name.strip()
        ],
    }
    encoded = json.dumps(report, indent=2, ensure_ascii=False)
    args.output.write_text(encoded, encoding="utf-8")
    print(encoded)


if __name__ == "__main__":
    main()
