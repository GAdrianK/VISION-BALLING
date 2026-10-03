#!/usr/bin/env python3
"""
EXP-10 Phase 6: Offline Sports-Specific Player ReID Sanity Benchmark.

Evaluates PRTReID appearance embeddings independently from tracking:
  - Associates locked RF-DETR Small 960 detections with Ground Truth player IDs (IoU >= 0.50).
  - Extracts deterministic player crops from raw frames (strictly no GT boxes).
  - Encodes crops to 256-D L2-normalized embeddings via PlayerAppearanceEncoder.
  - Computes same-ID vs different-ID cosine similarity distributions.
  - Computes Rank-1 identification accuracy and mean Average Precision (mAP).
Strictly evaluated on DEV sequences (SNMOT-060, SNMOT-061, SNMOT-062).
Zero GT labels used during inference or feature extraction.
"""

from __future__ import annotations

import configparser
import json
import pickle
import time
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.video_analysis.benchmark_metrics import compute_iou
from app.video_analysis.detectors import RawDetection
from app.video_analysis.reid_encoder import (
    DEFAULT_REID_CKPT_PATH,
    PlayerAppearanceEncoder,
    extract_player_crop,
    verify_checkpoint_hash,
)

DEFAULT_DATASET_DIR = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train")
DEFAULT_CACHE_DIR = Path("/media/adriano/Windows/runs/tracking/exp10")
DEV_SEQUENCES = ["SNMOT-060", "SNMOT-061", "SNMOT-062"]


def load_person_gt(seq_dir: Path) -> tuple[dict[int, list[tuple[int, list[float]]]], dict[int, str]]:
    """Loads GT person bounding boxes [x1, y1, x2, y2] and track IDs per frame."""
    ini_path = seq_dir / "gameinfo.ini"
    gt_path = seq_dir / "gt" / "gt.txt"

    roles: dict[int, str] = {}
    if ini_path.is_file():
        cp = configparser.ConfigParser(strict=False)
        cp.read(str(ini_path))
        if "Sequence" in cp:
            sec = cp["Sequence"]
            for k, v in sec.items():
                if k.startswith("trackletid_"):
                    try:
                        tid = int(k.replace("trackletid_", ""))
                        role_part = v.split(";")[0].strip().lower()
                        if any(role_part.startswith(p) for p in ("player", "goalkeeper", "referee")):
                            roles[tid] = "person"
                        elif role_part.startswith("ball"):
                            roles[tid] = "ball"
                        else:
                            roles[tid] = f"other_{role_part}"
                    except Exception:
                        pass

    gt_by_frame: dict[int, list[tuple[int, list[float]]]] = {}
    with open(gt_path, "r") as f:
        for line in f:
            parts = line.strip().split(",")
            if len(parts) < 6:
                continue
            f_idx = int(parts[0])
            tid = int(parts[1])
            l, t, w, h = float(parts[2]), float(parts[3]), float(parts[4]), float(parts[5])
            bbox = [l, t, l + w, t + h]
            role = roles.get(tid, "person")
            if role == "person":
                gt_by_frame.setdefault(f_idx, []).append((tid, bbox))

    return gt_by_frame, roles


