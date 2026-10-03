#!/usr/bin/env python3
"""
Precomputes and caches locked RF-DETR Small 960 detections for EXP-10 holdout sequences:
  - SNMOT-069
  - SNMOT-070
  - SNMOT-071
Uses the frozen checkpoint (SHA-256: c1a1d88b...) with tracking floor threshold 0.10.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
import pickle
import time
import cv2

from app.video_analysis.detectors import RFDETRDetector, RawDetection

EXPECTED_CKPT_SHA256 = "c1a1d88b74edc5ddefa7da4581e2848c4c58c3938d88ad4a1b615f071752ffff"
DEFAULT_CKPT_PATH = Path("/media/adriano/Windows/runs/detect/exp04_rfdetr_small_h250_960/checkpoint_best_total.pth")
DEFAULT_DATASET_DIR = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train")
DEFAULT_CACHE_DIR = Path("/media/adriano/Windows/runs/tracking/exp10")

HOLDOUT_SEQUENCES = ["SNMOT-069", "SNMOT-070", "SNMOT-071"]


def verify_checkpoint(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"Checkpoint missing: {path}")
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1024 * 1024):
            hasher.update(chunk)
    digest = hasher.hexdigest()
    if digest != EXPECTED_CKPT_SHA256:
        raise ValueError(f"Checkpoint SHA-256 mismatch!\nExpected: {EXPECTED_CKPT_SHA256}\nFound:    {digest}")
    return digest


def main() -> None:
    print("=" * 80)
    print("EXP-10 HOLDOUT DETECTION CACHING")
    print("=" * 80)
    
    ckpt_hash = verify_checkpoint(DEFAULT_CKPT_PATH)
    print(f"[✓] Checkpoint verified: {DEFAULT_CKPT_PATH.name} (SHA-256: {ckpt_hash[:16]}...)")
    
    DEFAULT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    print("[*] Initializing locked RF-DETR Small 960 detector...")
    detector = RFDETRDetector(str(DEFAULT_CKPT_PATH))
    detector.load()
    print("[✓] RF-DETR loaded on CUDA.")
    
    for seq_name in HOLDOUT_SEQUENCES:
        cache_file = DEFAULT_CACHE_DIR / f"{seq_name}_raw_dets.pkl"
        if cache_file.is_file():
            print(f"[✓] {seq_name} already cached at {cache_file.name}. Skipping.")
            continue
            
        seq_dir = DEFAULT_DATASET_DIR / seq_name
        img1_dir = seq_dir / "img1"
        if not img1_dir.is_dir():
            raise FileNotFoundError(f"Missing img1 directory for {seq_name} at {img1_dir}")
            
        print(f"\n[*] Processing detections for {seq_name} (750 frames)...")
        t0 = time.perf_counter()
        dets_by_frame: dict[int, list[RawDetection]] = {}
        
        for f_idx in range(1, 751):
            fpath = img1_dir / f"{f_idx:06d}.jpg"
            frame = cv2.imread(str(fpath))
            if frame is None:
                raise FileNotFoundError(f"Failed to read {fpath}")
            dets = detector.detect_for_tracking(frame)
            dets_by_frame[f_idx] = dets
            if f_idx % 150 == 0:
                print(f"    Frame {f_idx}/750 processed...")
                
        t1 = time.perf_counter()
        fps = 750.0 / (t1 - t0)
        print(f"[✓] {seq_name} completed in {t1 - t0:.2f} s ({fps:.2f} FPS). Writing cache...")
        with open(cache_file, "wb") as f:
            pickle.dump(dets_by_frame, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"[✓] Cache saved: {cache_file.name} ({cache_file.stat().st_size / 1024:.1f} KB)")
        
    print("\n[✓] All holdout detections successfully cached!")


if __name__ == "__main__":
    main()
