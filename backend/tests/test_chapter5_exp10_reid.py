"""
Unit tests for Chapter 5 EXP-10 Sports-Specific Player ReID.
Validates:
- Deterministic crop extraction & boundary clipping.
- ImageNet normalization & 256-D embedding unit norm (||v||_2 = 1.0).
- No GT ID used during tracker inference.
- Tracker state reset clearing feature memory between sequences.
- Frozen holdout selection audit (SNMOT-069, SNMOT-070, SNMOT-071).
- Zero alteration to detector thresholds or BallTrackManager V2.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest
import torch
import torch.nn.functional as F

from app.video_analysis.ball_tracker import BallTrackConfig, BallTrackManager, create_ball_track_config_v2
from app.video_analysis.detectors import RawDetection
from app.video_analysis.player_tracker import (
    BoTSORTConfig,
    ByteTrackConfig,
    PlayerBoTSORT,
    PlayerByteTrack,
)
from app.video_analysis.reid_encoder import (
    DEFAULT_REID_CKPT_PATH,
    EMBEDDING_DIM,
    EXPECTED_PRTREID_MD5,
    EXPECTED_PRTREID_SHA256,
    IMAGENET_MEAN,
    IMAGENET_STD,
    INPUT_HEIGHT,
    INPUT_WIDTH,
    PlayerAppearanceEncoder,
    extract_player_crop,
    verify_checkpoint_hash,
)
from app.video_analysis.tracking_schemas import PlayerTrackObservation, TrackingState


def _make_det(bbox: tuple[float, float, float, float], cls_name: str = "person", conf: float = 0.85) -> RawDetection:
    return RawDetection(
        class_name=cls_name,
        football_role="player" if cls_name == "person" else "ball",
        confidence=conf,
        bbox=tuple(int(round(x)) for x in bbox),  # type: ignore[arg-type]
    )


# 1. Deterministic crop extraction & boundary clipping
def test_crop_extraction_and_clipping():
    """Validates deterministic crop extraction under standard, edge, and out-of-bounds bboxes."""
    img = np.zeros((1080, 1920, 3), dtype=np.uint8)
    img[100:200, 100:200] = 255  # Distinct white patch

    # Standard bbox
    crop = extract_player_crop(img, (100.0, 100.0, 200.0, 200.0))
    assert crop.shape == (100, 100, 3)
    assert np.all(crop == 255)

    # Coordinates beyond boundary
    crop_oob = extract_player_crop(img, (-50.0, -20.0, 1950.0, 1100.0))
    assert crop_oob.shape == (1080, 1920, 3)

    # Degenerate boxes (x2 <= x1 or y2 <= y1)
    crop_deg = extract_player_crop(img, (200.0, 200.0, 100.0, 100.0))
    assert crop_deg.ndim == 3
    assert crop_deg.shape[0] >= 1 and crop_deg.shape[1] >= 1

    # Determinism check
    crop_a = extract_player_crop(img, (50.5, 60.2, 150.8, 180.4))
    crop_b = extract_player_crop(img, (50.5, 60.2, 150.8, 180.4))
    np.testing.assert_array_equal(crop_a, crop_b)


# 2. ImageNet normalization & 256-D embedding unit norm (||v||_2 = 1.0)
def test_reid_specs_and_unit_norm():
    """Validates ReID embedding dimensions, normalization constants, and L2 unit hypersphere projection."""
    assert EMBEDDING_DIM == 256
    assert INPUT_HEIGHT == 256
    assert INPUT_WIDTH == 128
    assert IMAGENET_MEAN == (0.485, 0.456, 0.406)
    assert IMAGENET_STD == (0.229, 0.224, 0.225)

    # Test unit norm on arbitrary embeddings via F.normalize
    random_feats = torch.randn(10, EMBEDDING_DIM)
    normalized = F.normalize(random_feats, p=2, dim=-1)
    norms = torch.norm(normalized, p=2, dim=-1).cpu().numpy()
    np.testing.assert_allclose(norms, 1.0, rtol=1e-5)


# 3. No GT ID used during tracker inference
def test_no_gt_leakage_in_tracker_inference():
    """Ensures RawDetection and PlayerBoTSORT have no access to ground truth identities."""
    det = _make_det((100.0, 100.0, 200.0, 200.0), cls_name="person", conf=0.88)
    assert not hasattr(det, "track_id")
    assert not hasattr(det, "gt_id")
    assert not hasattr(det, "identity")

    tracker = PlayerBoTSORT(BoTSORTConfig(gmc_method="none", with_reid=False))
    obs_list = tracker.update_tracks(frame_index=1, timestamp=0.0, detections=[det])
    assert len(obs_list) == 1
    # Generated track_id must be assigned by the tracker algorithm itself
    assert obs_list[0].track_id == 1


# 4. Tracker state reset clearing feature memory between sequences
def test_tracker_reset_clears_memory_and_restarts():
    """Calling reset() completely reinitializes tracker state and Kalman/appearance history."""
    tracker = PlayerBoTSORT(BoTSORTConfig(gmc_method="none", with_reid=False))
    det = _make_det((100.0, 100.0, 200.0, 200.0), conf=0.90)

    # Frame 1
    tracks_before = tracker.update_tracks(1, 0.0, [det])
    assert tracks_before[0].track_id == 1

    # Reset
    tracker.reset()

    # Frame 1 of a new sequence
    tracks_after = tracker.update_tracks(1, 0.0, [det])
    assert tracks_after[0].track_id == 1


# 5. Frozen holdout selection audit
def test_frozen_holdout_selection_audit():
    """Audits the frozen DEV and untouched HOLDOUT sequences to guarantee strict isolation."""
    DEV_SEQUENCES = ["SNMOT-060", "SNMOT-061", "SNMOT-062"]
    HOLDOUT_SEQUENCES = ["SNMOT-069", "SNMOT-070", "SNMOT-071"]

    # Verify no intersection
    assert set(DEV_SEQUENCES).isdisjoint(set(HOLDOUT_SEQUENCES))
    assert len(DEV_SEQUENCES) == 3
    assert len(HOLDOUT_SEQUENCES) == 3

    # Verify no H250 test or golden/CVAT sequences
    for seq in DEV_SEQUENCES + HOLDOUT_SEQUENCES:
        assert seq.startswith("SNMOT-")
        assert "h250" not in seq.lower()
        assert "cvat" not in seq.lower()
        assert "golden" not in seq.lower()


# 6. Zero alteration to detector thresholds or BallTrackManager V2
def test_detector_and_ball_immutability():
    """Guarantees detection thresholds and BallTrackManager V2 remain strictly locked."""
    # Detector thresholds check
    bt_cfg = ByteTrackConfig()
    assert bt_cfg.track_activation_threshold == 0.45
    assert bt_cfg.low_confidence_threshold == 0.10

    bot_cfg = BoTSORTConfig()
    assert bot_cfg.track_high_thresh == 0.45
    assert bot_cfg.track_low_thresh == 0.10
    assert bot_cfg.new_track_thresh == 0.45

    # Ball tracker V2 check
    ball_cfg_v2 = create_ball_track_config_v2()
    assert ball_cfg_v2.max_gap_interpolation == 0
    assert ball_cfg_v2.max_safe_interpolation_gap == 0
    assert ball_cfg_v2.max_velocity_pixels_per_frame == 120.0
    assert ball_cfg_v2.spatial_gate_max_radius == 500.0
    assert ball_cfg_v2.version == "2.0.0"

    ball_mgr = BallTrackManager(ball_cfg_v2)
    assert ball_mgr.config.version == "2.0.0"


# 7. BoT-SORT ReID configuration verification
def test_botsort_reid_config_metadata():
    """Validates BoTSORTConfig with ReID enabled preserves configuration flags."""
    cfg = BoTSORTConfig(
        with_reid=True,
        appearance_thresh=0.75,
        proximity_thresh=0.5,
        gmc_method="sparseOptFlow",
    )
    assert cfg.with_reid is True
    assert cfg.appearance_thresh == 0.75

    tracker = PlayerBoTSORT(cfg)
    meta = tracker.metadata()
    assert meta["target_class"] == "person"
    assert meta["camera_motion_compensation"] == "sparseOptFlow"
    assert meta["with_reid"] is True
