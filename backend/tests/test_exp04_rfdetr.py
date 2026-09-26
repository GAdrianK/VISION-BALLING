from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from h250_dataset import (  # noqa: E402
    EXPECTED_SPLIT_COUNTS,
    H250ValidationError,
    validate_h250_dataset,
)
from run_exp04_rfdetr import (  # noqa: E402
    EXPECTED_RFDETR_SMALL_SHA256,
    FORBIDDEN_EXP01_BEST_SHA256,
    FORBIDDEN_EXP02_BEST_SHA256,
    FORBIDDEN_EXP03_BEST_SHA256,
    _comparison,
    _require_mode_consistency,
    build_preflight,
    load_spec,
    parse_args,
)
from app.video_analysis.detectors import RFDETRDetector, create_detector  # noqa: E402
from app.video_analysis.benchmark_metrics import DetectionEvaluator  # noqa: E402


def _build_tiny_h250(root: Path, *, names: str = "  0: ball\n  1: person\n") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    data_yaml = root / "data.yaml"
    data_yaml.write_text(
        "path: .\n"
        "train: train/images\n"
        "val: valid/images\n"
        "test: test/images\n"
        "\n"
        "names:\n"
        f"{names}",
        encoding="utf-8",
    )
    for split in ("train", "valid", "test"):
        images = root / split / "images"
        labels = root / split / "labels"
        images.mkdir(parents=True, exist_ok=True)
        labels.mkdir(parents=True, exist_ok=True)
        (images / "frame.jpg").write_bytes(b"dummy")
        (labels / "frame.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    return data_yaml


def test_exp04_spec_freezes_rfdetr_small_and_training_parameters() -> None:
    spec = load_spec(ROOT / "configs/training/exp04_rfdetr_small_h250_960.json")

    assert spec["spec_version"] == "1.0.0"
    assert spec["experiment_id"] == "exp04_rfdetr_small_h250_960"
    assert spec["status"] == "READY_TO_RUN"

    initial_model = spec["initial_model"]
    assert initial_model["model_id"] == "rf-detr-small"
    assert initial_model["variant"] == "RFDETRSmall"
    assert initial_model["filename"] == "rf-detr-small.pth"
    assert initial_model["bytes"] == 386045550
    assert initial_model["sha256"] == EXPECTED_RFDETR_SMALL_SHA256
    assert initial_model["fresh_start_required"] is True
    assert initial_model["forbidden_initial_checkpoint"] == "EXP-03 best.pt"

    dataset = spec["dataset"]
    assert dataset["expected_split_counts"] == EXPECTED_SPLIT_COUNTS
    assert dataset["classes"] == {"0": "ball", "1": "person"}
    assert dataset["dataset_role"] == "training"

    training = spec["training"]
    assert training["model"] == "RFDETRSmall"
    assert training["resolution"] == 960
    assert training["epochs"] == 30
    assert training["batch_size"] == 2
    assert training["grad_accum_steps"] == 2
    assert training["effective_batch_size"] == 4
    assert training["gradient_checkpointing"] is True
    assert training["lr"] == 0.0001
    assert training["lr_encoder"] == 0.00015
    assert training["optimizer"] == "adamw"
    assert training["weight_decay"] == 0.0001
    assert training["use_ema"] is True
    assert training["seed"] == 42
    assert training["run_test"] is False
    assert training["num_queries"] == 300
    assert training["patch_size"] == 16
    assert training["num_windows"] == 2


def test_exp04_runner_rejects_forbidden_yolo_checkpoints(tmp_path: Path) -> None:
    data_yaml = _build_tiny_h250(tmp_path / "dataset")
    spec = copy.deepcopy(load_spec(ROOT / "configs/training/exp04_rfdetr_small_h250_960.json"))
    spec["dataset"]["expected_split_counts"] = {"train": 1, "valid": 1, "test": 1}

    fake_ckpt = tmp_path / "fake_checkpoint.pt"
    fake_ckpt.write_bytes(b"fake_checkpoint")

    for forbidden_hash in (
        FORBIDDEN_EXP01_BEST_SHA256,
        FORBIDDEN_EXP02_BEST_SHA256,
        FORBIDDEN_EXP03_BEST_SHA256,
    ):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("run_exp04_rfdetr.sha256_file", lambda p: forbidden_hash)
            args = parse_args(
                ["--data", str(data_yaml), "--weights", str(fake_ckpt), "--check-only", "--device", "cpu"]
            )
            with pytest.raises(H250ValidationError, match="interdit formellement d'initialiser"):
                build_preflight(args, spec)


def test_exp04_modes_are_mutually_exclusive() -> None:
    with pytest.raises(H250ValidationError, match="mutuellement exclusifs"):
        _require_mode_consistency(parse_args(["--resume", "--restart"]))
    with pytest.raises(H250ValidationError, match="mutuellement exclusifs"):
        _require_mode_consistency(parse_args(["--resume", "--eval-only"]))
    with pytest.raises(H250ValidationError, match="mutuellement exclusifs"):
        _require_mode_consistency(parse_args(["--smoke-test", "--resume"]))


def test_exp04_h250_dataset_isolation_and_no_golden() -> None:
    spec = load_spec(ROOT / "configs/training/exp04_rfdetr_small_h250_960.json")
    dataset = spec["dataset"]
    counts = dataset["expected_split_counts"]
    assert counts["train"] == 14368
    assert counts["valid"] == 2726
    assert counts["test"] == 2692
    assert dataset["classes"] == {"0": "ball", "1": "person"}

    prohibited = spec["privacy_and_split"]["prohibited_training_sources"]
    assert "data/golden" in prohibited
    assert "CVAT golden exports" in prohibited


def test_exp04_canonical_evaluator_thresholds_match_exp03() -> None:
    spec = load_spec(ROOT / "configs/training/exp04_rfdetr_small_h250_960.json")
    eval_cfg = spec["evaluation"]
    assert eval_cfg["iou_threshold"] == 0.5
    assert eval_cfg["ball_confidence"] == 0.25
    assert eval_cfg["person_confidence"] == 0.45
    assert eval_cfg["expected_images"] == 2726

    evaluator = DetectionEvaluator(iou_threshold=eval_cfg["iou_threshold"])
    assert evaluator.iou_threshold == 0.5


def test_exp04_rfdetr_detector_adapter_mapping_and_thresholding() -> None:
    detector = RFDETRDetector(
        model_path="dummy.pth",
        device="cpu",
        resolution=960,
        person_threshold=0.45,
        ball_threshold=0.25,
        class_map={0: "sports ball", 1: "person"},
    )
    assert detector.person_threshold == 0.45
    assert detector.ball_threshold == 0.25
    assert detector.resolution == 960

    # Mock model
    class MockDetections:
        def __init__(self):
            self.xyxy = np.array([
                [10, 10, 30, 30],   # Ball, conf 0.30 -> pass (> 0.25)
                [40, 40, 60, 60],   # Ball, conf 0.20 -> filtered (< 0.25)
                [100, 100, 200, 200], # Person, conf 0.80 -> pass (> 0.45)
                [300, 300, 400, 400], # Person, conf 0.40 -> filtered (< 0.45)
            ])
            self.confidence = np.array([0.30, 0.20, 0.80, 0.40])
            self.class_id = np.array([0, 0, 1, 1])

        def __len__(self):
            return 4

    class MockModel:
        def predict(self, frame, threshold, include_source_image):
            return MockDetections()

    detector._model = MockModel()

    dummy_frame = np.zeros((1080, 1920, 3), dtype=np.uint8)
    detections = detector.detect(dummy_frame)

    assert len(detections) == 2
    # First detection is ball
    assert detections[0].class_name == "sports ball"
    assert detections[0].football_role == "ball_candidate"
    assert detections[0].confidence == 0.30
    assert detections[0].bbox == (10, 10, 30, 30)

    # Second detection is person
    assert detections[1].class_name == "person"
    assert detections[1].football_role == "player_candidate"
    assert detections[1].confidence == 0.80
    assert detections[1].bbox == (100, 100, 200, 200)


def test_exp04_environment_separation_from_yolo() -> None:
    # Verifies that rfdetr environment is isolated
    rfdetr_venv = ROOT / ".venv-rfdetr"
    yolo_venv = ROOT / ".venv-training"
    assert rfdetr_venv.exists(), ".venv-rfdetr must exist"
    assert yolo_venv.exists(), ".venv-training must exist"
    # Ensure they point to separate locations
    assert rfdetr_venv.resolve() != yolo_venv.resolve()


def test_exp04_smoke_test_subset_cannot_leak_into_full_config(tmp_path: Path) -> None:
    spec = load_spec(ROOT / "configs/training/exp04_rfdetr_small_h250_960.json")
    assert spec["training"]["epochs"] == 30
    assert spec["training"]["batch_size"] == 2
    assert spec["training"]["grad_accum_steps"] == 2
    assert spec["training"]["effective_batch_size"] == 4
    # Smoke test runs fast_dev_run=2 without persisting in output_dir
    assert "fast_dev_run" not in spec["training"]


def test_exp04_no_coco_sports_ball_remapping() -> None:
    # H250 class 0 is ball, class 1 is person
    # In standard COCO, sports ball is 32 and person is 0
    spec = load_spec(ROOT / "configs/training/exp04_rfdetr_small_h250_960.json")
    classes = spec["dataset"]["classes"]
    assert classes["0"] == "ball"
    assert classes["1"] == "person"
    assert "32" not in classes


def test_exp04_frozen_exp03_reference_exists_and_matches() -> None:
    doc_path = ROOT / "docs/experiments/exp03_yolo11s_h250_960_b4.json"
    assert doc_path.is_file(), "docs/experiments/exp03_yolo11s_h250_960_b4.json must exist"

    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    assert doc["experiment"] == "exp03_yolo11s_h250_960_b4"
    assert doc["canonical_benchmark_metrics"]["mAP_50"] == 0.7533
    assert doc["canonical_benchmark_metrics"]["macro_f1"] == 0.8061
    assert doc["canonical_benchmark_metrics"]["ball"]["ap50"] == 0.5632
    assert doc["canonical_benchmark_metrics"]["ball"]["recall"] == 0.6526
    assert doc["canonical_benchmark_metrics"]["ball"]["precision"] == 0.6473
    assert doc["canonical_benchmark_metrics"]["ball"]["f1"] == 0.6500
    assert doc["canonical_benchmark_metrics"]["person"]["ap50"] == 0.9435
    assert doc["canonical_benchmark_metrics"]["person"]["recall"] == 0.9464
    assert doc["canonical_benchmark_metrics"]["person"]["precision"] == 0.9785
    assert doc["canonical_benchmark_metrics"]["person"]["f1"] == 0.9622
    assert doc["training"]["checkpoint_best_sha256"] == "46f5f8d94db71ef0786ca15aeb6a7aaea8d7c1c213ec6390002d005f3add518c"

