from __future__ import annotations

from pathlib import Path

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
    labels_dir.mkdir()

    (labels_dir / "frame_000.txt").write_text("0 0.5 0.5 0.2 0.4\n1 0.8 0.8 0.05 0.05\n", encoding="utf-8")
    (labels_dir / "frame_001.txt").write_text("0 0.2 0.3 0.1 0.2\n", encoding="utf-8")

    adapter = YOLOAdapter(labels_dir=labels_dir, image_size=(1000, 1000))
    dataset = adapter.load_dataset()

    assert len(dataset) == 2
    f0 = dataset[0]
    assert len(f0.annotations) == 2
    assert f0.annotations[0].class_name == "person"
    assert f0.annotations[0].bbox == [400.0, 300.0, 600.0, 700.0]
    assert f0.annotations[1].class_name == "sports ball"


def test_mot_adapter_parsing(tmp_path: Path) -> None:
    gt_file = tmp_path / "gt.txt"
    content = (
        "1, 10, 100, 200, 50, 150, 1, 1, 1.0\n"
        "1, 11, 300, 400, 30, 30, 1, 2, 1.0\n"
        "2, 10, 105, 202, 50, 150, 1, 1, 1.0\n"
    )
    gt_file.write_text(content, encoding="utf-8")

    adapter = MOTChallengeAdapter(gt_file=gt_file)
    frames_dict = adapter.load_dataset()

    assert len(frames_dict) == 2
    assert 1 in frames_dict and 2 in frames_dict
    f1 = frames_dict[1]
    assert len(f1.annotations) == 2
    assert f1.annotations[0].track_id == 10
    assert f1.annotations[0].class_name == "person"
    assert f1.annotations[0].bbox == [100.0, 200.0, 150.0, 350.0]


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
    res = evaluator.evaluate(ground_truth=gt, predictions_by_frame=preds, duration_seconds=0.1, peak_rss_mb=12.5)

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
