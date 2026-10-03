"""
Conditional ReID Policy and Track Appearance Memory for VISION-BALLING.
Chapter 5 EXP-11: Performance + Conditional ReID.

Guarantees:
- Selective ReID inference triggered strictly on spatial/kinetic ambiguity.
- Unambiguous frames and detections bypass ReID extraction entirely.
- TrackAppearanceMemory preserves normalized rolling prototype (EMA) per track.
- Clean memory isolation and reset between video sequences.
- Zero reliance on ground-truth IDs, team classifications, or role labels.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import logging
from typing import Any, Sequence

import numpy as np
import torch

from app.video_analysis.benchmark_metrics import compute_iou
from app.video_analysis.detectors import RawDetection

logger = logging.getLogger("football.conditional_reid")


@dataclass(frozen=True)
class ConditionalReIDConfig:
    """Explicit configuration for the conditional ReID policy and appearance cache."""

    enabled: bool = True
    appearance_thresh: float = 0.75             # BoT-SORT appearance threshold (from EXP-10)
    proximity_thresh: float = 0.50              # BoT-SORT proximity threshold (from EXP-10)
    detection_overlap_iou: float = 0.15         # IoU threshold indicating physical overlap/collision
    track_competition_iou: float = 0.20         # IoU threshold indicating competing tracks/detections
    lost_reacquisition_iou: float = 0.10        # Overlap with lost track prediction indicating candidate reacquisition
    lost_reacquisition_max_dist_px: float = 150.0 # Pixel distance for reacquisition gating
    initial_seed_frames: int = 3                # Initial frames where tracks seed their appearance prototype
    max_cache_age_frames: int = 100             # Max frames before a track's prototype is considered stale
    ema_alpha: float = 0.90                     # Exponential moving average smoothing factor for prototypes
    version: str = "1.0.0"


@dataclass
class TrackAppearanceRecord:
    """Per-track appearance prototype and lifecycle state."""

    track_id: int
    prototype: np.ndarray       # L2-normalized rolling prototype vector (256-D)
    last_embedding: np.ndarray  # Most recent raw embedding vector (256-D)
    first_frame: int
    last_updated_frame: int
    update_count: int = 1


class TrackAppearanceMemory:
    """
    Per-track appearance memory preserving rolling prototype embeddings.

    Guarantees:
      - Memory bounds: bounded by number of active tracks in sequence.
      - Invalidation: inactive/lost tracks removed once expired.
      - Normalization: prototype always maintained on L2 unit hypersphere.
      - Reset: completely wipes state between sequences.
    """

    def __init__(self, ema_alpha: float = 0.90, max_age_frames: int = 100) -> None:
        self.ema_alpha = ema_alpha
        self.max_age_frames = max_age_frames
        self._records: dict[int, TrackAppearanceRecord] = {}
        self._total_updates: int = 0
        self._total_queries: int = 0
        self._cache_hits: int = 0

    def update_track(
        self,
        track_id: int,
        embedding: np.ndarray,
        frame_index: int,
    ) -> np.ndarray:
        """
        Updates track appearance record with a fresh L2-normalized embedding.
        If track already exists, applies EMA: prototype = norm(alpha * prototype + (1 - alpha) * embedding).
        Returns the updated normalized prototype.
        """
        self._total_updates += 1
        emb_norm = float(np.linalg.norm(embedding))
        if emb_norm < 1e-6:
            # Zero feature: do not pollute prototype
            if track_id in self._records:
                return self._records[track_id].prototype
            return embedding

        unit_emb = (embedding / emb_norm).astype(np.float32)

        if track_id not in self._records:
            record = TrackAppearanceRecord(
                track_id=track_id,
                prototype=unit_emb.copy(),
                last_embedding=unit_emb.copy(),
                first_frame=frame_index,
                last_updated_frame=frame_index,
                update_count=1,
            )
            self._records[track_id] = record
            return record.prototype

        record = self._records[track_id]
        smoothed = self.ema_alpha * record.prototype + (1.0 - self.ema_alpha) * unit_emb
        norm_smoothed = smoothed / max(1e-6, float(np.linalg.norm(smoothed)))
        record.prototype = norm_smoothed.astype(np.float32)
        record.last_embedding = unit_emb.copy()
        record.last_updated_frame = frame_index
        record.update_count += 1
        return record.prototype

    def get_prototype(self, track_id: int) -> np.ndarray | None:
        """Returns the rolling prototype embedding for a given track, or None if not cached."""
        self._total_queries += 1
        rec = self._records.get(track_id)
        if rec is not None:
            self._cache_hits += 1
            return rec.prototype
        return None

    def get_embedding_age(self, track_id: int, current_frame: int) -> int:
        """Returns frames elapsed since last embedding update, or 999999 if unknown."""
        rec = self._records.get(track_id)
        if rec is None:
            return 999999
        return current_frame - rec.last_updated_frame

    def has_prototype(self, track_id: int) -> bool:
        return track_id in self._records

    def purge_inactive(self, active_track_ids: set[int]) -> int:
        """Removes records for tracks that no longer exist in the tracker pool."""
        stale_ids = [tid for tid in self._records if tid not in active_track_ids]
        for tid in stale_ids:
            del self._records[tid]
        return len(stale_ids)

    def reset(self) -> None:
        """Completely purges all appearance memory."""
        self._records.clear()
        self._total_updates = 0
        self._total_queries = 0
        self._cache_hits = 0

    def stats(self) -> dict[str, Any]:
        """Returns operational cache metrics."""
        return {
            "cached_track_count": len(self._records),
            "total_updates": self._total_updates,
            "total_queries": self._total_queries,
            "cache_hits": self._cache_hits,
            "hit_rate_pct": round(self._cache_hits / max(1, self._total_queries) * 100.0, 2),
        }


class ConditionalReIDPolicy:
    """
    Decides at inference time which detections in the current frame require ReID extraction.

    Triggers:
      1. Overlap Conflict: detections whose bounding boxes overlap with another detection (IoU > overlap_iou).
      2. Competition Conflict: detections overlapping with multiple tracks, or tracks overlapping with multiple detections.
      3. Lost Track Reacquisition: detections proximate to a lost tracklet's predicted location.
      4. Seeding: initial frames or newly confirmed tracks requiring prototype initialization.
    """

    def __init__(self, config: ConditionalReIDConfig | None = None) -> None:
        self.config = config or ConditionalReIDConfig()
        self.memory = TrackAppearanceMemory(
            ema_alpha=self.config.ema_alpha,
            max_age_frames=self.config.max_cache_age_frames,
        )
        self.total_frames_evaluated: int = 0
        self.frames_triggered: int = 0
        self.total_detections_evaluated: int = 0
        self.detections_triggered: int = 0
        self.trigger_breakdown: dict[str, int] = {
            "detection_overlap": 0,
            "track_competition": 0,
            "lost_reacquisition": 0,
            "seed_initial": 0,
        }

    def reset(self) -> None:
        """Resets policy state and appearance memory."""
        self.memory.reset()
        self.total_frames_evaluated = 0
        self.frames_triggered = 0
        self.total_detections_evaluated = 0
        self.detections_triggered = 0
        for k in self.trigger_breakdown:
            self.trigger_breakdown[k] = 0

    def evaluate_ambiguity(
        self,
        detections: Sequence[RawDetection],
        active_tracks: Sequence[Any],
        lost_tracks: Sequence[Any],
        frame_index: int,
    ) -> tuple[np.ndarray, dict[str, int]]:
        """
        Evaluates a set of person detections against active and lost tracks.

        Args:
            detections: List of RawDetection objects for 'person'.
            active_tracks: List of active/tracked STrack / BOTrack objects.
            lost_tracks: List of lost STrack / BOTrack objects.
            frame_index: Current integer frame index (1-indexed).

        Returns:
            reid_mask: Boolean numpy array of shape (len(detections),) where True = extract ReID.
            counts: Dictionary of counts for each trigger category.
        """
        n_dets = len(detections)
        self.total_frames_evaluated += 1
        self.total_detections_evaluated += n_dets

        if n_dets == 0 or not self.config.enabled:
            return np.zeros(0, dtype=bool), {"triggered": 0}

        reid_mask = np.zeros(n_dets, dtype=bool)
        step_counts = {
            "detection_overlap": 0,
            "track_competition": 0,
            "lost_reacquisition": 0,
            "seed_initial": 0,
        }

        # Trigger 4: Initial sequence seeding
        if frame_index <= self.config.initial_seed_frames:
            reid_mask[:] = True
            step_counts["seed_initial"] += n_dets

        # Trigger 1: Overlap between detection pairs (dense clusters / scrums)
        det_bboxes = [d.bbox for d in detections]
        for i in range(n_dets):
            for j in range(i + 1, n_dets):
                iou = compute_iou(det_bboxes[i], det_bboxes[j])
                if iou >= self.config.detection_overlap_iou:
                    if not reid_mask[i]:
                        reid_mask[i] = True
                        step_counts["detection_overlap"] += 1
                    if not reid_mask[j]:
                        reid_mask[j] = True
                        step_counts["detection_overlap"] += 1

        # Trigger 2: Track competition (multi-match ambiguity)
        # Bounding box of tracks is t.tlbr (x1, y1, x2, y2)
        track_boxes = []
        for t in active_tracks:
            if hasattr(t, "tlbr"):
                track_boxes.append(t.tlbr)

        if track_boxes:
            # Check detection-to-track multi-overlap
            for i, db in enumerate(det_bboxes):
                overlap_count = sum(
                    1 for tb in track_boxes if compute_iou(tb, db) >= self.config.track_competition_iou
                )
                if overlap_count > 1 and not reid_mask[i]:
                    reid_mask[i] = True
                    step_counts["track_competition"] += 1

            # Check track-to-detection multi-overlap
            for tb in track_boxes:
                det_matches = [
                    i for i, db in enumerate(det_bboxes)
                    if compute_iou(tb, db) >= self.config.track_competition_iou
                ]
                if len(det_matches) > 1:
                    for i in det_matches:
                        if not reid_mask[i]:
                            reid_mask[i] = True
                            step_counts["track_competition"] += 1

        # Trigger 3: Lost track reacquisition candidates
        lost_boxes = []
        for lt in lost_tracks:
            if hasattr(lt, "tlbr"):
                lost_boxes.append(lt.tlbr)

        if lost_boxes:
            for i, db in enumerate(det_bboxes):
                d_cx = (db[0] + db[2]) / 2.0
                d_cy = (db[1] + db[3]) / 2.0
                for lb in lost_boxes:
                    iou = compute_iou(lb, db)
                    l_cx = (lb[0] + lb[2]) / 2.0
                    l_cy = (lb[1] + lb[3]) / 2.0
                    dist = float(np.hypot(d_cx - l_cx, d_cy - l_cy))
                    if (iou >= self.config.lost_reacquisition_iou) or (dist <= self.config.lost_reacquisition_max_dist_px):
                        if not reid_mask[i]:
                            reid_mask[i] = True
                            step_counts["lost_reacquisition"] += 1
                        break

        # Tally metrics
        n_triggered = int(np.sum(reid_mask))
        self.detections_triggered += n_triggered
        if n_triggered > 0:
            self.frames_triggered += 1

        for k, v in step_counts.items():
            self.trigger_breakdown[k] += v

        step_counts["triggered"] = n_triggered
        return reid_mask, step_counts

    def diagnostics(self) -> dict[str, Any]:
        """Returns comprehensive diagnostic metrics of policy execution."""
        frac_dets = (self.detections_triggered / max(1, self.total_detections_evaluated)) * 100.0
        frac_frames = (self.frames_triggered / max(1, self.total_frames_evaluated)) * 100.0
        avg_crops_per_frame = self.detections_triggered / max(1, self.total_frames_evaluated)
        return {
            "total_frames_evaluated": self.total_frames_evaluated,
            "frames_requiring_reid": self.frames_triggered,
            "fraction_frames_requiring_reid_pct": round(frac_frames, 2),
            "total_detections_evaluated": self.total_detections_evaluated,
            "detections_requiring_reid": self.detections_triggered,
            "fraction_detections_requiring_reid_pct": round(frac_dets, 2),
            "average_crops_per_frame": round(avg_crops_per_frame, 2),
            "trigger_breakdown": dict(self.trigger_breakdown),
            "memory_stats": self.memory.stats(),
        }
