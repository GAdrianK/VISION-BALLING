#!/usr/bin/env python3
"""
EXP-05: SoccerNet Tracking 2023 Baseline Benchmark Runner.

Executes temporal multi-object tracking evaluation of the frozen RF-DETR Small 960 px detector
combined with PlayerByteTrack and BallTrackManager on official SoccerNet Tracking 2023 sequences:
  - SNMOT-060 (Kick-off, 750 frames)
  - SNMOT-061 (Shots on target, 750 frames)
  - SNMOT-062 (Foul, 750 frames)

Evaluates:
  1. Class-agnostic tracking (official SoccerNet standard)
  2. PERSON tracking (players + referees + goalkeepers)
  3. BALL tracking (separate trajectory metrics & temporal diagnostics)
"""

from __future__ import annotations

import configparser
import hashlib
import json
import os
import subprocess
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from app.video_analysis.ball_tracker import BallTrackConfig, BallTrackManager
from app.video_analysis.benchmark_adapters import FrameGroundTruth, GroundTruthBox, MOTChallengeAdapter
from app.video_analysis.benchmark_metrics import TrackingEvaluator
from app.video_analysis.detectors import RFDETRDetector
from app.video_analysis.player_tracker import ByteTrackConfig, PlayerByteTrack
from app.video_analysis.tracking_diagnostics import compute_ball_diagnostics
from app.video_analysis.tracking_schemas import BallObservationState
from app.video_analysis.tracking_visualizer import draw_ball_track, draw_player_tracks


EXPECTED_CKPT_SHA256 = "c1a1d88b74edc5ddefa7da4581e2848c4c58c3938d88ad4a1b615f071752ffff"
DEFAULT_CKPT_PATH = Path("/media/adriano/Windows/runs/detect/exp04_rfdetr_small_h250_960/checkpoint_best_total.pth")
DEFAULT_DATASET_DIR = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train")
DEFAULT_OUTPUT_DIR = Path("/media/adriano/Windows/runs/tracking/exp05")
DEFAULT_REPORT_PATH = Path("docs/experiments/exp05_soccernet_tracking_baseline.json")

SEQUENCES = ["SNMOT-060", "SNMOT-061", "SNMOT-062"]


def get_git_commit() -> str:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return res.stdout.strip()
    except Exception:
        return "unknown"


def verify_checkpoint(ckpt_path: Path) -> str:
    if not ckpt_path.is_file():
        raise FileNotFoundError(f"Checkpoint EXP-04 introuvable : {ckpt_path}")
    data = ckpt_path.read_bytes()
    sha256 = hashlib.sha256(data).hexdigest()
    if sha256 != EXPECTED_CKPT_SHA256:
        raise ValueError(
            f"Altération du checkpoint détectée ! Obtenu: {sha256}, Attendu: {EXPECTED_CKPT_SHA256}"
        )
    return sha256


def parse_gameinfo_roles(gameinfo_path: Path) -> dict[int, str]:
    """
    Parses gameinfo.ini to extract ground truth role mapping per tracklet ID:
      - 'person' for player, goalkeeper, referee
      - 'ball' for ball
    """
    cp = configparser.ConfigParser()
    cp.read(gameinfo_path)
    seq_sec = cp["Sequence"]
    roles: dict[int, str] = {}
    for k, v in seq_sec.items():
        if k.startswith("trackletid_"):
            tid = int(k.replace("trackletid_", ""))
            role_part = v.split(";")[0].strip().lower()
            if role_part.startswith("ball"):
                roles[tid] = "ball"
            elif any(role_part.startswith(p) for p in ("player", "goalkeeper", "referee")):
                roles[tid] = "person"
            else:
                roles[tid] = f"unknown_{role_part}"
    return roles


