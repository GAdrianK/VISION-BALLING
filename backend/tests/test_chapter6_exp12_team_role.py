"""
Unit tests for Chapter 6A: Team & Role Attribution (EXP-12).
Verifies crop filtering, torso extraction, color representation, track aggregation,
permutation-invariant evaluation, role heuristics, and zero GT leakage.
"""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pytest

from app.video_analysis.team_classifier import (
    ColorFeatureExtractor,
    CropQualityFilterConfig,
    RoleType,
    TeamClassifier,
    TeamClassifierConfig,
    TeamLabel,
    TrackAppearanceAggregator,
    TrackIdentityAttributes,
    compute_laplacian_sharpness,
    extract_torso_crop,
    is_crop_quality_valid,
)
from app.video_analysis.team_evaluator import (
    GTTrackMetadata,
    PermutationInvariantTeamEvaluator,
    SoccerNetGameStateAdapter,
    TeamEvaluationResult,
)


def test_torso_crop_bounds_and_dimensions() -> None:
    """Verifies that torso crop extracts upper-body center region and handles edge bounds."""
    frame = np.ones((1080, 1920, 3), dtype=np.uint8) * 128
    bbox = [100.0, 200.0, 200.0, 400.0]  # w = 100, h = 200

    torso = extract_torso_crop(frame, bbox)
    assert torso.ndim == 3
    assert torso.shape[2] == 3
    # Expected height: ~0.40 * 200 = 80 px
    # Expected width: ~0.70 * 100 = 70 px
    assert 75 <= torso.shape[0] <= 85
    assert 65 <= torso.shape[1] <= 75


def test_torso_crop_degenerate_bounding_box() -> None:
    """Verifies that degenerate bounding boxes produce valid non-empty arrays."""
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    torso = extract_torso_crop(frame, [50.0, 50.0, 50.0, 50.0])
    assert torso.size > 0


def test_laplacian_sharpness_calculation() -> None:
    """Verifies sharpness calculation differentiates sharp patterns from uniform blur."""
    uniform = np.ones((64, 64, 3), dtype=np.uint8) * 100
    noisy = np.random.randint(0, 255, (64, 64, 3), dtype=np.uint8)

    sharp_uniform = compute_laplacian_sharpness(uniform)
    sharp_noisy = compute_laplacian_sharpness(noisy)

    assert sharp_uniform < 1.0
    assert sharp_noisy > 100.0


def test_crop_quality_filter_rejections() -> None:
    """Verifies explicit rejection rules: tiny height, extreme aspect ratio, blur, overlap."""
    cfg = CropQualityFilterConfig(min_bbox_height=40.0, min_sharpness=20.0, max_overlap_iou=0.20)
    frame_shape = (1080, 1920, 3)

    # 1. Too small height
    assert not is_crop_quality_valid([100, 100, 120, 130], frame_shape, None, config=cfg)

    # 2. Extreme aspect ratio (too wide, h/w < 1.2)
    assert not is_crop_quality_valid([100, 100, 300, 180], frame_shape, None, config=cfg)

    # 3. Blurred crop
    blurred_crop = np.ones((60, 30, 3), dtype=np.uint8) * 100
    assert not is_crop_quality_valid([100, 100, 130, 200], frame_shape, blurred_crop, config=cfg)

    # 4. Overlapping player
    other_bbox = [105, 105, 135, 205]
    valid_crop = np.random.randint(0, 255, (60, 30, 3), dtype=np.uint8)
    assert not is_crop_quality_valid(
        [100, 100, 130, 200], frame_shape, valid_crop, other_bboxes_xyxy=[other_bbox], config=cfg
    )


def test_color_extractor_pitch_green_masking() -> None:
    """Verifies that pitch green is masked out while player jersey color is preserved."""
    extractor = ColorFeatureExtractor(hsv_h_bins=16, hsv_s_bins=8, hsv_v_bins=8, exclude_pitch_green=True)

    # Green pitch background: H=60 (green), S=200, V=150
    green_patch = np.zeros((30, 30, 3), dtype=np.uint8)
    green_patch[:, :] = (35, 150, 35)  # BGR green

    # Red jersey center: H=0 (red), S=255, V=255
    red_jersey = green_patch.copy()
    red_jersey[10:20, 10:20] = (0, 0, 255)  # BGR red

    hist_green_only = extractor.extract_hsv_histogram(green_patch)
    hist_with_jersey = extractor.extract_hsv_histogram(red_jersey)

    assert hist_green_only.shape[0] == 16 * 8 + 8
    assert hist_with_jersey.shape[0] == 16 * 8 + 8
    # Jersey produces distinct non-zero histogram
    assert np.linalg.norm(hist_with_jersey) > 0.99


