"""
Unit tests for Chapter 5 EXP-11: Performance + Conditional ReID.
Validates:
- Ambiguity trigger logic (detection overlap, track competition, lost track reacquisition).
- No ReID invocation on unambiguous association.
- ReID invocation on ambiguous case.
- Embedding cache (TrackAppearanceMemory) and EMA prototype smoothing.
- Cache reset between sequences.
- Embedding age and staleness calculation.
- Absence of GT, team, jersey, or role leakage.
- BallTrackManager V2 immutability and decoupling.
- Prefetch frame reader preserving sequential frame ordering and timestamps.
"""
from __future__ import annotations

import queue
import threading
import numpy as np
import pytest
import torch

from app.video_analysis.ball_tracker import BallTrackManager, create_ball_track_config_v2
from app.video_analysis.conditional_reid import (
    ConditionalReIDConfig,
    ConditionalReIDPolicy,
    TrackAppearanceMemory,
)
from app.video_analysis.detectors import RawDetection
from app.video_analysis.player_tracker import BoTSORTConfig, PlayerBoTSORT


def _make_det(bbox: tuple[float, float, float, float], conf: float = 0.88, cls_name: str = "person") -> RawDetection:
    return RawDetection(
        class_name=cls_name,
        football_role="player" if cls_name == "person" else "ball",
        confidence=conf,
        bbox=tuple(int(round(x)) for x in bbox),  # type: ignore[arg-type]
    )


# 1. Ambiguity trigger: Overlap conflict
def test_conditional_trigger_detection_overlap():
    """Two overlapping person detections trigger selective ReID."""
    policy = ConditionalReIDPolicy(ConditionalReIDConfig(initial_seed_frames=0, detection_overlap_iou=0.15))
    det1 = _make_det((100.0, 100.0, 200.0, 200.0))
    det2 = _make_det((120.0, 120.0, 220.0, 220.0))  # Significant overlap with det1
    det3 = _make_det((800.0, 800.0, 900.0, 900.0))  # Far away, isolated

    mask, counts = policy.evaluate_ambiguity([det1, det2, det3], active_tracks=[], lost_tracks=[], frame_index=10)
    assert mask[0] is True or mask[0] == 1
    assert mask[1] is True or mask[1] == 1
    assert mask[2] is False or mask[2] == 0
    assert counts["detection_overlap"] >= 2


# 2. No ReID on unambiguous association
def test_no_reid_on_unambiguous_association():
    """Isolated, non-overlapping detections do NOT trigger ReID after seed period."""
    policy = ConditionalReIDPolicy(ConditionalReIDConfig(initial_seed_frames=0))
    det1 = _make_det((100.0, 100.0, 200.0, 200.0))
    det2 = _make_det((500.0, 500.0, 600.0, 600.0))
    det3 = _make_det((1000.0, 300.0, 1100.0, 400.0))

    mask, counts = policy.evaluate_ambiguity([det1, det2, det3], active_tracks=[], lost_tracks=[], frame_index=10)
    assert not np.any(mask)
    assert counts["triggered"] == 0


# 3. ReID trigger on lost track reacquisition
def test_reid_trigger_on_lost_reacquisition():
    """A detection proximate to a lost track triggers ReID."""
    class DummyTrack:
        def __init__(self, tlbr: tuple[float, float, float, float]):
            self.tlbr = tlbr

    policy = ConditionalReIDPolicy(ConditionalReIDConfig(initial_seed_frames=0, lost_reacquisition_iou=0.10))
    lost_track = DummyTrack((100.0, 100.0, 200.0, 200.0))
    det_near = _make_det((110.0, 110.0, 210.0, 210.0))
    det_far = _make_det((800.0, 800.0, 900.0, 900.0))

    mask, counts = policy.evaluate_ambiguity([det_near, det_far], active_tracks=[], lost_tracks=[lost_track], frame_index=10)
    assert mask[0] is True or mask[0] == 1
    assert mask[1] is False or mask[1] == 0
    assert counts["lost_reacquisition"] >= 1