def split_ground_truth(
    gt_all: dict[int, FrameGroundTruth],
    roles: dict[int, str],
) -> tuple[dict[int, FrameGroundTruth], dict[int, FrameGroundTruth]]:
    """Splits ground truth frames into person and ball subsets according to official roles."""
    gt_person: dict[int, FrameGroundTruth] = {}
    gt_ball: dict[int, FrameGroundTruth] = {}

    for f_idx, frame_gt in gt_all.items():
        person_boxes: list[GroundTruthBox] = []
        ball_boxes: list[GroundTruthBox] = []

        for ann in frame_gt.annotations:
            if ann.track_id is None:
                continue
            role = roles.get(ann.track_id, "unknown")
            if role == "person":
                person_boxes.append(
                    GroundTruthBox(
                        frame_index=ann.frame_index,
                        class_name="person",
                        bbox=ann.bbox,
                        track_id=ann.track_id,
                        confidence=ann.confidence,
                    )
                )
            elif role == "ball":
                ball_boxes.append(
                    GroundTruthBox(
                        frame_index=ann.frame_index,
                        class_name="sports ball",
                        bbox=ann.bbox,
                        track_id=ann.track_id,
                        confidence=ann.confidence,
                    )
                )

        gt_person[f_idx] = FrameGroundTruth(
            frame_index=f_idx,
            image_path=frame_gt.image_path,
            width=frame_gt.width,
            height=frame_gt.height,
            annotations=person_boxes,
        )
        gt_ball[f_idx] = FrameGroundTruth(
            frame_index=f_idx,
            image_path=frame_gt.image_path,
            width=frame_gt.width,
            height=frame_gt.height,
            annotations=ball_boxes,
        )

    return gt_person, gt_ball


