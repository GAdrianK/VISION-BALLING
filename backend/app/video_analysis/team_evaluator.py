"""
Chapter 6A: Team Attribution & Role Evaluation Module.
Evaluates predicted track-level team and role assignments against official SoccerNet
Tracking 2023 ground-truth (gameinfo.ini metadata) using permutation-invariant alignment.

Strict Isolation Guarantees:
  - Ground truth team and role labels are used EXCLUSIVELY for evaluation.
  - Zero leakage into model inference or feature aggregation.
  - Permutation-invariant: optimally maps neutral TEAM_0/TEAM_1 to GT team_left/team_right.
"""
from __future__ import annotations

import configparser
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

import numpy as np

from app.video_analysis.benchmark_adapters import MOTChallengeAdapter
from app.video_analysis.benchmark_metrics import compute_iou


@dataclass(frozen=True)
class GTTrackMetadata:
    """Ground truth identity metadata parsed from sequence gameinfo.ini."""
    track_id: int
    raw_role: str
    normalized_role: str  # "OUTFIELD_PLAYER", "GOALKEEPER", "REFEREE", "OTHER"
    team: str | None  # "team_left", "team_right", or None for referee/ball
    jersey_id: str | None


class SoccerNetGameStateAdapter:
    """
    Parses SoccerNet Tracking 2023 gameinfo.ini alongside gt.txt to extract
    official ground-truth team assignments and player roles.
    """

    @staticmethod
    def parse_gameinfo(gameinfo_path: Path | str) -> dict[int, GTTrackMetadata]:
        path = Path(gameinfo_path)
        if not path.is_file():
            raise FileNotFoundError(f"gameinfo.ini not found: {path}")

        cp = configparser.ConfigParser(strict=False)
        cp.read(str(path))
        if "Sequence" not in cp:
            raise ValueError(f"Invalid gameinfo.ini (missing [Sequence] section): {path}")

        results: dict[int, GTTrackMetadata] = {}
        sec = cp["Sequence"]

        for k, v in sec.items():
            if not k.startswith("trackletid_"):
                continue
            try:
                tid = int(k.replace("trackletid_", ""))
                parts = v.split(";")
                desc = parts[0].strip().lower()
                jersey_id = parts[1].strip() if len(parts) > 1 else None

                # Role and Team parsing
                team: str | None = None
                if "team left" in desc:
                    team = "team_left"
                elif "team right" in desc:
                    team = "team_right"

                if desc.startswith("goalkeeper"):
                    normalized_role = "GOALKEEPER"
                elif desc.startswith("referee"):
                    normalized_role = "REFEREE"
                    team = None
                elif desc.startswith("player"):
                    normalized_role = "OUTFIELD_PLAYER"
                elif desc.startswith("ball"):
                    normalized_role = "BALL"
                    team = None
                else:
                    normalized_role = "OTHER"

                results[tid] = GTTrackMetadata(
                    track_id=tid,
                    raw_role=desc,
                    normalized_role=normalized_role,
                    team=team,
                    jersey_id=jersey_id,
                )
            except Exception:
                continue

        return results


@dataclass
class TeamEvaluationResult:
    """Detailed metrics output from permutation-invariant team & role evaluation."""
    sequence_name: str
    optimal_mapping: dict[str, str]  # e.g. {"TEAM_0": "team_left", "TEAM_1": "team_right"}
    num_matched_outfield_tracks: int
    track_level_team_accuracy: float
    frame_weighted_team_accuracy: float
    balanced_team_accuracy: float
    confusion_matrix: dict[str, dict[str, int]]
    role_metrics: dict[str, dict[str, float]]  # role -> {"precision", "recall", "f1", "support"}
    intra_track_team_switches: int
    matched_track_details: list[dict[str, Any]] = field(default_factory=list)


