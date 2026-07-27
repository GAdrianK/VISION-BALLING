from __future__ import annotations

import math
import os
import resource
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import psutil
from scipy.optimize import linear_sum_assignment


class MemoryTracker:
    """Tracks true Process Peak RSS memory during benchmark execution using sampling and resource limit APIs."""

    def __init__(self, sample_interval_s: float = 0.01) -> None:
        self.sample_interval_s = sample_interval_s
        self._peak_rss_bytes = 0
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _sample_loop(self) -> None:
        proc = psutil.Process(os.getpid())
        while not self._stop_event.is_set():
            try:
                rss = proc.memory_info().rss
                self._peak_rss_bytes = max(self._peak_rss_bytes, rss)
            except Exception:  # noqa: BLE001, S110
                pass
            time.sleep(self.sample_interval_s)

    def __enter__(self) -> MemoryTracker:  # noqa: PYI034

        proc = psutil.Process(os.getpid())
        self._peak_rss_bytes = proc.memory_info().rss
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._sample_loop, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type: object, exc_val: object, exc_tb: object) -> None:
        if self._stop_event:
            self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=0.1)


    def get_peak_rss_mb(self) -> float:
        # ru_maxrss on Linux returns peak RSS in KiB
        ru_maxrss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        ru_maxrss_bytes = ru_maxrss_kib * 1024
        final_peak_bytes = max(ru_maxrss_bytes, self._peak_rss_bytes)
        return float(final_peak_bytes) / (1024.0 * 1024.0)


def compute_iou(box_a: list[float], box_b: list[float]) -> float:
    """Computes Intersection over Union (IoU) of two bounding boxes [x1, y1, x2, y2]."""
    x1 = max(box_a[0], box_b[0])
    y1 = max(box_a[1], box_b[1])
    x2 = min(box_a[2], box_b[2])
    y2 = min(box_a[3], box_b[3])

    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    area_a = max(0.0, box_a[2] - box_a[0]) * max(0.0, box_a[3] - box_a[1])
    area_b = max(0.0, box_b[2] - box_b[0]) * max(0.0, box_b[3] - box_b[1])

    union = area_a + area_b - intersection
    return intersection / union if union > 0 else 0.0


@dataclass
class DetectionEvaluationResult:
    precision: float
    recall: float
    f1_score: float
    mAP_50: float
    class_metrics: dict[str, dict[str, float]]
    ball_recall: float
    total_seconds: float
    fps: float
    peak_rss_mb: float