def run_benchmark(max_frames: int | None = None) -> dict[str, Any]:
    print("=" * 70)
    print("EXP-05: SOCCERNET TRACKING 2023 BASELINE BENCHMARK")
    print("=" * 70)

    # 1. Provenance & Integrity checks
    git_head = get_git_commit()
    print(f"[*] Git HEAD commit: {git_head}")
    ckpt_sha = verify_checkpoint(DEFAULT_CKPT_PATH)
    print(f"[*] Checkpoint valid: {DEFAULT_CKPT_PATH} (SHA-256: {ckpt_sha})")

    DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 2. Load locked detector
    print("\n[*] Loading locked RF-DETR Small 960 px detector...")
    detector = RFDETRDetector(
        model_path=str(DEFAULT_CKPT_PATH),
        resolution=960,
        optimize_inference=True,
    )
    detector.load()
    print("[*] Detector loaded successfully with float16 inference.")

    evaluator = TrackingEvaluator(iou_threshold=0.5)

    per_sequence_results: dict[str, Any] = {}
    total_det_time = 0.0
    total_track_time = 0.0
    total_frames_processed = 0

    for seq_name in SEQUENCES:
        seq_dir = DEFAULT_DATASET_DIR / seq_name
        if not seq_dir.is_dir():
            raise FileNotFoundError(f"Sequence directory not found: {seq_dir}")

        print("\n" + "-" * 70)
        print(f"[*] Processing sequence: {seq_name}")
        print("-" * 70)

        seqinfo_path = seq_dir / "seqinfo.ini"
        gameinfo_path = seq_dir / "gameinfo.ini"
        gt_path = seq_dir / "gt" / "gt.txt"
        img1_dir = seq_dir / "img1"

        cp = configparser.ConfigParser()
        cp.read(seqinfo_path)
        seq_sec = cp["Sequence"]
        frame_rate = float(seq_sec.get("frameRate", 25.0))
        seq_length = int(seq_sec.get("seqLength", 750))
        if max_frames is not None:
            seq_length = min(seq_length, max_frames)
        im_width = int(seq_sec.get("imWidth", 1920))
        im_height = int(seq_sec.get("imHeight", 1080))
        im_ext = seq_sec.get("imExt", ".jpg")

        print(f"    FPS: {frame_rate}, Length: {seq_length} frames, Dimensions: {im_width}x{im_height}")

        # Parse ground truth & roles
        roles = parse_gameinfo_roles(gameinfo_path)
        print(f"    Official tracklet roles: {len(roles)} total (ball: {sum(1 for r in roles.values() if r == 'ball')}, person: {sum(1 for r in roles.values() if r == 'person')})")

        adapter = MOTChallengeAdapter(gt_file=gt_path, frames_dir=img1_dir)
        gt_all = adapter.load_dataset()
        gt_person, gt_ball = split_ground_truth(gt_all, roles)

        # Initialize fresh trackers for sequence
        # ByteTrack: 25 fps, track_activation_threshold=0.45, low_confidence_threshold=0.10, lost_track_buffer=30
        bytetrack_cfg = ByteTrackConfig(
            track_activation_threshold=0.45,
            low_confidence_threshold=0.10,
            lost_track_buffer=30,
            minimum_matching_threshold=0.80,
            frame_rate=frame_rate,
            minimum_consecutive_frames=1,
        )
        player_tracker = PlayerByteTrack(config=bytetrack_cfg)

        ball_cfg = BallTrackConfig(
            min_detection_confidence=0.25,
            max_gap_interpolation=15,
            max_velocity_pixels_per_frame=120.0,
            spatial_gate_base_distance=150.0,
            fps=frame_rate,
        )
        ball_tracker = BallTrackManager(config=ball_cfg)

        # Video writer for visual output (generate for SNMOT-060 or all)
        video_out_path = DEFAULT_OUTPUT_DIR / f"{seq_name}_baseline.mp4"
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        video_writer = cv2.VideoWriter(str(video_out_path), fourcc, frame_rate, (im_width, im_height))

        pred_all: dict[int, list[dict[str, Any]]] = {}
        pred_person: dict[int, list[dict[str, Any]]] = {}
        pred_ball: dict[int, list[dict[str, Any]]] = {}

        seq_det_time = 0.0
        seq_track_time = 0.0

        ball_trail: list[Any] = []

        print(f"    Running sequential inference and tracking on {seq_length} frames...")
        t_seq_start = time.perf_counter()

        for f_idx in range(1, seq_length + 1):
            frame_filename = f"{f_idx:06d}{im_ext}"
            frame_path = img1_dir / frame_filename
            frame = cv2.imread(str(frame_path))
            if frame is None:
                raise FileNotFoundError(f"Frame missing or unreadable: {frame_path}")

            timestamp = (f_idx - 1) / frame_rate

            # 1. Detection
            t_d0 = time.perf_counter()
            dets = detector.detect_for_tracking(frame)
            t_d1 = time.perf_counter()
            seq_det_time += (t_d1 - t_d0)

            # 2. Tracking
            t_t0 = time.perf_counter()
            p_tracks = player_tracker.update_tracks(
                frame_index=f_idx,
                timestamp=timestamp,
                detections=dets,
                source_detector="rf-detr-small",
            )
            b_obs = ball_tracker.update(
                frame_index=f_idx,
                timestamp=timestamp,
                detections=dets,
                source_detector="rf-detr-small",
            )
            t_t1 = time.perf_counter()
            seq_track_time += (t_t1 - t_t0)

            # 3. Format predictions
            f_persons: list[dict[str, Any]] = [
                {"track_id": p.track_id, "bbox": list(p.bbox), "confidence": p.confidence}
                for p in p_tracks
            ]
            pred_person[f_idx] = f_persons

            f_balls: list[dict[str, Any]] = []
            if b_obs.observation_state != BallObservationState.LOST:
                # Use track_id=1 for ball in ball evaluation
                f_balls.append({
                    "track_id": 1,
                    "bbox": list(b_obs.bbox),
                    "confidence": b_obs.confidence or 0.5,
                })
            pred_ball[f_idx] = f_balls

            # Class-agnostic combined (offset ball track_id by 10000 to prevent ID collision)
            f_all: list[dict[str, Any]] = list(f_persons)
            if b_obs.observation_state != BallObservationState.LOST:
                f_all.append({
                    "track_id": 10001,
                    "bbox": list(b_obs.bbox),
                    "confidence": b_obs.confidence or 0.5,
                })
            pred_all[f_idx] = f_all

            # 4. Render representative video
            ball_trail.append(b_obs)
            if len(ball_trail) > 30:
                ball_trail.pop(0)

            vis_frame = draw_player_tracks(frame, p_tracks)
            vis_frame = draw_ball_track(vis_frame, b_obs, trail=ball_trail)
            # Overlay info header
            header_text = (
                f"{seq_name} | Frame {f_idx:03d}/{seq_length:03d} | "
                f"Players: {len(p_tracks)} | Ball: {b_obs.observation_state.value}"
            )
            cv2.putText(
                vis_frame,
                header_text,
                (20, 40),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.9,
                (0, 255, 255),
                2,
                cv2.LINE_AA,
            )
            video_writer.write(vis_frame)

            if f_idx % 150 == 0 or f_idx == seq_length:
                elapsed = time.perf_counter() - t_seq_start
                fps = f_idx / elapsed
                print(f"      Frame {f_idx}/{seq_length} ({fps:.1f} FPS e2e)...")

        video_writer.release()
        print(f"    Visual output saved: {video_out_path}")

        # Metrics evaluation
        print("    Evaluating tracking metrics...")
        eval_agnostic = evaluator.evaluate(gt_all, pred_all, tracker_name="class_agnostic")
        eval_person = evaluator.evaluate(gt_person, pred_person, tracker_name="bytetrack_person")
        eval_ball = evaluator.evaluate(gt_ball, pred_ball, tracker_name="ball_tracker")

        ball_diag = compute_ball_diagnostics(ball_tracker.history)

        fps_tracking_only = seq_length / seq_track_time if seq_track_time > 0 else 0.0
        fps_e2e = seq_length / (seq_det_time + seq_track_time)

        total_det_time += seq_det_time
        total_track_time += seq_track_time
        total_frames_processed += seq_length

        print(f"    [CLASS-AGNOSTIC] HOTA@0.5: {eval_agnostic.hota_0_5:.4f} | DetA: {eval_agnostic.deta_0_5:.4f} | AssA: {eval_agnostic.assa_0_5:.4f} | IDF1: {eval_agnostic.idf1:.4f}")
        print(f"    [PERSON]         HOTA@0.5: {eval_person.hota_0_5:.4f} | DetA: {eval_person.deta_0_5:.4f} | AssA: {eval_person.assa_0_5:.4f} | IDF1: {eval_person.idf1:.4f}")
        print(f"    [BALL]           HOTA@0.5: {eval_ball.hota_0_5:.4f} | DetA: {eval_ball.deta_0_5:.4f} | AssA: {eval_ball.assa_0_5:.4f} | IDF1: {eval_ball.idf1:.4f}")
        print(f"    [THROUGHPUT]     Tracking-only: {fps_tracking_only:.1f} FPS | End-to-End: {fps_e2e:.1f} FPS")

        per_sequence_results[seq_name] = {
            "num_frames": seq_length,
            "fps": frame_rate,
            "roles_summary": {
                "total_gt_tracklets": len(roles),
                "person_gt_tracklets": sum(1 for r in roles.values() if r == "person"),
                "ball_gt_tracklets": sum(1 for r in roles.values() if r == "ball"),
            },
            "class_agnostic": {
                "hota_0_5": round(eval_agnostic.hota_0_5, 4),
                "deta_0_5": round(eval_agnostic.deta_0_5, 4),
                "assa_0_5": round(eval_agnostic.assa_0_5, 4),
                "idf1": round(eval_agnostic.idf1, 4),
                "num_gt_tracks": eval_agnostic.num_gt_tracks,
                "num_pred_tracks": eval_agnostic.num_pred_tracks,
            },
            "person": {
                "hota_0_5": round(eval_person.hota_0_5, 4),
                "deta_0_5": round(eval_person.deta_0_5, 4),
                "assa_0_5": round(eval_person.assa_0_5, 4),
                "idf1": round(eval_person.idf1, 4),
                "num_gt_tracks": eval_person.num_gt_tracks,
                "num_pred_tracks": eval_person.num_pred_tracks,
            },
            "ball": {
                "hota_0_5": round(eval_ball.hota_0_5, 4),
                "deta_0_5": round(eval_ball.deta_0_5, 4),
                "assa_0_5": round(eval_ball.assa_0_5, 4),
                "idf1": round(eval_ball.idf1, 4),
                "num_gt_tracks": eval_ball.num_gt_tracks,
                "num_pred_tracks": eval_ball.num_pred_tracks,
                "diagnostics": {
                    **ball_diag.to_dict(),
                    "rejected_velocity_jumps": ball_tracker.rejected_jump_count,
                },
            },
            "throughput": {
                "detection_time_seconds": round(seq_det_time, 3),
                "tracking_time_seconds": round(seq_track_time, 3),
                "total_time_seconds": round(seq_det_time + seq_track_time, 3),
                "fps_tracking_only": round(fps_tracking_only, 2),
                "fps_end_to_end": round(fps_e2e, 2),
            },
            "visual_artifact": str(video_out_path),
        }

    # 4. Macro-Averages calculation
    def _mean_metric(key: str, subkey: str) -> float:
        vals = [per_sequence_results[s][key][subkey] for s in SEQUENCES]
        return round(float(np.mean(vals)), 4)

    macro_results = {
        "class_agnostic": {
            "hota_0_5": _mean_metric("class_agnostic", "hota_0_5"),
            "deta_0_5": _mean_metric("class_agnostic", "deta_0_5"),
            "assa_0_5": _mean_metric("class_agnostic", "assa_0_5"),
            "idf1": _mean_metric("class_agnostic", "idf1"),
        },
        "person": {
            "hota_0_5": _mean_metric("person", "hota_0_5"),
            "deta_0_5": _mean_metric("person", "deta_0_5"),
            "assa_0_5": _mean_metric("person", "assa_0_5"),
            "idf1": _mean_metric("person", "idf1"),
        },
        "ball": {
            "hota_0_5": _mean_metric("ball", "hota_0_5"),
            "deta_0_5": _mean_metric("ball", "deta_0_5"),
            "assa_0_5": _mean_metric("ball", "assa_0_5"),
            "idf1": _mean_metric("ball", "idf1"),
            "mean_temporal_track_coverage": round(
                float(np.mean([per_sequence_results[s]["ball"]["diagnostics"]["temporal_track_coverage"] for s in SEQUENCES])),
                4,
            ),
        },
        "throughput": {
            "total_frames": total_frames_processed,
            "total_detection_time_seconds": round(total_det_time, 3),
            "total_tracking_time_seconds": round(total_track_time, 3),
            "macro_fps_tracking_only": round(total_frames_processed / total_track_time, 2),
            "macro_fps_end_to_end": round(total_frames_processed / (total_det_time + total_track_time), 2),
        },
    }

    report_payload = {
        "experiment": "exp05_soccernet_tracking_baseline",
        "description": "SoccerNet Tracking 2023 baseline using locked RF-DETR Small (960px) + PlayerByteTrack + BallTrackManager",
        "provenance": {
            "git_head": git_head,
            "detector_architecture": "RF-DETR Small",
            "detector_resolution": 960,
            "checkpoint_path": str(DEFAULT_CKPT_PATH),
            "checkpoint_sha256": ckpt_sha,
            "canonical_detector_person_threshold": 0.45,
            "canonical_detector_ball_threshold": 0.25,
            "tracking_person_low_confidence_floor": 0.10,
            "gpu": "NVIDIA GeForce RTX 4060 Laptop GPU",
        },
        "configurations": {
            "player_tracker": {
                "type": "PlayerByteTrack",
                "config": asdict(bytetrack_cfg),
            },
            "ball_tracker": {
                "type": "BallTrackManager",
                "config": asdict(ball_cfg),
            },
            "evaluation": {
                "engine": "built_in (TrackingEvaluator)",
                "iou_threshold": 0.5,
                "class_metadata_status": "A (100% reliable track_id -> role mapping via gameinfo.ini)",
            },
        },
        "macro_metrics": macro_results,
        "per_sequence_results": per_sequence_results,
        "conclusion": "EXP-05 baseline established on SoccerNet Tracking 2023. Baseline locked.",
    }

    DEFAULT_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DEFAULT_REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report_payload, f, indent=2)

    print("\n" + "=" * 70)
    print("EXP-05 BENCHMARK COMPLETE")
    print("=" * 70)
    print(f"Report written to: {DEFAULT_REPORT_PATH}")
    print(f"Class-Agnostic Macro: HOTA@0.5={macro_results['class_agnostic']['hota_0_5']}, IDF1={macro_results['class_agnostic']['idf1']}")
    print(f"PERSON Macro:         HOTA@0.5={macro_results['person']['hota_0_5']}, IDF1={macro_results['person']['idf1']}")
    print(f"BALL Macro:           HOTA@0.5={macro_results['ball']['hota_0_5']}, IDF1={macro_results['ball']['idf1']}")
    print(f"End-to-End Speed:     {macro_results['throughput']['macro_fps_end_to_end']} FPS")
    print("=" * 70)

    return report_payload


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run EXP-05 SoccerNet Tracking Baseline Benchmark.")
    parser.add_argument(
        "--max-frames",
        type=int,
        default=None,
        help="Optional ceiling on number of frames per sequence (for testing).",
    )
    args = parser.parse_args()
    run_benchmark(max_frames=args.max_frames)
