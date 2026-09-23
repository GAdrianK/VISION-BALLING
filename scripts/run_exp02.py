#!/usr/bin/env python3
"""Run the portable, reproducible EXP-02 YOLO11n experiment on SoccerNet H250."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from h250_dataset import (  # noqa: E402
    EXPECTED_SPLIT_COUNTS,
    EXPECTED_YOLO11N_SHA256,
    H250ValidationError,
    resolve_data_yaml,
    resolve_runs_dir,
    sha256_file,
    validate_h250_dataset,
    validate_initial_weights,
)


DEFAULT_SPEC = ROOT / "configs/training/exp02_yolo11n_h250_960_b4.json"
DEFAULT_WEIGHTS = ROOT / "yolo11n.pt"
DEFAULT_REPORT_COPY = ROOT / "runs/detect/exp02_yolo11n_960_val_report.json"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="EXP-02 portable : YOLO11n, H250, 960 px, batch 4"
    )
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--data", type=Path, help="Chemin vers H250 data.yaml")
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--runs-dir", type=Path)
    parser.add_argument("--device", default="0", help="Périphérique Ultralytics : 0, 1 ou cpu")
    parser.add_argument("--resume", action="store_true", help="Reprendre depuis last.pt")
    parser.add_argument("--restart", action="store_true", help="Redémarrer explicitement EXP-02")
    parser.add_argument("--eval-only", action="store_true", help="Évaluer le best.pt existant")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Valider le PC, le dataset et les poids sans entraînement",
    )
    parser.add_argument(
        "--report-copy",
        type=Path,
        default=DEFAULT_REPORT_COPY,
        help="Copie JSON locale du rapport final (répertoire runs ignoré par Git)",
    )
    return parser.parse_args(argv)


def load_spec(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise H250ValidationError(f"Spec EXP-02 illisible : {path}: {error}") from error
    if payload.get("spec_version") != "1.0.0":
        raise H250ValidationError("La spec EXP-02 doit être en version 1.0.0")
    if payload.get("experiment_id") != "exp02_yolo11n_h250_960_b4":
        raise H250ValidationError("Identifiant EXP-02 inattendu")
    if payload.get("dataset", {}).get("dataset_role") != "training":
        raise H250ValidationError("EXP-02 exige un dataset portant le rôle training")
    if payload.get("initial_model", {}).get("sha256") != EXPECTED_YOLO11N_SHA256:
        raise H250ValidationError("La spec ne référence pas le yolo11n.pt gelé")
    if payload.get("dataset", {}).get("expected_split_counts") != EXPECTED_SPLIT_COUNTS:
        raise H250ValidationError("Les tailles de splits H250 de la spec sont invalides")
    return payload


def _package_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def _git_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def runtime_info() -> dict[str, Any]:
    info: dict[str, Any] = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "torch": _package_version("torch"),
        "ultralytics": _package_version("ultralytics"),
        "opencv": _package_version("opencv-python-headless") or _package_version("opencv-python"),
        "cuda_available": False,
        "cuda_runtime": None,
        "gpu": None,
        "gpu_memory_bytes": None,
    }
    if importlib.util.find_spec("torch") is None:
        return info
    import torch

    info["cuda_available"] = bool(torch.cuda.is_available())
    info["cuda_runtime"] = torch.version.cuda
    if torch.cuda.is_available():
        info["gpu"] = torch.cuda.get_device_name(0)
        info["gpu_memory_bytes"] = torch.cuda.get_device_properties(0).total_memory
    return info


def build_preflight(args: argparse.Namespace, spec: dict[str, Any]) -> dict[str, Any]:
    data_yaml = resolve_data_yaml(args.data)
    dataset = validate_h250_dataset(data_yaml)
    if dataset["data_yaml_sha256"] != spec["dataset"]["data_yaml_sha256"]:
        raise H250ValidationError(
            "SHA-256 data.yaml invalide : "
            f"expected={spec['dataset']['data_yaml_sha256']} "
            f"actual={dataset['data_yaml_sha256']}"
        )
    weights = validate_initial_weights(
        args.weights,
        expected_sha256=spec["initial_model"]["sha256"],
    )
    runs_dir = resolve_runs_dir(args.runs_dir)
    runtime = runtime_info()
    missing_packages = [
        name for name in ("torch", "ultralytics", "opencv") if not runtime.get(name)
    ]
    needs_cuda = str(args.device).lower() != "cpu"
    ready = not missing_packages and (not needs_cuda or runtime["cuda_available"])
    blockers: list[str] = []
    if missing_packages:
        blockers.append("Dépendances manquantes : " + ", ".join(missing_packages))
    if needs_cuda and not runtime["cuda_available"]:
        blockers.append("PyTorch CUDA indisponible pour --device " + str(args.device))
    if runtime["ultralytics"] != spec["runtime"]["ultralytics"]:
        blockers.append(
            "Version Ultralytics invalide : "
            f"expected={spec['runtime']['ultralytics']} actual={runtime['ultralytics']}"
        )
    ready = not blockers
    return {
        "status": "READY" if ready else "BLOCKED",
        "experiment_id": spec["experiment_id"],
        "git_head": _git_head(),
        "data": dataset,
        "initial_weights": weights,
        "runs_dir": str(runs_dir),
        "runtime": runtime,
        "blockers": blockers,
    }


def _require_mode_consistency(args: argparse.Namespace) -> None:
    enabled = sum(bool(value) for value in (args.resume, args.restart, args.eval_only))
    if enabled > 1:
        raise H250ValidationError("--resume, --restart et --eval-only sont mutuellement exclusifs")


def _metric_class(metrics: Any, label: str) -> dict[str, float]:
    source = metrics.class_metrics.get(label, {})
    return {key: float(source.get(key, 0.0)) for key in ("ap50", "precision", "recall", "f1")}


def _comparison(current: dict[str, Any], reference: dict[str, Any]) -> dict[str, Any]:
    current_ball = current["ball"]
    current_person = current["person"]
    return {
        "ball_precision_reference": reference["ball"]["precision"],
        "ball_precision_current": current_ball["precision"],
        "ball_precision_delta": round(
            current_ball["precision"] - reference["ball"]["precision"], 4
        ),
        "ball_recall_reference": reference["ball"]["recall"],
        "ball_recall_current": current_ball["recall"],
        "ball_recall_delta": round(current_ball["recall"] - reference["ball"]["recall"], 4),
        "ball_f1_reference": reference["ball"]["f1"],
        "ball_f1_current": current_ball["f1"],
        "ball_f1_delta": round(current_ball["f1"] - reference["ball"]["f1"], 4),
        "ball_ap50_reference": reference["ball"]["ap50"],
        "ball_ap50_current": current_ball["ap50"],
        "ball_ap50_delta": round(current_ball["ap50"] - reference["ball"]["ap50"], 4),
        "person_f1_reference": reference["person"]["f1"],
        "person_f1_current": current_person["f1"],
        "person_f1_delta": round(current_person["f1"] - reference["person"]["f1"], 4),
        "person_ap50_reference": reference["person"]["ap50"],
        "person_ap50_current": current_person["ap50"],
        "person_ap50_delta": round(current_person["ap50"] - reference["person"]["ap50"], 4),
        "macro_f1_reference": reference["macro_f1"],
        "macro_f1_current": current["macro_f1"],
        "macro_f1_delta": round(current["macro_f1"] - reference["macro_f1"], 4),
        "map50_reference": reference["mAP_50"],
        "map50_current": current["mAP_50"],
        "map50_delta": round(current["mAP_50"] - reference["mAP_50"], 4),
    }


def run_experiment(
    args: argparse.Namespace,
    spec: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    import cv2
    import torch
    from ultralytics import YOLO

    from app.video_analysis.benchmark_adapters import SOCCERNET_H250_CLASS_MAP, YOLOAdapter
    from app.video_analysis.benchmark_metrics import DetectionEvaluator, MemoryTracker
    from app.video_analysis.detectors import create_detector

    train_config = spec["training"]
    data_yaml = Path(preflight["data"]["data_yaml"])
    weights = Path(preflight["initial_weights"]["path"])
    runs_dir = Path(preflight["runs_dir"])
    experiment_name = spec["experiment_id"]
    experiment_dir = runs_dir / experiment_name
    last_weights = experiment_dir / "weights/last.pt"
    best_weights = experiment_dir / "weights/best.pt"

    if args.resume and not last_weights.is_file():
        raise H250ValidationError(f"Checkpoint de reprise introuvable : {last_weights}")
    if args.eval_only and not best_weights.is_file():
        raise H250ValidationError(f"Checkpoint d'évaluation introuvable : {best_weights}")
    if not any((args.resume, args.restart, args.eval_only)) and experiment_dir.exists():
        raise H250ValidationError(
            f"Le run existe déjà : {experiment_dir}. Utiliser --resume, --restart ou --eval-only."
        )

    print("=" * 72)
    print("EXP-02 — YOLO11n / H250 / 960 px / batch 4")
    print(f"Dataset : {data_yaml}")
    print(f"Poids initiaux gelés : {weights}")
    print(f"Sortie : {experiment_dir}")
    print(f"Device : {args.device} ({preflight['runtime'].get('gpu') or 'CPU'})")
    print("=" * 72)

    session_duration = 0.0
    peak_vram_allocated_mb = 0.0
    peak_vram_reserved_mb = 0.0
    if not args.eval_only:
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()
        if args.resume:
            model = YOLO(str(last_weights))
            model.train(resume=True, device=args.device)
        else:
            model = YOLO(str(weights))
            model.train(
                data=str(data_yaml),
                epochs=train_config["epochs"],
                batch=train_config["batch"],
                imgsz=train_config["imgsz"],
                patience=train_config["patience"],
                device=args.device,
                workers=train_config["workers"],
                seed=train_config["seed"],
                deterministic=train_config["deterministic"],
                amp=train_config["amp"],
                close_mosaic=train_config["close_mosaic"],
                cache=train_config["cache"],
                optimizer=train_config["optimizer"],
                lr0=train_config["lr0"],
                lrf=train_config["lrf"],
                momentum=train_config["momentum"],
                weight_decay=train_config["weight_decay"],
                warmup_epochs=train_config["warmup_epochs"],
                warmup_momentum=train_config["warmup_momentum"],
                warmup_bias_lr=train_config["warmup_bias_lr"],
                box=train_config["box"],
                cls=train_config["cls"],
                dfl=train_config["dfl"],
                hsv_h=train_config["hsv_h"],
                hsv_s=train_config["hsv_s"],
                hsv_v=train_config["hsv_v"],
                degrees=train_config["degrees"],
                translate=train_config["translate"],
                scale=train_config["scale"],
                shear=train_config["shear"],
                perspective=train_config["perspective"],
                flipud=train_config["flipud"],
                fliplr=train_config["fliplr"],
                mosaic=train_config["mosaic"],
                mixup=train_config["mixup"],
                copy_paste=train_config["copy_paste"],
                project=str(runs_dir),
                name=experiment_name,
                exist_ok=train_config["exist_ok"],
            )
        session_duration = time.monotonic() - started
        if torch.cuda.is_available():
            peak_vram_allocated_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
            peak_vram_reserved_mb = torch.cuda.max_memory_reserved() / (1024 * 1024)

    if not best_weights.is_file():
        raise H250ValidationError(f"Poids optimaux introuvables après entraînement : {best_weights}")

    print("Évaluation native Ultralytics...")
    val_model = YOLO(str(best_weights))
    val_metrics = val_model.val(
        data=str(data_yaml),
        split="val",
        imgsz=train_config["imgsz"],
        device=args.device,
        project=str(runs_dir),
        name=f"{experiment_name}_val",
        exist_ok=True,
    )

    valid = preflight["data"]["splits"]["valid"]
    adapter = YOLOAdapter(
        labels_dir=Path(valid["labels_dir"]),
        images_dir=Path(valid["images_dir"]),
    )
    dataset = adapter.load_dataset()
    detector = create_detector(
        "yolo",
        model_path=str(best_weights),
        device=args.device,
        class_map=SOCCERNET_H250_CLASS_MAP,
    )
    detector.load()
    predictions_by_frame: dict[int, list[Any]] = {}
    evaluation_started = time.monotonic()
    with MemoryTracker() as memory_tracker:
        for index, frame_gt in enumerate(dataset, start=1):
            image = cv2.imread(str(frame_gt.image_path))
            if image is None:
                raise H250ValidationError(f"Image illisible : {frame_gt.image_path}")
            predictions_by_frame[frame_gt.frame_index] = detector.detect(image)
            if index % 500 == 0 or index == len(dataset):
                elapsed = time.monotonic() - evaluation_started
                print(f"Benchmark {index}/{len(dataset)} ({index / max(elapsed, 0.001):.1f} FPS)")
        evaluation_duration = time.monotonic() - evaluation_started
        peak_rss_mb = memory_tracker.get_peak_rss_mb()

    metrics = DetectionEvaluator(iou_threshold=spec["evaluation"]["iou_threshold"]).evaluate(
        ground_truth=dataset,
        predictions_by_frame=predictions_by_frame,
        duration_seconds=evaluation_duration,
        peak_rss_mb=peak_rss_mb,
    )
    canonical = {
        "mAP_50": float(metrics.mAP_50),
        "macro_f1": float(metrics.macro_f1),
        "overall_precision": float(metrics.precision),
        "overall_recall": float(metrics.recall),
        "overall_f1": float(metrics.f1_score),
        "ball": _metric_class(metrics, "sports ball"),
        "person": _metric_class(metrics, "person"),
        "fps": float(metrics.fps),
        "duration_seconds": float(metrics.total_seconds),
        "peak_rss_mb": float(metrics.peak_rss_mb),
    }
    report = {
        "experiment": experiment_name,
        "status": "COMPLETED",
        "git_head": preflight["git_head"],
        "spec": str(args.spec.resolve()),
        "dataset": preflight["data"],
        "initial_weights": preflight["initial_weights"],
        "best_checkpoint": {
            "path": str(best_weights),
            "bytes": best_weights.stat().st_size,
            "sha256": sha256_file(best_weights),
        },
        "runtime": preflight["runtime"],
        "training": {
            **train_config,
            "session_duration_seconds": round(session_duration, 3),
            "peak_vram_allocated_mb": round(peak_vram_allocated_mb, 3),
            "peak_vram_reserved_mb": round(peak_vram_reserved_mb, 3),
        },
        "ultralytics_val": {
            "map50": round(float(val_metrics.box.map50), 6),
            "map50_95": round(float(val_metrics.box.map), 6),
            "precision": round(float(val_metrics.box.mp), 6),
            "recall": round(float(val_metrics.box.mr), 6),
            "per_class_map50": [round(float(value), 6) for value in val_metrics.box.ap50],
            "per_class_map50_95": [
                round(float(value), 6) for value in val_metrics.box.maps
            ],
        },
        "canonical_benchmark_metrics": canonical,
        "comparison_vs_exp01": _comparison(canonical, spec["references"]["exp01"]),
        "comparison_vs_exp00": _comparison(canonical, spec["references"]["exp00"]),
    }
    report_path = experiment_dir / "exp02_evaluation_report.json"
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    if args.report_copy:
        args.report_copy.parent.mkdir(parents=True, exist_ok=True)
        args.report_copy.write_text(
            json.dumps(report, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    print(
        json.dumps(
            {"status": "COMPLETED", "report": str(report_path), "metrics": canonical},
            indent=2,
        )
    )
    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        _require_mode_consistency(args)
        spec = load_spec(args.spec)
        preflight = build_preflight(args, spec)
        if args.check_only:
            print(json.dumps(preflight, indent=2, ensure_ascii=False))
            return 0 if preflight["status"] == "READY" else 2
        if preflight["status"] != "READY":
            raise H250ValidationError("; ".join(preflight["blockers"]))
        run_experiment(args, spec, preflight)
        return 0
    except (H250ValidationError, KeyError, OSError, ValueError) as error:
        print(f"FAIL — {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