class PermutationInvariantTeamEvaluator:
    """
    Evaluates unsupervised team and role assignments against ground truth.
    Solves the cluster permutation invariance by maximizing outfield player accuracy.
    """

    def __init__(self, iou_match_threshold: float = 0.50) -> None:
        self.iou_thresh = iou_match_threshold

    def match_predicted_to_gt_tracks(
        self,
        gt_by_frame: dict[int, Any],
        preds_by_frame: dict[int, list[dict[str, Any]]],
    ) -> dict[int, int]:
        """
        Matches each predicted track_id to the ground-truth track_id that maximizes
        the number of overlapping detections (IoU >= threshold) across all frames.
        Returns mapping: predicted_track_id -> gt_track_id.
        """
        overlap_counts: dict[int, dict[int, int]] = {}

        for f_idx, preds in preds_by_frame.items():
            if f_idx not in gt_by_frame:
                continue
            frame_gt = gt_by_frame[f_idx]
            gt_boxes = [(ann.track_id, ann.bbox) for ann in frame_gt.annotations if ann.track_id is not None]

            for p in preds:
                p_tid = int(p["track_id"])
                p_box = p["bbox"]
                if p_tid not in overlap_counts:
                    overlap_counts[p_tid] = {}

                for g_tid, g_box in gt_boxes:
                    iou = compute_iou(p_box, g_box)
                    if iou >= self.iou_thresh:
                        overlap_counts[p_tid][g_tid] = overlap_counts[p_tid].get(g_tid, 0) + 1

        matches: dict[int, int] = {}
        for p_tid, g_counts in overlap_counts.items():
            if g_counts:
                best_gt_id = max(g_counts.keys(), key=lambda k: g_counts[k])
                matches[p_tid] = best_gt_id

        return matches

    def evaluate(
        self,
        sequence_name: str,
        gt_metadata: dict[int, GTTrackMetadata],
        gt_by_frame: dict[int, Any],
        preds_by_frame: dict[int, list[dict[str, Any]]],
        track_attributes: dict[int, Any],  # track_id -> TrackIdentityAttributes
    ) -> TeamEvaluationResult:
        """
        Executes full evaluation:
          1. Matches predicted tracks to GT tracks.
          2. Optimally aligns TEAM_0 / TEAM_1 to team_left / team_right.
          3. Computes team accuracy (track and frame level) and role precision/recall/F1.
        """
        pred_to_gt = self.match_predicted_to_gt_tracks(gt_by_frame, preds_by_frame)

        # Count frames per predicted track
        pred_frame_counts: dict[int, int] = {}
        for preds in preds_by_frame.values():
            for p in preds:
                tid = int(p["track_id"])
                pred_frame_counts[tid] = pred_frame_counts.get(tid, 0) + 1

        # Identify outfield player tracks with ground-truth team
        outfield_pairs: list[tuple[int, int, str, str]] = []  # (p_tid, g_tid, pred_team, gt_team)
        for p_tid, g_tid in pred_to_gt.items():
            if g_tid not in gt_metadata:
                continue
            gt_meta = gt_metadata[g_tid]
            if gt_meta.normalized_role == "OUTFIELD_PLAYER" and gt_meta.team in ("team_left", "team_right"):
                attr = track_attributes.get(p_tid)
                pred_team = attr.team_label if attr else "UNKNOWN"
                outfield_pairs.append((p_tid, g_tid, pred_team, gt_meta.team))

        # Test both permutations of TEAM_0 / TEAM_1
        perm_a = {"TEAM_0": "team_left", "TEAM_1": "team_right", "UNKNOWN": "UNKNOWN"}
        perm_b = {"TEAM_0": "team_right", "TEAM_1": "team_left", "UNKNOWN": "UNKNOWN"}

        correct_a = sum(1 for _, _, p_team, g_team in outfield_pairs if perm_a.get(p_team) == g_team)
        correct_b = sum(1 for _, _, p_team, g_team in outfield_pairs if perm_b.get(p_team) == g_team)

        best_perm = perm_a if correct_a >= correct_b else perm_b
        best_correct_tracks = max(correct_a, correct_b)
        n_outfield_tracks = len(outfield_pairs)

        track_team_acc = float(best_correct_tracks / max(1, n_outfield_tracks))

        # Frame-weighted team accuracy
        total_outfield_frames = 0
        correct_outfield_frames = 0
        for p_tid, _, p_team, g_team in outfield_pairs:
            n_f = pred_frame_counts.get(p_tid, 1)
            total_outfield_frames += n_f
            if best_perm.get(p_team) == g_team:
                correct_outfield_frames += n_f

        frame_team_acc = float(correct_outfield_frames / max(1, total_outfield_frames))

        # Confusion Matrix & Balanced Accuracy
        cm = {
            "team_left": {"team_left": 0, "team_right": 0, "UNKNOWN": 0},
            "team_right": {"team_left": 0, "team_right": 0, "UNKNOWN": 0},
        }
        for _, _, p_team, g_team in outfield_pairs:
            mapped_pred = best_perm.get(p_team, "UNKNOWN")
            if g_team in cm:
                cm[g_team][mapped_pred] = cm[g_team].get(mapped_pred, 0) + 1

        rec_left = cm["team_left"]["team_left"] / max(1, sum(cm["team_left"].values()))
        rec_right = cm["team_right"]["team_right"] / max(1, sum(cm["team_right"].values()))
        balanced_acc = float((rec_left + rec_right) / 2.0)

        # Role Evaluation (OUTFIELD_PLAYER, GOALKEEPER, REFEREE)
        roles_to_eval = ["OUTFIELD_PLAYER", "GOALKEEPER", "REFEREE"]
        role_tp: dict[str, int] = {r: 0 for r in roles_to_eval}
        role_fp: dict[str, int] = {r: 0 for r in roles_to_eval}
        role_fn: dict[str, int] = {r: 0 for r in roles_to_eval}
        role_support: dict[str, int] = {r: 0 for r in roles_to_eval}

        matched_details: list[dict[str, Any]] = []

        for p_tid, g_tid in pred_to_gt.items():
            if g_tid not in gt_metadata:
                continue
            gt_meta = gt_metadata[g_tid]
            attr = track_attributes.get(p_tid)
            p_role = attr.role if attr else "UNKNOWN"
            g_role = gt_meta.normalized_role

            if g_role in role_support:
                role_support[g_role] += 1

            for r in roles_to_eval:
                if p_role == r and g_role == r:
                    role_tp[r] += 1
                elif p_role == r and g_role != r:
                    role_fp[r] += 1
                elif p_role != r and g_role == r:
                    role_fn[r] += 1

            matched_details.append({
                "pred_track_id": p_tid,
                "gt_track_id": g_tid,
                "gt_role": g_role,
                "pred_role": p_role,
                "gt_team": gt_meta.team,
                "pred_team_raw": attr.team_label if attr else "UNKNOWN",
                "pred_team_mapped": best_perm.get(attr.team_label if attr else "UNKNOWN", "UNKNOWN"),
                "confidence": attr.team_confidence if attr else 0.0,
                "evidence_crops": attr.evidence_count if attr else 0,
            })

        role_metrics: dict[str, dict[str, float]] = {}
        for r in roles_to_eval:
            tp = role_tp[r]
            fp = role_fp[r]
            fn = role_fn[r]
            prec = tp / max(1, tp + fp) if (tp + fp) > 0 else 0.0
            rec = tp / max(1, tp + fn) if (tp + fn) > 0 else 0.0
            f1 = (2 * prec * rec) / max(1e-6, prec + rec) if (prec + rec) > 0 else 0.0
            role_metrics[r] = {
                "precision": round(float(prec), 4),
                "recall": round(float(rec), 4),
                "f1": round(float(f1), 4),
                "support": role_support[r],
            }

        return TeamEvaluationResult(
            sequence_name=sequence_name,
            optimal_mapping={k: v for k, v in best_perm.items() if k != "UNKNOWN"},
            num_matched_outfield_tracks=n_outfield_tracks,
            track_level_team_accuracy=round(track_team_acc, 4),
            frame_weighted_team_accuracy=round(frame_team_acc, 4),
            balanced_team_accuracy=round(balanced_acc, 4),
            confusion_matrix=cm,
            role_metrics=role_metrics,
            intra_track_team_switches=0,  # Strict track-level assignment guarantee
            matched_track_details=matched_details,
        )
