from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from h250_dataset import (  # noqa: E402
    H250ValidationError,
    parse_h250_yaml,
    validate_h250_dataset,
)
from download_h250 import extract_zip  # noqa: E402
from prepare_exp02_transfer import _copy_verified  # noqa: E402
from run_exp02 import _comparison, _require_mode_consistency, load_spec, parse_args  # noqa: E402


def _build_tiny_h250(root: Path, *, names: str = "  0: ball\n  1: person\n") -> Path:
    root.mkdir(parents=True)
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
        images.mkdir(parents=True)
        labels.mkdir(parents=True)
        (images / "frame.jpg").write_bytes(b"not-decoded-in-structural-test")
        (labels / "frame.txt").write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    return data_yaml


def test_h250_parser_and_structure_support_portable_split_layout(tmp_path: Path) -> None:
    data_yaml = _build_tiny_h250(tmp_path / "h250")

    parsed = parse_h250_yaml(data_yaml)
    summary = validate_h250_dataset(
        data_yaml,
        root=tmp_path / "repo",
        expected_counts={"train": 1, "valid": 1, "test": 1},
    )

    assert parsed["names"] == {0: "ball", 1: "person"}
    assert summary["dataset_role"] == "training"
    assert summary["splits"]["valid"]["images"] == 1
    assert summary["splits"]["valid"]["labels"] == 1


def test_h250_rejects_wrong_classes_and_golden_training_leak(tmp_path: Path) -> None:
    wrong_yaml = _build_tiny_h250(
        tmp_path / "wrong",
        names="  0: person\n  1: ball\n",
    )
    with pytest.raises(H250ValidationError, match="Classes H250 invalides"):
        parse_h250_yaml(wrong_yaml)

    golden_yaml = _build_tiny_h250(tmp_path / "repo/data/golden/h250")
    with pytest.raises(H250ValidationError, match="golden"):
        validate_h250_dataset(
            golden_yaml,
            root=tmp_path / "repo",
            expected_counts={"train": 1, "valid": 1, "test": 1},
        )


def test_exp02_spec_freezes_transfer_hashes_parameters_and_training_role() -> None:
    spec = load_spec(ROOT / "configs/training/exp02_yolo11n_h250_960_b4.json")

    assert spec["status"] == "READY_TO_RUN"
    assert spec["dataset"]["dataset_role"] == "training"
    assert spec["initial_model"]["fresh_start_required"] is True
    assert spec["training"] == {
        "epochs": 50,
        "batch": 4,
        "imgsz": 960,
        "patience": 15,
        "device": "0",
        "workers": 4,
        "seed": 42,
        "deterministic": True,
        "amp": True,
        "close_mosaic": 10,
        "cache": False,
        "exist_ok": True,
        "optimizer": "auto",
        "lr0": 0.01,
        "lrf": 0.01,
        "momentum": 0.937,
        "weight_decay": 0.0005,
        "warmup_epochs": 3.0,
        "warmup_momentum": 0.8,
        "warmup_bias_lr": 0.0,
        "box": 7.5,
        "cls": 0.5,
        "dfl": 1.5,
        "hsv_h": 0.015,
        "hsv_s": 0.7,
        "hsv_v": 0.4,
        "degrees": 0.0,
        "translate": 0.1,
        "scale": 0.5,
        "shear": 0.0,
        "perspective": 0.0,
        "flipud": 0.0,
        "fliplr": 0.5,
        "mosaic": 1.0,
        "mixup": 0.0,
        "copy_paste": 0.0,
    }
    assert "data/golden" in spec["privacy_and_split"]["prohibited_training_sources"]


def test_exp02_modes_are_mutually_exclusive() -> None:
    args = parse_args(["--resume", "--restart"])

    with pytest.raises(H250ValidationError, match="mutuellement exclusifs"):
        _require_mode_consistency(args)


def test_exp02_comparison_uses_frozen_references_without_mutation() -> None:
    current = {
        "mAP_50": 0.7,
        "macro_f1": 0.8,
        "ball": {"precision": 0.6, "recall": 0.5, "f1": 0.545, "ap50": 0.4},
        "person": {"precision": 0.9, "recall": 0.9, "f1": 0.9, "ap50": 0.92},
    }
    reference = {
        "mAP_50": 0.65,
        "macro_f1": 0.75,
        "ball": {"precision": 0.5, "recall": 0.4, "f1": 0.444, "ap50": 0.3},
        "person": {"precision": 0.8, "recall": 0.8, "f1": 0.8, "ap50": 0.82},
    }

    comparison = _comparison(current, reference)

    assert comparison["ball_recall_delta"] == 0.1
    assert comparison["person_ap50_delta"] == 0.1
    assert comparison["map50_delta"] == 0.05


def test_verified_copy_is_idempotent_and_refuses_different_destination(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    destination = tmp_path / "bundle/file.bin"
    source.write_bytes(b"exp02-transfer")
    expected_sha = hashlib.sha256(source.read_bytes()).hexdigest()

    _copy_verified(source, destination, expected_sha)
    _copy_verified(source, destination, expected_sha)
    assert destination.read_bytes() == source.read_bytes()

    destination.write_bytes(b"different")
    with pytest.raises(H250ValidationError, match="Refus d'écraser"):
        _copy_verified(source, destination, expected_sha)


def test_h250_extractor_rejects_path_traversal(tmp_path: Path) -> None:
    archive = tmp_path / "malicious.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../outside.txt", "forbidden")

    with pytest.raises(H250ValidationError, match="hors destination"):
        extract_zip(archive, tmp_path / "target")


def test_committed_exp01_reference_matches_frozen_exp02_reference() -> None:
    exp01 = json.loads(
        (ROOT / "docs/experiments/exp01_yolo11n_h250_640_b4.json").read_text(
            encoding="utf-8"
        )
    )
    spec = load_spec(ROOT / "configs/training/exp02_yolo11n_h250_960_b4.json")

    reference = spec["references"]["exp01"]
    canonical = exp01["canonical_benchmark_metrics"]
    assert canonical["mAP_50"] == reference["mAP_50"]
    assert canonical["macro_f1"] == reference["macro_f1"]
    assert canonical["ball"] == reference["ball"]
    assert canonical["person"] == reference["person"]
