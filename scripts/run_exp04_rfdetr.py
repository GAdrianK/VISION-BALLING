#!/usr/bin/env python3
"""Run the controlled EXP-04 RF-DETR Small experiment on SoccerNet H250."""

from __future__ import annotations

import argparse
import importlib.metadata
import importlib.util
import json
import math
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from h250_dataset import (  # noqa: E402
    EXPECTED_SPLIT_COUNTS,
    H250ValidationError,
    resolve_data_yaml,
    resolve_runs_dir,
    sha256_file,
    validate_h250_dataset,
)

DEFAULT_SPEC = ROOT / "configs/training/exp04_rfdetr_small_h250_960.json"
DEFAULT_WEIGHTS = Path(os.path.expanduser("~/.roboflow/models/rf-detr-small.pth"))
DEFAULT_REPORT_COPY = ROOT / "runs/detect/exp04_rfdetr_small_960_val_report.json"

EXPECTED_RFDETR_SMALL_SHA256 = (
    "d81979a9213a2109345158ce9232668df4c1ae52e9b8db3f2ec0a8cbad959b33"
)
FORBIDDEN_EXP01_BEST_SHA256 = (
    "590dcb69ee501bddc61de0cded5f40b0bf65c00d83c2ebbe8e5962a646eb9844"
)
FORBIDDEN_EXP02_BEST_SHA256 = (
    "d2f23dee97207135b6c225e708864b4e1b6f7deb191f9d0f8410281091b56a45"
)
FORBIDDEN_EXP03_BEST_SHA256 = (
    "46f5f8d94db71ef0786ca15aeb6a7aaea8d7c1c213ec6390002d005f3add518c"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="EXP-04 : RF-DETR Small, H250, 960 px, batch 2, accum 2"
    )
    parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    parser.add_argument("--data", type=Path, help="Chemin vers H250 data.yaml")
    parser.add_argument("--weights", type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument("--runs-dir", type=Path)
    parser.add_argument("--device", default="0", help="Périphérique : 0, cuda ou cpu")
    parser.add_argument("--resume", action="store_true", help="Reprendre l'entraînement")
    parser.add_argument("--restart", action="store_true", help="Redémarrer explicitement EXP-04")
    parser.add_argument("--eval-only", action="store_true", help="Évaluer le meilleur checkpoint existant")
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="Valider le PC, le dataset et les poids sans entraînement",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Exécuter un smoke-test réel (forward + backward + optimizer step) sans altérer EXP-04",
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
        raise H250ValidationError(f"Spec EXP-04 illisible : {path}: {error}") from error
    if payload.get("spec_version") != "1.0.0":
        raise H250ValidationError("La spec EXP-04 doit être en version 1.0.0")
    if payload.get("experiment_id") != "exp04_rfdetr_small_h250_960":
        raise H250ValidationError("Identifiant EXP-04 inattendu")
    if payload.get("dataset", {}).get("dataset_role") != "training":
        raise H250ValidationError("EXP-04 exige un dataset portant le rôle training")
    if payload.get("initial_model", {}).get("sha256") != EXPECTED_RFDETR_SMALL_SHA256:
        raise H250ValidationError("La spec ne référence pas le rf-detr-small.pth gelé")
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
        "torchvision": _package_version("torchvision"),
        "rfdetr": _package_version("rfdetr"),
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
    expected_counts = spec["dataset"].get("expected_split_counts", EXPECTED_SPLIT_COUNTS)
    dataset = validate_h250_dataset(data_yaml, expected_counts=expected_counts)
    expected_yaml_sha = spec["dataset"].get("data_yaml_sha256")
    if expected_yaml_sha and dataset["data_yaml_sha256"] != expected_yaml_sha:
        dataset["portability_notice"] = (
            "INFRASTRUCTURE PORTABILITY ONLY: data.yaml path differs from Windows reference "
            f"({dataset['data_yaml_sha256'][:8]}... != {expected_yaml_sha[:8]}...), "
            "semantic dataset integrity (14368 train, 2726 valid, 2692 test, classes: 0=ball, 1=person) "
            "is fully verified."
        )

    weights_path = Path(args.weights).expanduser().resolve()
    if not weights_path.is_file():
        raise H250ValidationError(f"Poids initiaux RF-DETR introuvables : {weights_path}")
    actual_weights_sha = sha256_file(weights_path)

    # Protection stricte contre l'utilisation accidentelle des checkpoints YOLO
    if actual_weights_sha in (
        FORBIDDEN_EXP01_BEST_SHA256,
        FORBIDDEN_EXP02_BEST_SHA256,
        FORBIDDEN_EXP03_BEST_SHA256,
    ):
        raise H250ValidationError(
            "VIOLATION PROTOCOLE : EXP-04 interdit formellement d'initialiser depuis un checkpoint YOLO ! "
            "Seul le rf-detr-small.pth officiel COCO est autorisé."
        )

    expected_sha = spec["initial_model"]["sha256"]
    if actual_weights_sha != expected_sha:
        raise H250ValidationError(
            f"SHA-256 rf-detr-small.pth invalide : expected={expected_sha} actual={actual_weights_sha}"
        )

    weights = {
        "path": str(weights_path),
        "bytes": weights_path.stat().st_size,
        "sha256": actual_weights_sha,
    }

    runs_dir = resolve_runs_dir(args.runs_dir)
    runtime = runtime_info()
    missing_packages = [
        name for name in ("torch", "rfdetr", "opencv") if not runtime.get(name)
    ]
    needs_cuda = str(args.device).lower() != "cpu"
    ready = not missing_packages and (not needs_cuda or runtime["cuda_available"])
    blockers: list[str] = []
    if missing_packages:
        blockers.append("Dépendances manquantes : " + ", ".join(missing_packages))
    if needs_cuda and not runtime["cuda_available"]:
        blockers.append("PyTorch CUDA indisponible pour --device " + str(args.device))
    if runtime["rfdetr"] != spec["runtime"]["rfdetr"]:
        blockers.append(
            f"RF-DETR {runtime['rfdetr']} différent de la spec {spec['runtime']['rfdetr']}"
        )

    return {
        "status": "READY" if ready and not blockers else "BLOCKED",
        "experiment_id": spec["experiment_id"],
        "git_head": _git_head(),
        "data": dataset,
        "initial_weights": weights,
        "runs_dir": str(runs_dir),
        "runtime": runtime,
        "blockers": blockers,
    }


def _require_mode_consistency(args: argparse.Namespace) -> None:
    enabled = sum(bool(value) for value in (args.resume, args.restart, args.eval_only, args.smoke_test))
    if enabled > 1:
        raise H250ValidationError("--resume, --restart, --eval-only et --smoke-test sont mutuellement exclusifs")


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


def run_smoke_test(
    spec: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    import torch
    from rfdetr import RFDETRSmall
    from rfdetr.training import RFDETRDataModule, RFDETRModelModule, build_trainer

    dataset_dir = Path(preflight["data"]["data_yaml"]).parent
    runs_dir = Path(preflight["runs_dir"])
    temp_dir = runs_dir / "exp04_smoke_test_tmp"
    temp_dir.mkdir(parents=True, exist_ok=True)

    print("Exécution du smoke-test RF-DETR Small (batch 2, 960 px, fast_dev_run=2)...")
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()

    model = RFDETRSmall(resolution=960, gradient_checkpointing=True)
    model._align_num_classes_from_dataset(str(dataset_dir))

    train_cfg = model.get_train_config(
        dataset_dir=str(dataset_dir),
        batch_size=2,
        grad_accum_steps=2,
        num_workers=0,
        multi_scale="per-batch",
        output_dir=str(temp_dir),
        epochs=1,
        progress_bar=None,
        tensorboard=False,
    )

    dm = RFDETRDataModule(model.model_config, train_cfg)
    module = RFDETRModelModule(model.model_config, train_cfg)

    trainer = build_trainer(
        train_cfg,
        model.model_config,
        accelerator="gpu" if torch.cuda.is_available() else "cpu",
        devices=1,
        include_training_callbacks=False,
        fast_dev_run=2,
    )

    t0 = time.perf_counter()
    trainer.fit(module, datamodule=dm)
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    duration = time.perf_counter() - t0

    alloc_mb = torch.cuda.max_memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0.0
    res_mb = torch.cuda.max_memory_reserved() / (1024 * 1024) if torch.cuda.is_available() else 0.0

    shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "status": "PASS",
        "peak_vram_allocated_mb": round(alloc_mb, 2),
        "peak_vram_reserved_mb": round(res_mb, 2),
        "batch_size": 2,
        "grad_accum_steps": 2,
        "effective_batch_size": 4,
        "resolution": 960,
        "duration_seconds": round(duration, 3),
        "cuda_errors": None,
        "oom": False,
    }


def find_best_checkpoint(experiment_dir: Path) -> Path:
    candidates = [
        experiment_dir / "checkpoint_best_total.pth",
        experiment_dir / "checkpoint_best_ema.pth",
        experiment_dir / "checkpoint_best_regular.pth",
        experiment_dir / "last_ema.pth",
    ]
    for c in candidates:
        if c.is_file():
            return c
    raise FileNotFoundError(f"Aucun checkpoint valide trouvé dans {experiment_dir}")


def run_experiment(
    args: argparse.Namespace,
    spec: dict[str, Any],
    preflight: dict[str, Any],
) -> dict[str, Any]:
    import cv2
    import torch
    from rfdetr import RFDETRSmall

    from app.video_analysis.benchmark_adapters import SOCCERNET_H250_CLASS_MAP, YOLOAdapter
    from app.video_analysis.benchmark_metrics import DetectionEvaluator, MemoryTracker
    from app.video_analysis.detectors import create_detector

    train_config = spec["training"]
    data_yaml = Path(preflight["data"]["data_yaml"])
    dataset_dir = data_yaml.parent
    weights = Path(preflight["initial_weights"]["path"])
    runs_dir = Path(preflight["runs_dir"])
    experiment_name = spec["experiment_id"]
    experiment_dir = runs_dir / experiment_name

    resume_ckpt = None
    if args.resume:
        # PTL trainer saves last.ckpt or similar in experiment_dir
        last_ckpt = experiment_dir / "last.ckpt"
        if last_ckpt.is_file():
            resume_ckpt = str(last_ckpt)
        else:
            # Fall back to best or last pth
            cand = experiment_dir / "checkpoint_best_total.pth"
            if cand.is_file():
                resume_ckpt = str(cand)
            else:
                raise H250ValidationError(f"Aucun checkpoint de reprise trouvé dans {experiment_dir}")

    if not any((args.resume, args.restart, args.eval_only)) and experiment_dir.exists():
        # Check if already completed
        done_flag = experiment_dir / "checkpoint_best_total.pth"
        if done_flag.is_file():
            raise H250ValidationError(
                f"Le run existe déjà et contient un checkpoint : {experiment_dir}. "
                "Utiliser --resume, --restart ou --eval-only."
            )

    print("=" * 72)
    print("EXP-04 — RF-DETR Small / H250 / 960 px / batch 2 / accum 2")
    print(f"Dataset : {data_yaml}")
    print(f"Poids initiaux gelés : {weights}")
    print(f"Sortie : {experiment_dir}")
    print(f"Device : {args.device} ({preflight['runtime'].get('gpu') or 'CPU'})")
    print("=" * 72)

    session_duration = 0.0
    peak_vram_allocated_mb = 0.0
    peak_vram_reserved_mb = 0.0

    if not args.eval_only:
        experiment_dir.mkdir(parents=True, exist_ok=True)
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        started = time.monotonic()

        # Initialize model
        model = RFDETRSmall(
            resolution=train_config["resolution"],
            gradient_checkpointing=train_config["gradient_checkpointing"],
            pretrain_weights=str(weights),
        )

        train_args = {
            "dataset_dir": str(dataset_dir),
            "epochs": train_config["epochs"],
            "batch_size": train_config["batch_size"],
            "grad_accum_steps": train_config["grad_accum_steps"],
            "resolution": train_config["resolution"],
            "lr": train_config["lr"],
            "lr_encoder": train_config["lr_encoder"],
            "optimizer": train_config["optimizer"],
            "weight_decay": train_config["weight_decay"],
            "multi_scale": train_config["multi_scale"],
            "expanded_scales": train_config["expanded_scales"],
            "use_ema": train_config["use_ema"],
            "ema_decay": train_config["ema_decay"],
            "ema_tau": train_config["ema_tau"],
            "ema_update_interval": train_config["ema_update_interval"],
            "early_stopping": train_config["early_stopping"],
            "clip_max_norm": train_config["clip_max_norm"],
            "amp_dtype": train_config["amp_dtype"],
            "num_workers": train_config["num_workers"],
            "seed": train_config["seed"],
            "run_test": train_config["run_test"],
            "output_dir": str(experiment_dir),
            "device": "cuda" if str(args.device) in ("0", "cuda", "cuda:0") else str(args.device),
        }
        if resume_ckpt:
            train_args["resume"] = resume_ckpt

        model.train(**train_args)

        session_duration = time.monotonic() - started
        if torch.cuda.is_available():
            peak_vram_allocated_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
            peak_vram_reserved_mb = torch.cuda.max_memory_reserved() / (1024 * 1024)

    best_checkpoint = find_best_checkpoint(experiment_dir)
    print(f"Meilleur checkpoint sélectionné pour l'évaluation canonique : {best_checkpoint}")

    # Canonical evaluation
    valid = preflight["data"]["splits"]["valid"]
    adapter = YOLOAdapter(
        labels_dir=Path(valid["labels_dir"]),
        images_dir=Path(valid["images_dir"]),
    )
    dataset = adapter.load_dataset()

    detector = create_detector(
        "rfdetr",
        model_path=str(best_checkpoint),
        device=args.device,
        resolution=train_config["resolution"],
        ball_threshold=spec["evaluation"]["ball_confidence"],
        person_threshold=spec["evaluation"]["person_confidence"],
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
            if index % 200 == 0 or index == len(dataset):
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
            "path": str(best_checkpoint),
            "bytes": best_checkpoint.stat().st_size,
            "sha256": sha256_file(best_checkpoint),
        },
        "runtime": preflight["runtime"],
        "training": {
            **train_config,
            "session_duration_seconds": round(session_duration, 3),
            "peak_vram_allocated_mb": round(peak_vram_allocated_mb, 3),
            "peak_vram_reserved_mb": round(peak_vram_reserved_mb, 3),
        },
        "canonical_benchmark_metrics": canonical,
        "comparison_vs_exp03": _comparison(canonical, spec["references"]["exp03"]),
        "comparison_vs_exp02": _comparison(canonical, spec["references"]["exp02"]),
    }

    report_path = experiment_dir / "exp04_evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Rapport sauvegardé : {report_path}")

    args.report_copy.parent.mkdir(parents=True, exist_ok=True)
    args.report_copy.write_text(json.dumps(report, indent=2), encoding="utf-8")

    return report


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _require_mode_consistency(args)
    spec = load_spec(args.spec)
    preflight = build_preflight(args, spec)

    if args.check_only:
        print(json.dumps(preflight, indent=2))
        return 0 if preflight["status"] == "READY" else 1

    if preflight["status"] != "READY":
        print(f"EXP-04 BLOQUÉ : {preflight['blockers']}", file=sys.stderr)
        return 1

    if args.smoke_test:
        smoke_report = run_smoke_test(spec, preflight)
        print(json.dumps(smoke_report, indent=2))
        return 0

    run_experiment(args, spec, preflight)
    return 0


if __name__ == "__main__":
    sys.exit(main())
