from __future__ import annotations

import argparse
import json
from pathlib import Path


def iou(a: list[float], b: list[float]) -> float:
    x1, y1, x2, y2 = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - intersection
    return intersection / union if union > 0 else 0


def evaluate(annotations: dict, predictions: dict, threshold: float = 0.5) -> dict:
    truth = {
        (frame["frame_index"], item["class_name"], index): item
        for frame in annotations["frames"]
        for index, item in enumerate(frame["annotations"])
    }
    matched: set[tuple] = set()
    tp = fp = 0
    ious: list[float] = []
    for prediction in predictions.get("detections", []):
        candidates = [
            (iou(prediction["bbox"], item["bbox"]), key)
            for key, item in truth.items()
            if key not in matched
            and key[0] == prediction["frame_index"]
            and key[1] == prediction["class_name"]
        ]
        score, key = max(candidates, default=(0, None))
        if score >= threshold and key is not None:
            tp += 1
            matched.add(key)
            ious.append(score)
        else:
            fp += 1
    fn = len(truth) - len(matched)
    return {
        "true_positives": tp,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": tp / (tp + fp) if tp + fp else 0,
        "recall": tp / (tp + fn) if tp + fn else 0,
        "mean_iou": sum(ious) / len(ious) if ious else 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--annotations", required=True, type=Path)
    parser.add_argument("--predictions", required=True, type=Path)
    args = parser.parse_args()
    print(
        json.dumps(
            evaluate(
                json.loads(args.annotations.read_text()),
                json.loads(args.predictions.read_text()),
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
