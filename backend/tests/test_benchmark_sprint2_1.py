from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest
from app.video_analysis.benchmark_adapters import (
    FrameGroundTruth,
    GroundTruthBox,
    MOTChallengeAdapter,
    YOLOAdapter,
)
from app.video_analysis.benchmark_metrics import (
    DetectionEvaluator,
    TrackingEvaluator,
)
from app.video_analysis.detectors import RawDetection


def test_yolo_adapter_parsing(tmp_path: Path) -> None:
    labels_dir = tmp_path / "labels"
    images_dir = tmp_path / "images"
    labels_dir.mkdir()
    images_dir.mkdir()

    (labels_dir / "frame_000.txt").write_text(
        "0 0.5 0.5 0.2 0.4\n1 0.8 0.8 0.05 0.05\n", encoding="utf-8"
    )
    (labels_dir / "frame_001.txt").write_text("0 0.2 0.3 0.1 0.2\n", encoding="utf-8")
    cv2.imwrite(
        str(images_dir / "frame_000.jpg"),
        np.zeros((500, 1000, 3), dtype=np.uint8),
    )
    cv2.imwrite(
        str(images_dir / "frame_001.jpg"),
        np.zeros((500, 1000, 3), dtype=np.uint8),
    )

    adapter = YOLOAdapter(labels_dir=labels_dir, images_dir=images_dir)
    dataset = adapter.load_dataset()

    assert len(dataset) == 2
    f0 = dataset[0]
    assert len(f0.annotations) == 2
    assert f0.width == 1000
    assert f0.height == 500
    assert f0.image_path == images_dir / "frame_000.jpg"
    assert f0.annotations[0].class_name == "sports ball"
    assert f0.annotations[0].bbox == [400.0, 150.0, 600.0, 350.0]
    assert f0.annotations[1].class_name == "person"


def test_mot_adapter_parsing(tmp_path: Path) -> None:
    gt_file = tmp_path / "gt.txt"
    frames_dir = tmp_path / "img1"
    frames_dir.mkdir()
    content = (
        "1, 10, 100, 200, 50, 150, 1, -1, -1, -1\n"
        "1, 11, 300, 400, 30, 30, 1, -1, -1, -1\n"
        "2, 10, 105, 202, 50, 150, 1, -1, -1, -1\n"
        "2, 99, 0, 0, 10, 10, 0, -1, -1, -1\n"
    )
    gt_file.write_text(content, encoding="utf-8")
    cv2.imwrite(
        str(frames_dir / "000001.jpg"),
        np.zeros((720, 1280, 3), dtype=np.uint8),
    )
    cv2.imwrite(
        str(frames_dir / "000002.jpg"),
        np.zeros((720, 1280, 3), dtype=np.uint8),
    )

    adapter = MOTChallengeAdapter(gt_file=gt_file, frames_dir=frames_dir)
    frames_dict = adapter.load_dataset()

    assert len(frames_dict) == 2
    assert 1 in frames_dict and 2 in frames_dict
    f1 = frames_dict[1]
    assert len(f1.annotations) == 2
    assert f1.annotations[0].track_id == 10
    assert f1.annotations[0].class_name == "tracked_object"
    assert f1.annotations[0].bbox == [100.0, 200.0, 150.0, 350.0]
    assert f1.image_path == frames_dir / "000001.jpg"
    assert f1.width == 1280
    assert f1.height == 720
    assert len(frames_dict[2].annotations) == 1


