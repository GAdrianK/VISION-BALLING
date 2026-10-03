#!/usr/bin/env python3
"""Exécute l'expérience EXP-01 : fine-tuning complet YOLO11n à 640px sur SoccerNet H250."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch
from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.video_analysis.benchmark_adapters import (  # noqa: E402
    SOCCERNET_H250_CLASS_MAP,
    YOLOAdapter,
)
from app.video_analysis.benchmark_metrics import (  # noqa: E402
    DetectionEvaluator,
    MemoryTracker,
)
from app.video_analysis.detectors import create_detector  # noqa: E402

DATA_YAML = Path("D:/datasets/h250/YOLO/data.yaml")
RUNS_DIR = Path("D:/runs/detect")
EXP_NAME = "exp01_yolo11n_h250_640_b4"
EXP_DIR = RUNS_DIR / EXP_NAME
VALID_LABELS = Path("D:/datasets/h250/YOLO/valid/labels")
VALID_IMAGES = Path("D:/datasets/h250/YOLO/valid/images")

# Baseline verrouillée EXP-00
EXP00_BASELINE = {
    "ball": {
        "precision": 0.5415,
        "recall": 0.0948,
        "f1": 0.1613,
        "ap50": 0.0690,
    },
    "person": {
        "precision": 0.9553,
        "recall": 0.6787,
        "f1": 0.7935,
        "ap50": 0.6691,
    },
    "macro_f1": 0.4774,
    "mAP_50": 0.3691,
}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="EXP-01 YOLO11n 640px")
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")
    parser.add_argument("--restart", action="store_true", help="Restart from scratch")
    parser.add_argument("--eval-only", action="store_true", help="Only run validation and benchmark on best.pt")
    args = parser.parse_args()

    last_weights = EXP_DIR / "weights" / "last.pt"
    should_resume = (args.resume or last_weights.is_file()) and not args.restart and not args.eval_only

    if not args.eval_only:
        print("=================================================================")
        if should_resume:
            print("        REPRISE DE L'EXPÉRIENCE EXP-01 (640px / Batch 4)         ")
        else:
            print("        LANCEMENT DE L'EXPÉRIENCE EXP-01 (640px / Batch 4)       ")
        print("=================================================================")
        print(f"Dataset : {DATA_YAML}")
        print(f"Modèle initial : {last_weights if should_resume else 'yolo11n.pt'}")
        print(f"Résolution : 640x640, Batch : 4, Époques : 50, Patience : 15")
        print(f"Périphérique : CUDA:0 ({torch.cuda.get_device_name(0)})")
        print(f"Dossier de sortie : {EXP_DIR}")
        print("-----------------------------------------------------------------")

        torch.cuda.reset_peak_memory_stats()
        train_start_time = time.monotonic()

        if should_resume:
            print(f"[*] Reprise de l'entraînement depuis {last_weights}...")
            model = YOLO(str(last_weights))
            train_res = model.train(resume=True)
        else:
            model = YOLO("yolo11n.pt")
            train_res = model.train(
                data=str(DATA_YAML),
                epochs=50,
                batch=4,
                imgsz=640,
                patience=15,
                device=0,
                workers=4,
                seed=42,
                deterministic=True,
                amp=True,
                close_mosaic=10,
                project=str(RUNS_DIR),
                name=EXP_NAME,
                exist_ok=True,
            )

        train_duration = time.monotonic() - train_start_time
        peak_vram_alloc_mb = torch.cuda.max_memory_allocated() / (1024 * 1024)
        peak_vram_res_mb = torch.cuda.max_memory_reserved() / (1024 * 1024)

        print("\n[✓] Entraînement terminé !")
        print(f"Durée totale entraînement : {train_duration / 60:.2f} minutes ({train_duration:.1f} s)")
        print(f"Pic VRAM allouée : {peak_vram_alloc_mb:.2f} Mo ({peak_vram_alloc_mb/1024:.2f} Go)")
        print(f"Pic VRAM réservée : {peak_vram_res_mb:.2f} Mo ({peak_vram_res_mb/1024:.2f} Go)")
    else:
        train_duration = 0.0
        peak_vram_alloc_mb = 0.0
        peak_vram_res_mb = 0.0

    best_weights = EXP_DIR / "weights" / "best.pt"
    if not best_weights.is_file():
        raise FileNotFoundError(f"Poids optimaux introuvables : {best_weights}")

    print(f"[✓] Checkpoint optimal préservé : {best_weights} ({best_weights.stat().st_size / (1024*1024):.2f} Mo)")

    # 1. Évaluation native Ultralytics val
    print("\n[*] Exécution de l'évaluation native Ultralytics val()...")
    val_model = YOLO(str(best_weights))
    val_metrics = val_model.val(
        data=str(DATA_YAML),
        split="val",
        imgsz=640,
        device=0,
        project=str(RUNS_DIR),
        name=f"{EXP_NAME}_val",
        exist_ok=True,
    )

    # 2. Évaluation avec l'évaluateur canonique du repo (aligné EXP-00)
    print("\n[*] Exécution de l'évaluation canonique (benchmark_sprint2_1) pour comparaison exacte...")
    adapter = YOLOAdapter(labels_dir=VALID_LABELS, images_dir=VALID_IMAGES)
    dataset = adapter.load_dataset()
    print(f"    - Frames à évaluer : {len(dataset)}")

    eval_detector = create_detector(
        "yolo",
        model_path=str(best_weights),
        device="0",
        class_map=SOCCERNET_H250_CLASS_MAP,
    )
    eval_detector.load()

    eval_start_time = time.monotonic()
    predictions_by_frame: dict[int, list] = {}
    with MemoryTracker() as mem_tracker:
        total_count = len(dataset)
        for idx, frame_gt in enumerate(dataset):
            import cv2
            img = cv2.imread(str(frame_gt.image_path))
            if img is None:
                raise ValueError(f"Image illisible : {frame_gt.image_path}")
            preds = eval_detector.detect(img)
            predictions_by_frame[frame_gt.frame_index] = preds
            if (idx + 1) % 500 == 0 or (idx + 1) == total_count:
                elapsed = time.monotonic() - eval_start_time
                fps_curr = (idx + 1) / max(0.001, elapsed)
                print(f"      [Évaluation EXP-01] Frame {idx + 1}/{total_count} ({fps_curr:.1f} FPS)")

        eval_duration = time.monotonic() - eval_start_time
        peak_rss_mb = mem_tracker.get_peak_rss_mb()

    evaluator = DetectionEvaluator(iou_threshold=0.5)
    metrics = evaluator.evaluate(
        ground_truth=dataset,
        predictions_by_frame=predictions_by_frame,
        duration_seconds=eval_duration,
        peak_rss_mb=peak_rss_mb,
    )

    exp01_ball = metrics.class_metrics.get("sports ball", {})
    exp01_person = metrics.class_metrics.get("person", {})

    report = {
        "experiment": EXP_NAME,
        "model_id": "yolo11n",
        "resolution": 640,
        "batch_size": 4,
        "training": {
            "duration_seconds": round(train_duration, 1),
            "peak_vram_allocated_mb": round(peak_vram_alloc_mb, 2),
            "peak_vram_reserved_mb": round(peak_vram_res_mb, 2),
            "checkpoint_best": str(best_weights),
        },
        "ultralytics_val": {
            "map50": round(float(val_metrics.box.map50), 4),
            "map50_95": round(float(val_metrics.box.map), 4),
            "precision": round(float(val_metrics.box.mp), 4),
            "recall": round(float(val_metrics.box.mr), 4),
            "per_class_map50": [round(float(x), 4) for x in val_metrics.box.ap50],
            "per_class_map50_95": [round(float(x), 4) for x in val_metrics.box.maps],
        },
        "canonical_benchmark_metrics": {
            "mAP_50": metrics.mAP_50,
            "macro_f1": metrics.macro_f1,
            "overall_precision": metrics.precision,
            "overall_recall": metrics.recall,
            "overall_f1": metrics.f1_score,
            "ball": exp01_ball,
            "person": exp01_person,
            "fps": metrics.fps,
            "duration_seconds": metrics.total_seconds,
            "peak_rss_mb": metrics.peak_rss_mb,
        },
        "comparison_vs_exp00": {
            "ball_recall_exp00": EXP00_BASELINE["ball"]["recall"],
            "ball_recall_exp01": exp01_ball.get("recall", 0.0),
            "ball_recall_delta": round(exp01_ball.get("recall", 0.0) - EXP00_BASELINE["ball"]["recall"], 4),
            "ball_ap50_exp00": EXP00_BASELINE["ball"]["ap50"],
            "ball_ap50_exp01": exp01_ball.get("ap50", 0.0),
            "ball_ap50_delta": round(exp01_ball.get("ap50", 0.0) - EXP00_BASELINE["ball"]["ap50"], 4),
            "person_ap50_exp00": EXP00_BASELINE["person"]["ap50"],
            "person_ap50_exp01": exp01_person.get("ap50", 0.0),
            "person_ap50_delta": round(exp01_person.get("ap50", 0.0) - EXP00_BASELINE["person"]["ap50"], 4),
            "macro_f1_exp00": EXP00_BASELINE["macro_f1"],
            "macro_f1_exp01": metrics.macro_f1,
            "macro_f1_delta": round(metrics.macro_f1 - EXP00_BASELINE["macro_f1"], 4),
            "map50_exp00": EXP00_BASELINE["mAP_50"],
            "map50_exp01": metrics.mAP_50,
            "map50_delta": round(metrics.mAP_50 - EXP00_BASELINE["mAP_50"], 4),
        },
    }

    report_path = EXP_DIR / "exp01_evaluation_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[✓] Rapport complet enregistré dans : {report_path}")

    print("\n=================================================================")
    print("              RÉSULTATS COMPARATIFS EXP-00 vs EXP-01              ")
    print("=================================================================")
    print(f"{'Métrique':<24} | {'EXP-00 (COCO)':<15} | {'EXP-01 (640px)':<15} | {'Delta':<10}")
    print("-" * 72)
    print(f"{'Ball Precision':<24} | {EXP00_BASELINE['ball']['precision']:<15.4f} | {exp01_ball.get('precision', 0):<15.4f} | {exp01_ball.get('precision', 0) - EXP00_BASELINE['ball']['precision']:+.4f}")
    print(f"{'Ball Recall':<24} | {EXP00_BASELINE['ball']['recall']:<15.4f} | {exp01_ball.get('recall', 0):<15.4f} | {exp01_ball.get('recall', 0) - EXP00_BASELINE['ball']['recall']:+.4f}")
    print(f"{'Ball F1':<24} | {EXP00_BASELINE['ball']['f1']:<15.4f} | {exp01_ball.get('f1', 0):<15.4f} | {exp01_ball.get('f1', 0) - EXP00_BASELINE['ball']['f1']:+.4f}")
    print(f"{'Ball AP@50':<24} | {EXP00_BASELINE['ball']['ap50']:<15.4f} | {exp01_ball.get('ap50', 0):<15.4f} | {exp01_ball.get('ap50', 0) - EXP00_BASELINE['ball']['ap50']:+.4f}")
    print("-" * 72)
    print(f"{'Person Precision':<24} | {EXP00_BASELINE['person']['precision']:<15.4f} | {exp01_person.get('precision', 0):<15.4f} | {exp01_person.get('precision', 0) - EXP00_BASELINE['person']['precision']:+.4f}")
    print(f"{'Person Recall':<24} | {EXP00_BASELINE['person']['recall']:<15.4f} | {exp01_person.get('recall', 0):<15.4f} | {exp01_person.get('recall', 0) - EXP00_BASELINE['person']['recall']:+.4f}")
    print(f"{'Person F1':<24} | {EXP00_BASELINE['person']['f1']:<15.4f} | {exp01_person.get('f1', 0):<15.4f} | {exp01_person.get('f1', 0) - EXP00_BASELINE['person']['f1']:+.4f}")
    print(f"{'Person AP@50':<24} | {EXP00_BASELINE['person']['ap50']:<15.4f} | {exp01_person.get('ap50', 0):<15.4f} | {exp01_person.get('ap50', 0) - EXP00_BASELINE['person']['ap50']:+.4f}")
    print("-" * 72)
    print(f"{'Macro F1':<24} | {EXP00_BASELINE['macro_f1']:<15.4f} | {metrics.macro_f1:<15.4f} | {metrics.macro_f1 - EXP00_BASELINE['macro_f1']:+.4f}")
    print(f"{'mAP@50':<24} | {EXP00_BASELINE['mAP_50']:<15.4f} | {metrics.mAP_50:<15.4f} | {metrics.mAP_50 - EXP00_BASELINE['mAP_50']:+.4f}")
    print("=================================================================")


if __name__ == "__main__":
    main()