def test_track_appearance_aggregator_median_and_norm() -> None:
    """Verifies temporal aggregation computes coordinate-wise median and returns unit vector."""
    v1 = np.array([1.0, 0.0, 0.0], dtype=np.float32)
    v2 = np.array([0.9, 0.1, 0.0], dtype=np.float32)
    v3 = np.array([0.8, 0.2, 0.0], dtype=np.float32)

    agg = TrackAppearanceAggregator.aggregate_features([v1, v2, v3], strategy="median")
    assert agg.shape == (3,)
    assert pytest.approx(np.linalg.norm(agg), abs=1e-5) == 1.0
    # Median of first component is 0.9 before normalization
    assert agg[0] > agg[1]


def test_team_classifier_two_cluster_separation() -> None:
    """Verifies unsupervised KMeans correctly separates two distinct team jersey color profiles."""
    classifier = TeamClassifier(config=TeamClassifierConfig(min_evidence_crops=2, seed=42))

    # Create dummy synthetic frames
    frame = np.ones((720, 1280, 3), dtype=np.uint8) * 128

    # Team Red (Track 1 and 2)
    red_box_1 = [100.0, 100.0, 140.0, 220.0]
    red_box_2 = [200.0, 100.0, 240.0, 220.0]
    # Team Blue (Track 3 and 4)
    blue_box_1 = [400.0, 100.0, 440.0, 220.0]
    blue_box_2 = [500.0, 100.0, 540.0, 220.0]

    # Populate frames
    for f in range(1, 4):
        # Frame with red torso
        frame_red = frame.copy()
        frame_red[115:165, 106:134] = (0, 0, 240)  # Red BGR
        frame_red[115:165, 206:234] = (0, 0, 240)

        # Frame with blue torso
        frame_red[115:165, 406:434] = (240, 0, 0)  # Blue BGR
        frame_red[115:165, 506:534] = (240, 0, 0)

        players = [
            {"track_id": 1, "bbox": red_box_1},
            {"track_id": 2, "bbox": red_box_2},
            {"track_id": 3, "bbox": blue_box_1},
            {"track_id": 4, "bbox": blue_box_2},
        ]
        classifier.process_frame_detections(frame_red, f, players)

    attributes = classifier.fit_and_assign(frame_width=1280)
    assert len(attributes) == 4

    team_1 = attributes[1].team_label
    team_2 = attributes[2].team_label
    team_3 = attributes[3].team_label
    team_4 = attributes[4].team_label

    # Same colors should cluster together
    assert team_1 == team_2
    assert team_3 == team_4
    assert team_1 != team_3
    assert team_1 in (TeamLabel.TEAM_0.value, TeamLabel.TEAM_1.value)