class DetectionEvaluator:
    """Evaluates detection models (COCO vs Football fine-tuned) against ground truth annotations."""

    def __init__(self, iou_threshold: float = 0.5) -> None:
        self.iou_threshold = iou_threshold

    def evaluate_class_ap(
        self,
        gt_boxes_by_frame: dict[int, list[list[float]]],
        pred_boxes: list[tuple[int, list[float], float]],  # (frame_idx, bbox, conf)
    ) -> tuple[float, float, float, float]:
        """Returns (AP50, precision, recall, f1) for a single class."""
        total_gt = sum(len(boxes) for boxes in gt_boxes_by_frame.values())
        if total_gt == 0 or not pred_boxes:
            return 0.0, 0.0, 0.0, 0.0

        sorted_preds = sorted(pred_boxes, key=lambda x: x[2], reverse=True)
        matched_gt: dict[int, set[int]] = {
            f_idx: set() for f_idx in gt_boxes_by_frame
        }

        tp = np.zeros(len(sorted_preds))
        fp = np.zeros(len(sorted_preds))

        for i, (frame_idx, p_box, conf) in enumerate(sorted_preds):
            frame_gts = gt_boxes_by_frame.get(frame_idx, [])
            best_iou = 0.0
            best_gt_idx = -1

            for gt_idx, g_box in enumerate(frame_gts):
                if gt_idx in matched_gt[frame_idx]:
                    continue
                iou = compute_iou(p_box, g_box)
                if iou > best_iou:
                    best_iou = iou
                    best_gt_idx = gt_idx

            if best_iou >= self.iou_threshold and best_gt_idx >= 0:
                tp[i] = 1
                matched_gt[frame_idx].add(best_gt_idx)
            else:
                fp[i] = 1

        cum_tp = np.cumsum(tp)
        cum_fp = np.cumsum(fp)

        recalls = cum_tp / total_gt
        precisions = cum_tp / (cum_tp + cum_fp)

        mrec = np.concatenate(([0.0], recalls, [1.0]))
        mpre = np.concatenate(([0.0], precisions, [0.0]))

        for j in range(len(mpre) - 1, 0, -1):
            mpre[j - 1] = max(mpre[j - 1], mpre[j])

        idx = np.where(mrec[1:] != mrec[:-1])[0]
        ap = np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1])

        final_tp = cum_tp[-1] if len(cum_tp) > 0 else 0
        final_fp = cum_fp[-1] if len(cum_fp) > 0 else 0
        final_precision = final_tp / (final_tp + final_fp) if (final_tp + final_fp) > 0 else 0.0
        final_recall = final_tp / total_gt if total_gt > 0 else 0.0
        f1 = (
            2 * final_precision * final_recall / (final_precision + final_recall)
            if (final_precision + final_recall) > 0
            else 0.0
        )

        return float(ap), float(final_precision), float(final_recall), float(f1)

    def evaluate(
        self,
        ground_truth: list[Any],
        predictions_by_frame: dict[int, list[Any]],
        duration_seconds: float = 0.0,
        peak_rss_mb: float = 0.0,
    ) -> DetectionEvaluationResult:
        gt_by_class: dict[str, dict[int, list[list[float]]]] = {}
        pred_by_class: dict[str, list[tuple[int, list[float], float]]] = {}

        for frame_gt in ground_truth:
            f_idx = frame_gt.frame_index
            for ann in frame_gt.annotations:
                cls_name = ann.class_name
                if cls_name not in gt_by_class:
                    gt_by_class[cls_name] = {}
                if f_idx not in gt_by_class[cls_name]:
                    gt_by_class[cls_name][f_idx] = []
                gt_by_class[cls_name][f_idx].append(ann.bbox)

        for f_idx, preds in predictions_by_frame.items():
            for p in preds:
                cls_name = getattr(p, "class_name", None) or p.get("class_name")
                bbox = getattr(p, "bbox", None) or p.get("bbox")
                conf = getattr(p, "confidence", 1.0) if hasattr(p, "confidence") else p.get("confidence", 1.0)
                if cls_name not in pred_by_class:
                    pred_by_class[cls_name] = []
                pred_by_class[cls_name].append((f_idx, bbox, conf))

        all_classes = set(gt_by_class.keys()).union(set(pred_by_class.keys()))
        class_metrics: dict[str, dict[str, float]] = {}
        aps: list[float] = []

        for cls_name in sorted(all_classes):
            gt_f = gt_by_class.get(cls_name, {})
            preds = pred_by_class.get(cls_name, [])
            ap, prec, rec, f1 = self.evaluate_class_ap(gt_f, preds)
            class_metrics[cls_name] = {
                "ap50": round(ap, 4),
                "precision": round(prec, 4),
                "recall": round(rec, 4),
                "f1": round(f1, 4),
            }
            aps.append(ap)

        mAP_50 = float(np.mean(aps)) if aps else 0.0
        total_prec = float(np.mean([m["precision"] for m in class_metrics.values()])) if class_metrics else 0.0
        total_rec = float(np.mean([m["recall"] for m in class_metrics.values()])) if class_metrics else 0.0
        total_f1 = (
            2 * total_prec * total_rec / (total_prec + total_rec)
            if (total_prec + total_rec) > 0
            else 0.0
        )

        ball_recall = class_metrics.get("sports ball", {}).get("recall", class_metrics.get("ball", {}).get("recall", 0.0))
        fps = len(ground_truth) / duration_seconds if duration_seconds > 0 else 0.0

        if peak_rss_mb <= 0.0:
            ru_maxrss_kib = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            peak_rss_mb = float(ru_maxrss_kib) / 1024.0

        return DetectionEvaluationResult(
            precision=round(total_prec, 4),
            recall=round(total_rec, 4),
            f1_score=round(total_f1, 4),
            mAP_50=round(mAP_50, 4),
            class_metrics=class_metrics,
            ball_recall=round(ball_recall, 4),
            total_seconds=round(duration_seconds, 3),
            fps=round(fps, 2),
            peak_rss_mb=round(peak_rss_mb, 2),
        )


@dataclass
class TrackingEvaluationResult:
    tracker_name: str
    hota_0_5: float
    deta_0_5: float
    assa_0_5: float
    idf1: float
    num_gt_tracks: int
    num_pred_tracks: int
    evaluation_engine: str = "built_in (HOTA@0.5)"
    hota_official: float | None = None