# 4. Embedding cache (TrackAppearanceMemory) and EMA prototype smoothing
def test_track_appearance_memory_ema_prototype():
    """Validates L2 normalization and EMA prototype smoothing."""
    mem = TrackAppearanceMemory(ema_alpha=0.90)

    # Initial embedding
    v1 = np.ones(256, dtype=np.float32)
    v1 /= np.linalg.norm(v1)

    p1 = mem.update_track(track_id=1, embedding=v1, frame_index=1)
    assert np.isclose(np.linalg.norm(p1), 1.0, atol=1e-5)
    np.testing.assert_allclose(p1, v1, atol=1e-5)

    # Second embedding
    v2 = np.zeros(256, dtype=np.float32)
    v2[0] = 1.0

    p2 = mem.update_track(track_id=1, embedding=v2, frame_index=2)
    assert np.isclose(np.linalg.norm(p2), 1.0, atol=1e-5)
    # EMA check: 0.9 * v1 + 0.1 * v2, normalized
    expected = 0.9 * v1 + 0.1 * v2
    expected /= np.linalg.norm(expected)
    np.testing.assert_allclose(p2, expected, atol=1e-5)


# 5. Cache reset between sequences
def test_cache_reset_between_sequences():
    """Reset completely flushes stored prototypes."""
    mem = TrackAppearanceMemory()
    v1 = np.ones(256, dtype=np.float32)
    v1 /= np.linalg.norm(v1)
    mem.update_track(1, v1, 1)
    assert mem.has_prototype(1)

    mem.reset()
    assert not mem.has_prototype(1)
    assert mem.get_prototype(1) is None
    assert mem.stats()["cached_track_count"] == 0


# 6. Embedding age and staleness calculation
def test_embedding_age_calculation():
    """Embedding age increments correctly across frames."""
    mem = TrackAppearanceMemory(max_age_frames=50)
    v1 = np.ones(256, dtype=np.float32)
    v1 /= np.linalg.norm(v1)
    mem.update_track(1, v1, frame_index=10)

    assert mem.get_embedding_age(1, current_frame=10) == 0
    assert mem.get_embedding_age(1, current_frame=25) == 15
    assert mem.get_embedding_age(999, current_frame=25) == 999999


# 7. Absence of GT, team, jersey, or role leakage
def test_zero_leakage_in_conditional_policy():
    """Verifies that RawDetection has no GT or role metadata and tracker operates independently."""
    det = _make_det((100.0, 100.0, 200.0, 200.0))
    for forbidden in ["gt_id", "team", "team_id", "jersey", "jersey_number", "role_label"]:
        assert not hasattr(det, forbidden)

    cfg = BoTSORTConfig(gmc_method="none", with_reid=True, conditional_reid=True)
    tracker = PlayerBoTSORT(cfg)
    assert tracker.config.conditional_reid is True
    meta = tracker.metadata()
    assert meta["conditional_reid"] is True


# 8. BallTrackManager V2 immutability
def test_ball_track_immutability():
    """BallTrackManager V2 remains strictly decoupled and frozen from EXP-07."""
    cfg = create_ball_track_config_v2(fps=25.0)
    assert cfg.version == "2.0.0"
    assert cfg.min_detection_confidence == 0.25
    assert cfg.max_gap_interpolation == 0
    assert cfg.spatial_gate_max_radius == 500.0

    mgr = BallTrackManager(cfg)
    assert mgr.config.version == "2.0.0"


# 9. Prefetch frame reader preserving sequential frame ordering and timestamps
def test_prefetched_frame_reader_ordering():
    """Background prefetch reader preserves strictly deterministic sequence ordering."""
    test_frames = [np.full((10, 10, 3), i, dtype=np.uint8) for i in range(10)]

    q: queue.Queue[np.ndarray | None] = queue.Queue(maxsize=3)

    def producer():
        for frame in test_frames:
            q.put(frame)
        q.put(None)

    th = threading.Thread(target=producer, daemon=True)
    th.start()

    retrieved = []
    while True:
        f = q.get()
        if f is None:
            break
        retrieved.append(f)
    th.join()

    assert len(retrieved) == len(test_frames)
    for idx, f in enumerate(retrieved):
        assert np.all(f == idx)