def test_detection_evaluator_metrics() -> None:
    gt = [
        FrameGroundTruth(
            frame_index=0,
            image_path=None,
            width=1000,
            height=1000,
            annotations=[
                GroundTruthBox(0, "person", [100, 100, 200, 300]),
                GroundTruthBox(0, "sports ball", [500, 500, 550, 550]),
            ],
        )
    ]

    preds = {
        0: [
            RawDetection("person", "player_candidate", 0.9, (102, 101, 198, 299)),
            RawDetection("sports ball", "ball_candidate", 0.85, (498, 502, 552, 548)),
        ]
    }

    evaluator = DetectionEvaluator(iou_threshold=0.5)
    res = evaluator.evaluate(
        ground_truth=gt,
        predictions_by_frame=preds,
        duration_seconds=0.1,
        peak_rss_mb=12.5,
    )

    assert res.precision == 1.0
    assert res.recall == 1.0
    assert res.f1_score == 1.0
    assert res.mAP_50 == 1.0
    assert res.ball_recall == 1.0
    assert res.peak_rss_mb == 12.5


def test_tracking_evaluator_metrics() -> None:
    gt_frames = {
        1: FrameGroundTruth(
            frame_index=1,
            image_path=None,
            width=1000,
            height=1000,
            annotations=[
                GroundTruthBox(1, "person", [100, 100, 200, 300], track_id=1),
                GroundTruthBox(1, "person", [400, 400, 500, 600], track_id=2),
            ],
        ),
        2: FrameGroundTruth(
            frame_index=2,
            image_path=None,
            width=1000,
            height=1000,
            annotations=[
                GroundTruthBox(2, "person", [105, 102, 205, 302], track_id=1),
                GroundTruthBox(2, "person", [405, 402, 505, 602], track_id=2),
            ],
        ),
    }

    tracker_preds = {
        1: [
            {"track_id": 1, "class_name": "person", "bbox": [100, 100, 200, 300]},
            {"track_id": 2, "class_name": "person", "bbox": [400, 400, 500, 600]},
        ],
        2: [
            {"track_id": 1, "class_name": "person", "bbox": [105, 102, 205, 302]},
            {"track_id": 2, "class_name": "person", "bbox": [405, 402, 505, 602]},
        ],
    }

    evaluator = TrackingEvaluator(iou_threshold=0.5)
    res = evaluator.evaluate(gt_frames, tracker_preds, tracker_name="test_tracker")

    assert res.hota_0_5 == 1.0
    assert res.deta_0_5 == 1.0
    assert res.assa_0_5 == 1.0
    assert res.idf1 == 1.0
    assert res.num_gt_tracks == 2
    assert res.num_pred_tracks == 2


def test_trackeval_payload_uses_contiguous_ids_and_iou() -> None:
    gt_frames = {
        1: FrameGroundTruth(
            frame_index=1,
            image_path=None,
            width=100,
            height=100,
            annotations=[
                GroundTruthBox(1, "tracked_object", [10, 10, 30, 40], track_id=42)
            ],
        )
    }
    tracker_preds = {
        1: [
            {
                "track_id": 900,
                "class_name": "person",
                "bbox": [10, 10, 30, 40],
            }
        ]
    }

    data = TrackingEvaluator()._build_trackeval_data(gt_frames, tracker_preds)

    assert data["num_gt_ids"] == 1
    assert data["num_tracker_ids"] == 1
    assert data["gt_ids"][0].tolist() == [0]
    assert data["tracker_ids"][0].tolist() == [0]
    assert data["similarity_scores"][0].tolist() == [[1.0]]


def test_official_trackeval_integration() -> None:
    pytest.importorskip("trackeval")
    gt_frames = {
        1: FrameGroundTruth(
            frame_index=1,
            image_path=None,
            width=100,
            height=100,
            annotations=[
                GroundTruthBox(1, "tracked_object", [10, 10, 30, 40], track_id=42)
            ],
        )
    }
    tracker_preds = {
        1: [
            {
                "track_id": 900,
                "class_name": "person",
                "bbox": [10, 10, 30, 40],
            }
        ]
    }

    result = TrackingEvaluator().evaluate(
        gt_frames,
        tracker_preds,
        tracker_name="trackeval_smoke",
        use_trackeval=True,
    )

    assert result.evaluation_engine == "trackeval (official 19 thresholds)"
    assert result.hota_0_5 == 1.0
    assert result.hota_official == 1.0
    assert result.deta_official == 1.0
    assert result.assa_official == 1.0