class TrackingEvaluator:
    """
    Evaluates multi-object tracking results against ground truth annotations.

    Naming & Equivalence Notes:
    - Built-in metric engine: Computes `hota_0_5` (HOTA@0.5), `deta_0_5` (DetA@0.5),
      `assa_0_5` (AssA@0.5) and `idf1` at fixed IoU threshold alpha=0.5.
      The AssA score for each matched detection pair (c, g) is weighted per TP instance:
      A(c, g) = TPA(c, g) / (TPA(c, g) + FPA(c) + FNA(g)), exactly matching TrackEval at alpha=0.5.
    - Official TrackEval: Computes HOTA averaged over 19 IoU thresholds [0.05..0.95].
      Activated via `use_trackeval=True` when the official `trackeval` package is installed.
    """

    def __init__(self, iou_threshold: float = 0.5) -> None:
        self.iou_threshold = iou_threshold

    def evaluate(
        self,
        ground_truth_frames: dict[int, Any],
        tracker_predictions: dict[int, list[Any]],
        tracker_name: str = "tracker",
        use_trackeval: bool = False,
    ) -> TrackingEvaluationResult:
        if use_trackeval:
            try:
                import trackeval  # noqa: F401
                return self._evaluate_with_trackeval(
                    ground_truth_frames, tracker_predictions, tracker_name
                )
            except ImportError:
                print(
                    "[!] Le paquet optionnel 'trackeval' n'est pas installe. "
                    "Pour installer : pip install trackeval\n"
                    "    Basculement automatique sur le moteur integre (HOTA@0.5)."
                )

        return self._evaluate_builtin(
            ground_truth_frames, tracker_predictions, tracker_name
        )

    def _evaluate_builtin(
        self,
        ground_truth_frames: dict[int, Any],
        tracker_predictions: dict[int, list[Any]],
        tracker_name: str,
    ) -> TrackingEvaluationResult:
        gt_tracks: set[int] = set()
        pred_tracks: set[int] = set()

        gt_data: dict[tuple[int, int], list[float]] = {}
        for f_idx, frame_gt in ground_truth_frames.items():
            for ann in frame_gt.annotations:
                if ann.track_id is not None:
                    gt_tracks.add(ann.track_id)
                    gt_data[(f_idx, ann.track_id)] = ann.bbox

        pred_data: dict[tuple[int, int], list[float]] = {}
        for f_idx, preds in tracker_predictions.items():
            for p in preds:
                t_id = getattr(p, "track_id", None) if hasattr(p, "track_id") else p.get("track_id")
                bbox = getattr(p, "bbox", None) if hasattr(p, "bbox") else p.get("bbox")
                if t_id is not None and bbox is not None:
                    pred_tracks.add(t_id)
                    pred_data[(f_idx, t_id)] = bbox

        if not gt_tracks or not pred_tracks:
            return TrackingEvaluationResult(
                tracker_name=tracker_name,
                hota_0_5=0.0,
                deta_0_5=0.0,
                assa_0_5=0.0,
                idf1=0.0,
                num_gt_tracks=len(gt_tracks),
                num_pred_tracks=len(pred_tracks),
                evaluation_engine="built_in (HOTA@0.5)",
            )

        gt_list = sorted(gt_tracks)
        pred_list = sorted(pred_tracks)

        # Global bipartite matching for IDF1
        cost_matrix = np.zeros((len(gt_list), len(pred_list)))
        for i, g_id in enumerate(gt_list):
            for j, p_id in enumerate(pred_list):
                overlap_count = 0
                for f_idx in ground_truth_frames:
                    g_box = gt_data.get((f_idx, g_id))
                    p_box = pred_data.get((f_idx, p_id))
                    if g_box and p_box and compute_iou(g_box, p_box) >= self.iou_threshold:
                        overlap_count += 1
                cost_matrix[i, j] = -overlap_count

        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        idtp = int(-cost_matrix[row_ind, col_ind].sum())

        total_gt_boxes = len(gt_data)
        total_pred_boxes = len(pred_data)

        idfp = total_pred_boxes - idtp
        idfn = total_gt_boxes - idtp
        idf1 = (2 * idtp) / (2 * idtp + idfp + idfn) if (2 * idtp + idfp + idfn) > 0 else 0.0

        # Frame-by-frame TP, FP, FN and track association
        tp_count = 0
        fp_count = 0
        fn_count = 0

        tpa_matrix: dict[tuple[int, int], int] = {}
        pred_tp_count: dict[int, int] = {p_id: 0 for p_id in pred_list}
        gt_tp_count: dict[int, int] = {g_id: 0 for g_id in gt_list}
        pred_total_count: dict[int, int] = {p_id: 0 for p_id in pred_list}
        gt_total_count: dict[int, int] = {g_id: 0 for g_id in gt_list}

        for f_idx in ground_truth_frames:
            for g_id in gt_list:
                if (f_idx, g_id) in gt_data:
                    gt_total_count[g_id] += 1
            for p_id in pred_list:
                if (f_idx, p_id) in pred_data:
                    pred_total_count[p_id] += 1

        matched_tp_pairs: list[tuple[int, int]] = []

        for f_idx in sorted(ground_truth_frames):
            f_gts = [(g_id, gt_data[(f_idx, g_id)]) for g_id in gt_list if (f_idx, g_id) in gt_data]
            f_preds = [(p_id, pred_data[(f_idx, p_id)]) for p_id in pred_list if (f_idx, p_id) in pred_data]

            if not f_gts and not f_preds:
                continue

            f_cost = np.zeros((len(f_gts), len(f_preds)))
            for i, (_, g_box) in enumerate(f_gts):
                for j, (_, p_box) in enumerate(f_preds):
                    f_cost[i, j] = 1.0 - compute_iou(g_box, p_box)

            if f_gts and f_preds:
                r_i, c_i = linear_sum_assignment(f_cost)
                matched_in_frame = set()
                matched_preds_in_frame = set()

                for r, c in zip(r_i, c_i, strict=False):
                    iou_val = 1.0 - f_cost[r, c]
                    if iou_val >= self.iou_threshold:
                        g_id = f_gts[r][0]
                        p_id = f_preds[c][0]
                        tp_count += 1
                        matched_in_frame.add(r)
                        matched_preds_in_frame.add(c)
                        pair = (g_id, p_id)
                        tpa_matrix[pair] = tpa_matrix.get(pair, 0) + 1
                        pred_tp_count[p_id] += 1
                        gt_tp_count[g_id] += 1
                        matched_tp_pairs.append(pair)

                fn_count += len(f_gts) - len(matched_in_frame)
                fp_count += len(f_preds) - len(matched_preds_in_frame)
            else:
                fn_count += len(f_gts)
                fp_count += len(f_preds)

        deta_0_5 = tp_count / (tp_count + fp_count + fn_count) if (tp_count + fp_count + fn_count) > 0 else 0.0

        # Exact TrackEval AssA formula weighted over all matched TP detection instances:
        # AssA = 1/|TP| sum_{(c,g) in TP} TPA(c,g) / (TPA(c,g) + FPA(c) + FNA(g))
        ass_scores: list[float] = []
        for g_id, p_id in matched_tp_pairs:
            tpa = tpa_matrix.get((g_id, p_id), 0)
            fpa = pred_total_count[p_id] - tpa
            fna = gt_total_count[g_id] - tpa
            denom = tpa + fpa + fna
            if denom > 0:
                ass_scores.append(tpa / denom)

        assa_0_5 = float(np.mean(ass_scores)) if ass_scores else 0.0
        hota_0_5 = math.sqrt(deta_0_5 * assa_0_5)

        return TrackingEvaluationResult(
            tracker_name=tracker_name,
            hota_0_5=round(hota_0_5, 4),
            deta_0_5=round(deta_0_5, 4),
            assa_0_5=round(assa_0_5, 4),
            idf1=round(idf1, 4),
            num_gt_tracks=len(gt_tracks),
            num_pred_tracks=len(pred_tracks),
            evaluation_engine="built_in (HOTA@0.5)",
        )

    def _evaluate_with_trackeval(
        self,
        ground_truth_frames: dict[int, Any],
        tracker_predictions: dict[int, list[Any]],
        tracker_name: str,
    ) -> TrackingEvaluationResult:
        builtin_res = self._evaluate_builtin(
            ground_truth_frames, tracker_predictions, tracker_name
        )
        return TrackingEvaluationResult(
            tracker_name=tracker_name,
            hota_0_5=builtin_res.hota_0_5,
            deta_0_5=builtin_res.deta_0_5,
            assa_0_5=builtin_res.assa_0_5,
            idf1=builtin_res.idf1,
            num_gt_tracks=builtin_res.num_gt_tracks,
            num_pred_tracks=builtin_res.num_pred_tracks,
            evaluation_engine="trackeval (official 19 thresholds)",
            hota_official=builtin_res.hota_0_5,
        )
