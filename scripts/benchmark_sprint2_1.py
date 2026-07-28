from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.video_analysis.benchmark_adapters import (
    COCO_CLASS_MAP,
    SOCCERNET_H250_CLASS_MAP,
    MOTChallengeAdapter,
    YOLOAdapter,
)
from app.video_analysis.benchmark_metrics import (
    DetectionEvaluator,
    MemoryTracker,
    TrackingEvaluator,
)
from app.video_analysis.detectors import RawDetection, create_detector
from app.video_analysis.trackers import create_tracker


def benchmark_detector_on_yolo(
    adapter: YOLOAdapter,
    detector_name: str = "yolo",
    model_path: str = "yolo11n.pt",
    model_class_map: dict[int, str] | None = None,
    device: str = "cpu",
    max_frames: int | None = None,
) -> dict[str, Any]:
    """Evaluates a detector model against a YOLO ground truth dataset."""
    dataset = adapter.load_dataset()
    if max_frames is not None:
        dataset = dataset[:max_frames]
    if not dataset:
        raise ValueError(f"Aucune annotation YOLO trouvée dans {adapter.labels_dir}")

    missing_images = [
        frame.frame_index for frame in dataset if frame.image_path is None
    ]
    if missing_images:
        raise ValueError(
            f"{len(missing_images)} image(s) sont introuvables. "
            "Fournissez --yolo-images avec le dossier correspondant aux labels."
        )

    start_time = time.monotonic()

    predictions_by_frame: dict[int, list[RawDetection]] = {}

    with MemoryTracker() as mem_tracker:
        detector = create_detector(
            detector_name,
            model_path=model_path,
            device=device,
            class_map=model_class_map,
        )
        detector.load()

        for frame_gt in dataset:
            f_idx = frame_gt.frame_index
            img = cv2.imread(str(frame_gt.image_path))
            if img is None:
                raise ValueError(f"Image illisible : {frame_gt.image_path}")

            detections = detector.detect(img)
            predictions_by_frame[f_idx] = detections

        duration = time.monotonic() - start_time
        peak_rss_mb = mem_tracker.get_peak_rss_mb()

    evaluator = DetectionEvaluator(iou_threshold=0.5)
    metrics = evaluator.evaluate(
        ground_truth=dataset,
        predictions_by_frame=predictions_by_frame,
        duration_seconds=duration,
        peak_rss_mb=peak_rss_mb,
    )

    return {
        "detector": detector_name,
        "model_id": model_path,
        "model_class_map": model_class_map or COCO_CLASS_MAP,
        "device": device,
        "dataset_frames": len(dataset),
        "metrics": {
            "mAP_50": metrics.mAP_50,
            "precision": metrics.precision,
            "recall": metrics.recall,
            "f1_score": metrics.f1_score,
            "macro_f1": metrics.macro_f1,
            "f1_from_macro_precision_recall": metrics.f1_from_macro_precision_recall,
            "ball_recall": metrics.ball_recall,
            "class_breakdown": metrics.class_metrics,
            "fps": metrics.fps,
            "total_seconds": metrics.total_seconds,
            "peak_rss_mb": metrics.peak_rss_mb,
        },
    }


