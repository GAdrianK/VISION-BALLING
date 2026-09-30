#!/usr/bin/env python3
"""
Precomputes and caches PRTReID appearance embeddings for locked RF-DETR detections
across all EXP-10 sequences using streaming frame-by-frame batching (batch_size=32):
  - DEV: SNMOT-060, SNMOT-061, SNMOT-062
  - HOLDOUT: SNMOT-069, SNMOT-070, SNMOT-071
Uses the official sports-specific PRTReID checkpoint (SHA-256: 1304562c...).
"""

from __future__ import annotations

import gc
from pathlib import Path
import pickle
import time
import cv2
import numpy as np
import torch

from app.video_analysis.detectors import RawDetection
from app.video_analysis.reid_encoder import (
    DEFAULT_REID_CKPT_PATH,
    PlayerAppearanceEncoder,
    extract_player_crop,
    verify_checkpoint_hash,
)

DEFAULT_DATASET_DIR = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train")
DEFAULT_CACHE_DIR = Path("/media/adriano/Windows/runs/tracking/exp10")

ALL_SEQUENCES = [
    "SNMOT-060",
    "SNMOT-061",
    "SNMOT-062",
    "SNMOT-069",
    "SNMOT-070",
    "SNMOT-071",
]


def main() -> None:
    print("=" * 80)
    print("EXP-10 PRTREID FEATURE CACHING (FRAME-BY-FRAME STREAMING)")
    print("=" * 80)

    sha256, md5 = verify_checkpoint_hash(DEFAULT_REID_CKPT_PATH)
    print(f"[✓] Checkpoint verified: {DEFAULT_REID_CKPT_PATH.name}")
    print(f"    SHA-256: {sha256}")
    print(f"    MD5:     {md5}")

    print("[*] Initializing PlayerAppearanceEncoder on CUDA (batch_size=32)...")
    encoder = PlayerAppearanceEncoder(DEFAULT_REID_CKPT_PATH, batch_size=32)
    print("[✓] Model ready on CUDA.")

    for seq_name in ALL_SEQUENCES:
        feats_cache_file = DEFAULT_CACHE_DIR / f"{seq_name}_reid_feats.pkl"
        if feats_cache_file.is_file():
            print(f"[✓] {seq_name} ReID features already cached at {feats_cache_file.name}. Skipping.")
            continue

        dets_cache_file = DEFAULT_CACHE_DIR / f"{seq_name}_raw_dets.pkl"
        if not dets_cache_file.is_file():
            raise FileNotFoundError(f"Missing detection cache for {seq_name}: {dets_cache_file}")

        with open(dets_cache_file, "rb") as f:
            dets_by_frame: dict[int, list[RawDetection]] = pickle.load(f)

        seq_dir = DEFAULT_DATASET_DIR / seq_name
        img1_dir = seq_dir / "img1"

        print(f"\n[*] Processing features for {seq_name} (750 frames)...")
        t0 = time.perf_counter()
        feats_by_frame: dict[int, np.ndarray] = {}
        total_crops = 0

        for f_idx in range(1, 751):
            frame_dets = dets_by_frame.get(f_idx, [])
            person_dets = [
                d for d in frame_dets if d.class_name == "person" and d.confidence > 0.10
            ]
            if not person_dets:
                feats_by_frame[f_idx] = np.empty((0, 256), dtype=np.float32)
                continue

            fpath = img1_dir / f"{f_idx:06d}.jpg"
            frame_img = cv2.imread(str(fpath))
            if frame_img is None:
                raise FileNotFoundError(f"Failed to read {fpath}")

            crops = [extract_player_crop(frame_img, d.bbox) for d in person_dets]
            frame_feats = encoder.encode_crops(crops)
            feats_by_frame[f_idx] = frame_feats
            total_crops += len(crops)

            if f_idx % 150 == 0:
                elapsed = time.perf_counter() - t0
                print(f"    Frame {f_idx}/750 ({total_crops} crops encoded, {f_idx/elapsed:.1f} FPS)...")

        t_total = time.perf_counter() - t0
        crops_per_sec = total_crops / max(0.001, t_total)
        print(f"[✓] {seq_name} ({total_crops} crops) completed in {t_total:.2f} s ({crops_per_sec:.1f} crops/sec).")

        with open(feats_cache_file, "wb") as f:
            pickle.dump(feats_by_frame, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"[✓] Saved: {feats_cache_file.name} ({feats_cache_file.stat().st_size / 1024 / 1024:.2f} MB)")

        # Clear memory between sequences
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

    print("\n[✓] All PRTReID sequence features cached successfully!")


if __name__ == "__main__":
    main()
