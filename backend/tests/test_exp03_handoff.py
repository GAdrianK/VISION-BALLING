from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from h250_dataset import (  # noqa: E402
    EXPECTED_SPLIT_COUNTS,
    EXPECTED_YOLO11N_SHA256,
    EXPECTED_YOLO11S_SHA256,
    H250ValidationError,
    validate_h250_dataset,
)
from run_exp03 import (  # noqa: E402
    FORBIDDEN_EXP01_BEST_SHA256,
    FORBIDDEN_EXP02_BEST_SHA256,
    _comparison,
    _require_mode_consistency,
    build_preflight,
    load_spec,
    parse_args,
)


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


def test_exp03_spec_freezes_initial_yolo11s_and_training_parameters() -> None:
    spec = load_spec(ROOT / "configs/training/exp03_yolo11s_h250_960_b4.json")

    assert spec["spec_version"] == "1.0.0"
    assert spec["experiment_id"] == "exp03_yolo11s_h250_960_b4"
    assert spec["status"] == "READY_TO_RUN"

    initial_model = spec["initial_model"]
    assert initial_model["model_id"] == "yolo11s"
    assert initial_model["filename"] == "yolo11s.pt"
    assert initial_model["bytes"] == 19313732
    assert initial_model["sha256"] == EXPECTED_YOLO11S_SHA256
    assert initial_model["fresh_start_required"] is True
    assert initial_model["forbidden_initial_checkpoint"] == "EXP-02 best.pt"

    dataset = spec["dataset"]
    assert dataset["expected_split_counts"] == EXPECTED_SPLIT_COUNTS
    assert dataset["classes"] == {"0": "ball", "1": "person"}
    assert dataset["dataset_role"] == "training"


def test_exp03_hyperparameters_strictly_match_exp02_except_model() -> None:
    exp02_spec = json.loads((ROOT / "configs/training/exp02_yolo11n_h250_960_b4.json").read_text(encoding="utf-8"))
    exp03_spec = load_spec(ROOT / "configs/training/exp03_yolo11s_h250_960_b4.json")

    # Hyperparameters must match 1:1
    assert exp03_spec["training"] == exp02_spec["training"]

    training = exp03_spec["training"]
    assert training["epochs"] == 50
    assert training["batch"] == 4
    assert training["imgsz"] == 960
    assert training["patience"] == 15
    assert training["amp"] is True
    assert training["seed"] == 42
    assert training["deterministic"] is True
    assert training["optimizer"] == "auto"
    assert training["lr0"] == 0.01
    assert training["lrf"] == 0.01
    assert training["momentum"] == 0.937
    assert training["weight_decay"] == 0.0005
    assert training["warmup_epochs"] == 3.0
    assert training["box"] == 7.5
    assert training["cls"] == 0.5
    assert training["dfl"] == 1.5
    assert training["mosaic"] == 1.0
    assert training["close_mosaic"] == 10
    assert training["mixup"] == 0.0
    assert training["copy_paste"] == 0.0
    assert training.get("fraction", 1.0) == 1.0

    # Provenance model difference
    assert exp02_spec["initial_model"]["model_id"] == "yolo11n"
    assert exp03_spec["initial_model"]["model_id"] == "yolo11s"


def test_exp03_runner_rejects_exp01_and_exp02_best_pt(tmp_path: Path) -> None:
    data_yaml = _build_tiny_h250(tmp_path / "dataset")
    spec = copy.deepcopy(load_spec(ROOT / "configs/training/exp03_yolo11s_h250_960_b4.json"))
    spec["dataset"]["expected_split_counts"] = {"train": 1, "valid": 1, "test": 1}

    # Test rejection of EXP-01 best.pt
    exp01_fake = tmp_path / "exp01_best.pt"
    exp01_fake.write_bytes(b"exp01_fake")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("run_exp03.sha256_file", lambda p: FORBIDDEN_EXP01_BEST_SHA256)
        args = parse_args(["--data", str(data_yaml), "--weights", str(exp01_fake), "--check-only", "--device", "cpu"])
        with pytest.raises(H250ValidationError, match="interdit d'initialiser depuis EXP-01"):
            build_preflight(args, spec)

    # Test rejection of EXP-02 best.pt
    exp02_fake = tmp_path / "exp02_best.pt"
    exp02_fake.write_bytes(b"exp02_fake")
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("run_exp03.sha256_file", lambda p: FORBIDDEN_EXP02_BEST_SHA256)
        args = parse_args(["--data", str(data_yaml), "--weights", str(exp02_fake), "--check-only", "--device", "cpu"])
        with pytest.raises(H250ValidationError, match="interdit d'initialiser depuis EXP-02"):
            build_preflight(args, spec)


def test_exp03_modes_are_mutually_exclusive() -> None:
    with pytest.raises(H250ValidationError, match="mutuellement exclusifs"):
        _require_mode_consistency(parse_args(["--resume", "--restart"]))
    with pytest.raises(H250ValidationError, match="mutuellement exclusifs"):
        _require_mode_consistency(parse_args(["--resume", "--eval-only"]))
    with pytest.raises(H250ValidationError, match="mutuellement exclusifs"):
        _require_mode_consistency(parse_args(["--smoke-test", "--resume"]))


def test_exp03_comparison_uses_exp02_reference_without_mutation() -> None:
    spec = load_spec(ROOT / "configs/training/exp03_yolo11s_h250_960_b4.json")
    exp02_ref = spec["references"]["exp02"]

    assert exp02_ref["mAP_50"] == 0.7103
    assert exp02_ref["macro_f1"] == 0.7802
    assert exp02_ref["ball"]["ap50"] == 0.4865
    assert exp02_ref["ball"]["precision"] == 0.6289
    assert exp02_ref["ball"]["recall"] == 0.5787
    assert exp02_ref["ball"]["f1"] == 0.6027
    assert exp02_ref["person"]["ap50"] == 0.9341
    assert exp02_ref["person"]["precision"] == 0.9794
    assert exp02_ref["person"]["recall"] == 0.9368
    assert exp02_ref["person"]["f1"] == 0.9576

    current_sample = {
        "mAP_50": 0.7350,
        "macro_f1": 0.8010,
        "ball": {"precision": 0.6500, "recall": 0.6100, "f1": 0.6300, "ap50": 0.5200},
        "person": {"precision": 0.9800, "recall": 0.9400, "f1": 0.9600, "ap50": 0.9400},
    }
    comparison = _comparison(current_sample, exp02_ref)

    assert comparison["ball_ap50_delta"] == round(0.5200 - 0.4865, 4)
    assert comparison["ball_recall_delta"] == round(0.6100 - 0.5787, 4)
    assert comparison["map50_delta"] == round(0.7350 - 0.7103, 4)


def test_exp03_committed_reference_doc_exists_and_matches() -> None:
    doc_path = ROOT / "docs/experiments/exp02_yolo11n_h250_960_b4.json"
    assert doc_path.is_file(), "docs/experiments/exp02_yolo11n_h250_960_b4.json must exist"

    doc = json.loads(doc_path.read_text(encoding="utf-8"))
    assert doc["experiment"] == "exp02_yolo11n_h250_960_b4"
    assert doc["canonical_benchmark_metrics"]["mAP_50"] == 0.7103
    assert doc["canonical_benchmark_metrics"]["macro_f1"] == 0.7802
    assert doc["canonical_benchmark_metrics"]["ball"]["ap50"] == 0.4865
    assert doc["canonical_benchmark_metrics"]["person"]["ap50"] == 0.9341