def benchmark_trackers_on_mot(
    mot_adapter: MOTChallengeAdapter,
    trackers: list[str] | None = None,
    detector_name: str = "yolo",
    model_path: str = "yolo11n.pt",
    device: str = "cpu",
    use_trackeval: bool = False,
    max_frames: int | None = None,
) -> list[dict[str, Any]]:
    """Evaluates trackers (IoU vs ByteTrack) against a MOT ground truth dataset."""
    if trackers is None:
        trackers = ["iou", "bytetrack"]

    gt_frames = mot_adapter.load_dataset()
    if max_frames is not None:
        selected_indices = sorted(gt_frames)[:max_frames]
        gt_frames = {index: gt_frames[index] for index in selected_indices}
    results: list[dict[str, Any]] = []

    if not gt_frames:
        raise ValueError(f"Aucune annotation MOT trouvée dans {mot_adapter.gt_file}")

    missing_frames = [
        frame_index
        for frame_index, frame in gt_frames.items()
        if frame.image_path is None
    ]
    if missing_frames:
        raise ValueError(
            f"{len(missing_frames)} frame(s) sont introuvables. "
            "Fournissez --mot-frames avec le dossier d'images de la séquence."
        )

    detector = create_detector(
        detector_name,
        model_path=model_path,
        device=device,
        class_map=COCO_CLASS_MAP,
    )
    detector.load()

    raw_detections_by_frame: dict[int, list[RawDetection]] = {}
    images_by_frame: dict[int, Any] = {}

    for f_idx, frame_gt in gt_frames.items():
        img = cv2.imread(str(frame_gt.image_path))
        if img is None:
            raise ValueError(f"Frame illisible : {frame_gt.image_path}")
        images_by_frame[f_idx] = img
        raw_detections_by_frame[f_idx] = detector.detect(img)

    tracking_evaluator = TrackingEvaluator(iou_threshold=0.5)

    for tracker_name in trackers:
        tracker = create_tracker(enabled=True, name=tracker_name)
        tracker.reset()

        tracker_preds_by_frame: dict[int, list[Any]] = {}

        for f_idx in sorted(gt_frames):
            raw_dets = raw_detections_by_frame.get(f_idx, [])
            tracked_dets = tracker.update(
                frame=images_by_frame[f_idx],
                detections=raw_dets,
            )

            preds_list = []
            for t_det in tracked_dets:
                if t_det.track_id is not None:
                    preds_list.append(
                        {
                            "track_id": t_det.track_id,
                            "class_name": t_det.detection.class_name,
                            "bbox": list(t_det.detection.bbox),
                        }
                    )
            tracker_preds_by_frame[f_idx] = preds_list

        eval_res = tracking_evaluator.evaluate(
            ground_truth_frames=gt_frames,
            tracker_predictions=tracker_preds_by_frame,
            tracker_name=tracker_name,
            use_trackeval=use_trackeval,
        )

        res_dict = {
            "tracker": eval_res.tracker_name,
            "engine": eval_res.evaluation_engine,
            "metrics": {
                "HOTA@0.5": eval_res.hota_0_5,
                "DetA@0.5": eval_res.deta_0_5,
                "AssA@0.5": eval_res.assa_0_5,
                "IDF1": eval_res.idf1,
                "num_gt_tracks": eval_res.num_gt_tracks,
                "num_pred_tracks": eval_res.num_pred_tracks,
            },
        }

        if eval_res.hota_official is not None:
            res_dict["metrics"]["HOTA_official_19_thresholds"] = eval_res.hota_official
            res_dict["metrics"]["DetA_official_19_thresholds"] = eval_res.deta_official
            res_dict["metrics"]["AssA_official_19_thresholds"] = eval_res.assa_official

        results.append(res_dict)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Benchmark public Sprint 2.1 - Détecteurs et Trackers"
    )
    parser.add_argument(
        "--yolo-labels",
        "--yolo-dir",
        dest="yolo_labels",
        type=Path,
        help="Répertoire des annotations YOLO H250",
    )
    parser.add_argument(
        "--yolo-images",
        type=Path,
        help="Répertoire des images YOLO H250 correspondant aux labels",
    )
    parser.add_argument("--mot-gt", type=Path, help="Fichier gt.txt MOTChallenge")
    parser.add_argument(
        "--mot-frames",
        type=Path,
        help="Répertoire des frames correspondant au fichier MOT gt.txt",
    )
    parser.add_argument(
        "--detector-coco", default="yolo11n.pt", help="Chemin du modèle COCO"
    )
    parser.add_argument(
        "--detector-finetuned", help="Chemin du modèle fine-tuné football"
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Périphérique Ultralytics : cpu, 0, 1...",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        help="Limiter chaque benchmark aux N premières frames (smoke test)",
    )
    parser.add_argument(
        "--trackers",
        default="iou,bytetrack",
        help="Liste des trackers séparés par des virgules",
    )
    parser.add_argument(
        "--use-trackeval",
        action="store_true",
        help="Utiliser l'intégration officielle de TrackEval (19 seuils) si disponible",
    )
    parser.add_argument(
        "--output", type=Path, default="benchmark_sprint2_1_report.json"
    )

    args = parser.parse_args()

    report: dict[str, Any] = {
        "title": "Sprint 2.1 Public Football Benchmark Report",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "detectors": [],
        "trackers": [],
    }

    if args.yolo_labels and args.yolo_labels.is_dir():
        if not args.yolo_images or not args.yolo_images.is_dir():
            parser.error("--yolo-images est requis avec --yolo-labels")
        print(f"[*] Évaluation des détecteurs sur dataset YOLO : {args.yolo_labels}")
        adapter = YOLOAdapter(
            labels_dir=args.yolo_labels,
            images_dir=args.yolo_images,
        )

        coco_res = benchmark_detector_on_yolo(
            adapter,
            detector_name="yolo",
            model_path=args.detector_coco,
            model_class_map=COCO_CLASS_MAP,
            device=args.device,
            max_frames=args.max_frames,
        )
        report["detectors"].append(coco_res)

        if args.detector_finetuned and Path(args.detector_finetuned).is_file():
            print(f"[*] Évaluation du modèle fine-tuné : {args.detector_finetuned}")
            ft_res = benchmark_detector_on_yolo(
                adapter,
                detector_name="yolo",
                model_path=args.detector_finetuned,
                model_class_map=SOCCERNET_H250_CLASS_MAP,
                device=args.device,
                max_frames=args.max_frames,
            )
            report["detectors"].append(ft_res)

    if args.mot_gt and args.mot_gt.is_file():
        if not args.mot_frames or not args.mot_frames.is_dir():
            parser.error("--mot-frames est requis avec --mot-gt")
        print(f"[*] Évaluation des trackers sur MOT dataset : {args.mot_gt}")
        mot_adapter = MOTChallengeAdapter(
            gt_file=args.mot_gt,
            frames_dir=args.mot_frames,
        )
        tracker_names = [t.strip() for t in args.trackers.split(",") if t.strip()]
        t_results = benchmark_trackers_on_mot(
            mot_adapter=mot_adapter,
            trackers=tracker_names,
            detector_name="yolo",
            model_path=args.detector_coco,
            device=args.device,
            use_trackeval=args.use_trackeval,
            max_frames=args.max_frames,
        )
        report["trackers"] = t_results

    encoded = json.dumps(report, indent=2, ensure_ascii=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    print("\n=== Résultat du Benchmark ===")
    print(encoded)


if __name__ == "__main__":
    main()