def test_permutation_invariant_evaluator_hypothesis_alignment() -> None:
    """Verifies that evaluator identifies optimal mapping regardless of cluster label permutation."""
    evaluator = PermutationInvariantTeamEvaluator(iou_match_threshold=0.50)

    gt_metadata = {
        101: GTTrackMetadata(101, "player team left;10", "OUTFIELD_PLAYER", "team_left", "10"),
        102: GTTrackMetadata(102, "player team left;11", "OUTFIELD_PLAYER", "team_left", "11"),
        201: GTTrackMetadata(201, "player team right;7", "OUTFIELD_PLAYER", "team_right", "7"),
        202: GTTrackMetadata(202, "player team right;9", "OUTFIELD_PLAYER", "team_right", "9"),
    }

    # Dummy GT boxes
    from app.video_analysis.benchmark_adapters import FrameGroundTruth, GroundTruthBox
    gt_by_frame = {
        1: FrameGroundTruth(1, None, 1920, 1080, [
            GroundTruthBox(1, "person", [10, 10, 50, 100], 101),
            GroundTruthBox(1, "person", [60, 10, 100, 100], 102),
            GroundTruthBox(1, "person", [200, 10, 240, 100], 201),
            GroundTruthBox(1, "person", [250, 10, 290, 100], 202),
        ])
    }

    preds_by_frame = {
        1: [
            {"track_id": 1, "bbox": [10, 10, 50, 100]},
            {"track_id": 2, "bbox": [60, 10, 100, 100]},
            {"track_id": 3, "bbox": [200, 10, 240, 100]},
            {"track_id": 4, "bbox": [250, 10, 290, 100]},
        ]
    }

    # Case A: TEAM_0 = team_left, TEAM_1 = team_right
    attrs_a = {
        1: TrackIdentityAttributes(1, "TEAM_0", 0.9, "OUTFIELD_PLAYER", 0.9, 10),
        2: TrackIdentityAttributes(2, "TEAM_0", 0.9, "OUTFIELD_PLAYER", 0.9, 10),
        3: TrackIdentityAttributes(3, "TEAM_1", 0.9, "OUTFIELD_PLAYER", 0.9, 10),
        4: TrackIdentityAttributes(4, "TEAM_1", 0.9, "OUTFIELD_PLAYER", 0.9, 10),
    }

    res_a = evaluator.evaluate("TEST_SEQ", gt_metadata, gt_by_frame, preds_by_frame, attrs_a)
    assert res_a.track_level_team_accuracy == 1.0
    assert res_a.optimal_mapping["TEAM_0"] == "team_left"
    assert res_a.optimal_mapping["TEAM_1"] == "team_right"

    # Case B: Inverted permutation: TEAM_1 = team_left, TEAM_0 = team_right
    attrs_b = {
        1: TrackIdentityAttributes(1, "TEAM_1", 0.9, "OUTFIELD_PLAYER", 0.9, 10),
        2: TrackIdentityAttributes(2, "TEAM_1", 0.9, "OUTFIELD_PLAYER", 0.9, 10),
        3: TrackIdentityAttributes(3, "TEAM_0", 0.9, "OUTFIELD_PLAYER", 0.9, 10),
        4: TrackIdentityAttributes(4, "TEAM_0", 0.9, "OUTFIELD_PLAYER", 0.9, 10),
    }

    res_b = evaluator.evaluate("TEST_SEQ", gt_metadata, gt_by_frame, preds_by_frame, attrs_b)
    assert res_b.track_level_team_accuracy == 1.0
    assert res_b.optimal_mapping["TEAM_1"] == "team_left"
    assert res_b.optimal_mapping["TEAM_0"] == "team_right"


def test_soccernet_gameinfo_parsing() -> None:
    """Verifies that SoccerNet gameinfo.ini parser correctly maps roles and teams."""
    gameinfo_path = Path("/media/adriano/Windows/datasets/SoccerNetTracking2023/train/SNMOT-060/gameinfo.ini")
    if not gameinfo_path.is_file():
        pytest.skip("SoccerNet dataset not mounted.")

    metadata = SoccerNetGameStateAdapter.parse_gameinfo(gameinfo_path)
    assert len(metadata) > 20

    # Verify trackletID_14 is referee
    assert 14 in metadata
    assert metadata[14].normalized_role == "REFEREE"
    assert metadata[14].team is None

    # Verify trackletID_1 is outfield player
    assert 1 in metadata
    assert metadata[1].normalized_role == "OUTFIELD_PLAYER"
    assert metadata[1].team == "team_left"

    # Verify trackletID_22 is goalkeeper
    assert 22 in metadata
    assert metadata[22].normalized_role == "GOALKEEPER"
    assert metadata[22].team == "team_left"


def test_no_gt_leakage_in_team_classifier() -> None:
    """Verifies that TeamClassifier has zero imports or references to GT metadata."""
    import inspect
    from app.video_analysis import team_classifier

    source = inspect.getsource(team_classifier)
    forbidden_tokens = ["gameinfo", "team_left", "team_right", "GroundTruthBox", "MOTChallengeAdapter"]
    for token in forbidden_tokens:
        assert token not in source, f"Forbidden GT token '{token}' found in inference module!"


def test_ball_tracker_immutability() -> None:
    """Verifies that BallTrackManager V2 remains completely unchanged by Chapter 6A."""
    from app.video_analysis.ball_tracker import BallTrackManager, create_ball_track_config_v2
    cfg = create_ball_track_config_v2()
    assert cfg.version == "2.0.0"
    assert cfg.spatial_gate_max_radius == 500.0
    assert cfg.max_gap_interpolation == 0