def main() -> None:
    print("=" * 80)
    print("EXP-10 PHASE 6 — OFFLINE REID SANITY BENCHMARK")
    print("=" * 80)

    # 1. Verify Checkpoint
    sha256, md5 = verify_checkpoint_hash(DEFAULT_REID_CKPT_PATH)
    print(f"[✓] PRTReID Checkpoint verified: {DEFAULT_REID_CKPT_PATH.name}")
    print(f"    SHA-256: {sha256}")
    print(f"    MD5:     {md5}")

    # 2. Initialize Encoder
    print("[*] Loading PlayerAppearanceEncoder on CUDA...")
    encoder = PlayerAppearanceEncoder(DEFAULT_REID_CKPT_PATH, batch_size=64)
    print("[✓] Model ready.")

    # 3. Associate Detections with GT & Extract Crops
    # We sample every 3 frames (8.3 fps) to capture diverse viewpoints without extreme redundancy
    FRAME_STRIDE = 3
    all_crops: list[np.ndarray] = []
    all_labels: list[tuple[str, int, int]] = []  # (seq, tid, frame_idx)

    for seq in DEV_SEQUENCES:
        seq_dir = DEFAULT_DATASET_DIR / seq
        cache_file = DEFAULT_CACHE_DIR / f"{seq}_raw_dets.pkl"
        img1_dir = seq_dir / "img1"

        with open(cache_file, "rb") as f:
            dets_by_frame: dict[int, list[RawDetection]] = pickle.load(f)

        gt_by_frame, _ = load_person_gt(seq_dir)

        print(f"[*] Extracting matched player crops for {seq} (stride={FRAME_STRIDE})...")
        t0 = time.perf_counter()
        seq_crop_count = 0

        for f_idx in range(1, 751, FRAME_STRIDE):
            frame_dets = dets_by_frame.get(f_idx, [])
            frame_gt = gt_by_frame.get(f_idx, [])
            if not frame_dets or not frame_gt:
                continue

            person_dets = [d for d in frame_dets if d.class_name == "person" and d.confidence >= 0.45]
            if not person_dets:
                continue

            # Greedy bipartite matching by IoU
            matched_dets: list[tuple[RawDetection, int]] = []
            used_gt: set[int] = set()

            for d in person_dets:
                best_iou = 0.0
                best_tid = -1
                best_g_idx = -1
                for g_idx, (tid, gt_box) in enumerate(frame_gt):
                    if g_idx in used_gt:
                        continue
                    iou = compute_iou(d.bbox, gt_box)
                    if iou > best_iou:
                        best_iou = iou
                        best_tid = tid
                        best_g_idx = g_idx

                if best_iou >= 0.50 and best_g_idx >= 0:
                    used_gt.add(best_g_idx)
                    matched_dets.append((d, best_tid))

            if not matched_dets:
                continue

            fpath = img1_dir / f"{f_idx:06d}.jpg"
            frame_img = cv2.imread(str(fpath))
            if frame_img is None:
                continue

            for d, tid in matched_dets:
                crop = extract_player_crop(frame_img, d.bbox)
                all_crops.append(crop)
                all_labels.append((seq, tid, f_idx))
                seq_crop_count += 1

        print(f"    Extracted {seq_crop_count} crops in {time.perf_counter() - t0:.2f} s")

    print(f"\n[✓] Total crops collected across DEV sequences: {len(all_crops)}")

    # 4. Compute Embeddings
    print("[*] Encoding player crops with PRTReID (batch_size=64)...")
    t_enc0 = time.perf_counter()
    embeddings = encoder.encode_crops(all_crops)
    t_enc1 = time.perf_counter()
    crops_per_sec = len(all_crops) / (t_enc1 - t_enc0)
    print(f"[✓] Encoded {len(all_crops)} crops in {t_enc1 - t_enc0:.2f} s ({crops_per_sec:.1f} crops/sec)")
    print(f"    Embedding array shape: {embeddings.shape}, dtype: {embeddings.dtype}")

    # 5. Cosine Similarity Distribution Analysis
    print("\n[*] Computing intra-sequence same-ID vs different-ID similarity distributions...")
    same_id_sims: list[float] = []
    diff_id_sims: list[float] = []

    # Group by sequence
    seq_groups: dict[str, list[int]] = {}
    for idx, (seq, tid, f_idx) in enumerate(all_labels):
        seq_groups.setdefault(seq, []).append(idx)

    rng = np.random.default_rng(42)

    for seq, indices in seq_groups.items():
        sub_embs = embeddings[indices]
        sub_labels = [all_labels[i] for i in indices]
        sub_tids = np.array([lbl[1] for lbl in sub_labels])
        sub_fidx = np.array([lbl[2] for lbl in sub_labels])

        n_items = len(indices)
        # Compute dot product matrix (since vectors are L2-normalized, dot product is cosine similarity)
        sim_mat = np.matmul(sub_embs, sub_embs.T)

        for i in range(n_items):
            for j in range(i + 1, n_items):
                # Only compare detections from DIFFERENT frames
                if sub_fidx[i] == sub_fidx[j]:
                    continue
                sim = float(sim_mat[i, j])
                if sub_tids[i] == sub_tids[j]:
                    same_id_sims.append(sim)
                else:
                    # Subsample diff_id pairs to keep memory and computation balanced
                    if rng.random() < 0.05:
                        diff_id_sims.append(sim)

    same_arr = np.array(same_id_sims, dtype=np.float32)
    diff_arr = np.array(diff_id_sims, dtype=np.float32)

    same_stats = {
        "count": int(len(same_arr)),
        "mean": float(np.mean(same_arr)),
        "median": float(np.median(same_arr)),
        "std": float(np.std(same_arr)),
        "min": float(np.min(same_arr)),
        "max": float(np.max(same_arr)),
        "p10": float(np.percentile(same_arr, 10)),
        "p50": float(np.percentile(same_arr, 50)),
        "p90": float(np.percentile(same_arr, 90)),
    }

    diff_stats = {
        "count": int(len(diff_arr)),
        "mean": float(np.mean(diff_arr)),
        "median": float(np.median(diff_arr)),
        "std": float(np.std(diff_arr)),
        "min": float(np.min(diff_arr)),
        "max": float(np.max(diff_arr)),
        "p10": float(np.percentile(diff_arr, 10)),
        "p50": float(np.percentile(diff_arr, 50)),
        "p90": float(np.percentile(diff_arr, 90)),
    }

    separation_margin = same_stats["mean"] - diff_stats["mean"]

    print(f"\n--- SAME-ID COSINE SIMILARITY (N={same_stats['count']:,}) ---")
    print(f"  Mean:   {same_stats['mean']:.4f} (±{same_stats['std']:.4f})")
    print(f"  Median: {same_stats['median']:.4f}")
    print(f"  P10:    {same_stats['p10']:.4f} | P50: {same_stats['p50']:.4f} | P90: {same_stats['p90']:.4f}")
    print(f"  Range:  [{same_stats['min']:.4f}, {same_stats['max']:.4f}]")

    print(f"\n--- DIFFERENT-ID COSINE SIMILARITY (N={diff_stats['count']:,} sampled) ---")
    print(f"  Mean:   {diff_stats['mean']:.4f} (±{diff_stats['std']:.4f})")
    print(f"  Median: {diff_stats['median']:.4f}")
    print(f"  P10:    {diff_stats['p10']:.4f} | P50: {diff_stats['p50']:.4f} | P90: {diff_stats['p90']:.4f}")
    print(f"  Range:  [{diff_stats['min']:.4f}, {diff_stats['max']:.4f}]")

    print(f"\n[*] Appearance Separation Margin (Mean Same - Mean Diff): {separation_margin:.4f}")

    # 6. Rank-1 and mAP Benchmark
    print("\n[*] Computing Rank-1 and mAP query/gallery metrics...")
    cmc_hits = 0
    total_queries = 0
    all_ap: list[float] = []

    for seq, indices in seq_groups.items():
        sub_embs = embeddings[indices]
        sub_labels = [all_labels[i] for i in indices]
        sub_tids = np.array([lbl[1] for lbl in sub_labels])
        sub_fidx = np.array([lbl[2] for lbl in sub_labels])

        sim_mat = np.matmul(sub_embs, sub_embs.T)

        unique_tids = np.unique(sub_tids)
        for tid in unique_tids:
            tid_indices = np.where(sub_tids == tid)[0]
            if len(tid_indices) < 2:
                # Need at least query + 1 gallery item
                continue

            # Query is first occurrence
            q_idx = tid_indices[0]
            q_frame = sub_fidx[q_idx]

            # Gallery: all other crops from DIFFERENT frames
            g_mask = sub_fidx != q_frame
            g_indices = np.where(g_mask)[0]
            if len(g_indices) == 0:
                continue

            # Check if target ID is in gallery
            target_in_gallery = np.any(sub_tids[g_indices] == tid)
            if not target_in_gallery:
                continue

            q_sims = sim_mat[q_idx, g_indices]
            sorted_order = np.argsort(-q_sims)  # Descending similarity
            top_ranked_tid = sub_tids[g_indices[sorted_order[0]]]

            total_queries += 1
            if top_ranked_tid == tid:
                cmc_hits += 1

            # Average Precision (AP) for this query
            binary_matches = (sub_tids[g_indices[sorted_order]] == tid).astype(int)
            cum_matches = np.cumsum(binary_matches)
            ranks = np.arange(1, len(binary_matches) + 1)
            precisions = cum_matches / ranks
            ap = np.sum(precisions * binary_matches) / np.sum(binary_matches)
            all_ap.append(float(ap))

    rank1_acc = cmc_hits / max(1, total_queries)
    mean_ap = float(np.mean(all_ap)) if all_ap else 0.0

    print(f"[✓] Rank-1 Identification Accuracy: {rank1_acc * 100:.2f}% ({cmc_hits}/{total_queries} queries)")
    print(f"[✓] mean Average Precision (mAP):       {mean_ap * 100:.2f}%")

    # 7. Output JSON Diagnostic
    sanity_results = {
        "status": "COMPLETED",
        "checkpoint": str(DEFAULT_REID_CKPT_PATH),
        "checkpoint_sha256": sha256,
        "checkpoint_md5": md5,
        "architecture": "bpbreid (HRNet-32 backbone, 256-D global embedding)",
        "dev_sequences": DEV_SEQUENCES,
        "total_crops_evaluated": len(all_crops),
        "crops_per_second": round(crops_per_sec, 2),
        "same_id_similarity": same_stats,
        "diff_id_similarity": diff_stats,
        "separation_margin": round(separation_margin, 4),
        "rank1_accuracy": round(rank1_acc, 4),
        "mean_average_precision_map": round(mean_ap, 4),
        "num_queries_evaluated": total_queries,
    }

    out_path = Path("docs/experiments/exp10_reid_sanity_diagnostic.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(sanity_results, f, indent=2)

    print(f"\n[✓] Offline sanity diagnostic written to: {out_path}")


if __name__ == "__main__":
    main()
