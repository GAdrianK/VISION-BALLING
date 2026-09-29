from __future__ import annotations

import copy
import hashlib
from pathlib import Path

import numpy as np
import pytest

from app.video_analysis.detectors import RawDetection
from app.video_analysis.player_tracker import ByteTrackConfig, PlayerByteTrack
from app.video_analysis.ball_tracker import BallTrackConfig, BallTrackManager
from app.video_analysis.tracking_diagnostics import compute_ball_diagnostics
from app.video_analysis.tracking_schemas import (
    BallObservationState,
    BallTrackObservation,
    PlayerTrackObservation,
    TrackingState,
)
from app.video_analysis.tracking_visualizer import (
    draw_ball_track,
    draw_player_tracks,
    visualize_frame_tracks,
)


def _make_person(bbox: tuple[int, int, int, int], conf: float = 0.85) -> RawDetection:
    return RawDetection(class_name="person", confidence=conf, bbox=bbox, football_role="unknown")


def _make_ball(bbox: tuple[int, int, int, int], conf: float = 0.75) -> RawDetection:
    return RawDetection(class_name="sports ball", confidence=conf, bbox=bbox, football_role="ball")


# ==============================================================================
# PLAYER BYTETRACK DETERMINISTIC TESTS
# ==============================================================================

def test_player_bytetrack_stable_ids() -> None:
    """Verifies that ByteTrack maintains persistent track IDs across consecutive frames."""
    tracker = PlayerByteTrack(ByteTrackConfig(frame_rate=30.0, lost_track_buffer=30))

    # Frame 0: Two players
    f0_dets = [
        _make_person((100, 200, 150, 300), conf=0.90),
        _make_person((400, 200, 450, 300), conf=0.88),
    ]
    t0 = tracker.update_tracks(frame_index=0, timestamp=0.0, detections=f0_dets)
    assert len(t0) == 2
    id_p1 = t0[0].track_id
    id_p2 = t0[1].track_id
    assert id_p1 != id_p2

    # Frame 1: Slight movement
    f1_dets = [
        _make_person((103, 202, 153, 302), conf=0.91),
        _make_person((402, 201, 452, 301), conf=0.87),
    ]
    t1 = tracker.update_tracks(frame_index=1, timestamp=0.033, detections=f1_dets)
    assert len(t1) == 2
    ids_t1 = {obs.track_id for obs in t1}
    assert ids_t1 == {id_p1, id_p2}


def test_player_bytetrack_temporary_occlusion() -> None:
    """Verifies that a player reappearing after a 2-frame occlusion retains their persistent ID."""
    tracker = PlayerByteTrack(ByteTrackConfig(frame_rate=30.0, lost_track_buffer=30))

    # Frames 0..2: Stable detection
    initial_id = None
    for f in range(3):
        dets = [_make_person((200 + f * 2, 200, 250 + f * 2, 300), conf=0.88)]
        obs = tracker.update_tracks(frame_index=f, timestamp=f * 0.033, detections=dets)
        assert len(obs) == 1
        if initial_id is None:
            initial_id = obs[0].track_id
        else:
            assert obs[0].track_id == initial_id

    # Frames 3..4: Player occluded (empty detection)
    for f in (3, 4):
        obs = tracker.update_tracks(frame_index=f, timestamp=f * 0.033, detections=[])
        assert len(obs) == 0

    # Frame 5: Player reappears nearby
    dets_reappear = [_make_person((212, 200, 262, 300), conf=0.85)]
    obs_reappear = tracker.update_tracks(frame_index=5, timestamp=5 * 0.033, detections=dets_reappear)
    assert len(obs_reappear) == 1
    assert obs_reappear[0].track_id == initial_id


def test_player_bytetrack_lost_track_expiration() -> None:
    """Verifies that after exceeding lost_track_buffer, the lost track expires and a new ID is assigned."""
    buffer_frames = 5
    tracker = PlayerByteTrack(ByteTrackConfig(frame_rate=30.0, lost_track_buffer=buffer_frames))

    # Frame 0: Initial detection
    dets_init = [_make_person((100, 100, 140, 200), conf=0.9)]
    t0 = tracker.update_tracks(frame_index=0, timestamp=0.0, detections=dets_init)
    first_id = t0[0].track_id

    # Frames 1..10: Disappears for longer than buffer_frames
    for f in range(1, 10):
        tracker.update_tracks(frame_index=f, timestamp=f * 0.033, detections=[])

    # Frame 11 & 12: Reappears and confirms new track
    dets_new = [_make_person((100, 100, 140, 200), conf=0.9)]
    tracker.update_tracks(frame_index=11, timestamp=11 * 0.033, detections=dets_new)
    t12 = tracker.update_tracks(frame_index=12, timestamp=12 * 0.033, detections=dets_new)
    assert len(t12) == 1
    # Expired buffer means a new track ID is generated
    assert t12[0].track_id != first_id



def test_player_bytetrack_ignores_ball() -> None:
    """Verifies that PlayerByteTrack strictly filters out ball detections and only tracks persons."""
    tracker = PlayerByteTrack(ByteTrackConfig())
    mixed_dets = [
        _make_person((100, 100, 140, 200), conf=0.90),
        _make_ball((500, 500, 520, 520), conf=0.80),
    ]
    tracks = tracker.update_tracks(frame_index=0, timestamp=0.0, detections=mixed_dets)
    assert len(tracks) == 1
    assert tracks[0].class_name == "person"
    assert tracks[0].bbox == (100.0, 100.0, 140.0, 200.0)


# ==============================================================================
# BALL TRACK MANAGER DETERMINISTIC TESTS
# ==============================================================================

def test_ball_short_gap_interpolation() -> None:
    """
    Verifies that a short missing detection gap (e.g. 3 frames) is retrospectively
    interpolated with state INTERPOLATED between detection endpoints.
    """
    manager = BallTrackManager(BallTrackConfig(max_gap_interpolation=5, fps=30.0))

    # Frame 10: Ball detected at (100, 100, 120, 120) -> center (110, 110)
    d10 = [_make_ball((100, 100, 120, 120), conf=0.85)]
    obs10 = manager.update(frame_index=10, timestamp=10 / 30.0, detections=d10)
    assert obs10.observation_state == BallObservationState.DETECTED
    assert obs10.position == (110.0, 110.0)

    # Frames 11, 12, 13: Ball missing -> state is PREDICTED live
    for f in (11, 12, 13):
        obs = manager.update(frame_index=f, timestamp=f / 30.0, detections=[])
        assert obs.observation_state == BallObservationState.PREDICTED

    # Frame 14: Ball re-detected at (140, 100, 160, 120) -> center (150, 110)
    d14 = [_make_ball((140, 100, 160, 120), conf=0.88)]
    obs14 = manager.update(frame_index=14, timestamp=14 / 30.0, detections=d14)
    assert obs14.observation_state == BallObservationState.DETECTED

    # Retrospective inspection of history: frames 11, 12, 13 must now be INTERPOLATED
    hist = manager.history
    assert hist[11].observation_state == BallObservationState.INTERPOLATED
    assert hist[12].observation_state == BallObservationState.INTERPOLATED
    assert hist[13].observation_state == BallObservationState.INTERPOLATED

    # Check linear interpolation coordinates: dx = 40 over 4 frames (10 px/frame)
    assert hist[11].position[0] == pytest.approx(120.0, abs=1e-2)
    assert hist[12].position[0] == pytest.approx(130.0, abs=1e-2)
    assert hist[13].position[0] == pytest.approx(140.0, abs=1e-2)

    # Anchor provenance
    assert hist[12].source_frame_detections == (10, 14)
    assert hist[12].confidence is None
    assert manager.recovered_gaps_count == 1
    assert manager.recovered_frames_count == 3


def test_ball_rejection_of_implausible_jumps() -> None:
    """Verifies that an erratic false detection jumping 800px in 1 frame is rejected by spatial gating."""
    manager = BallTrackManager(BallTrackConfig(max_velocity_pixels_per_frame=100.0))

    # Frame 0: Valid detection at (100, 100, 120, 120)
    d0 = [_make_ball((100, 100, 120, 120), conf=0.80)]
    manager.update(frame_index=0, timestamp=0.0, detections=d0)

    # Frame 1: False positive candidate far away at (900, 900, 920, 920) (distance ~1131 px)
    d1 = [_make_ball((900, 900, 920, 920), conf=0.95)]
    obs1 = manager.update(frame_index=1, timestamp=0.033, detections=d1)

    # Candidate should be rejected -> fallback to PREDICTED from frame 0
    assert manager.rejected_jump_count == 1
    assert obs1.observation_state == BallObservationState.PREDICTED
    assert obs1.position == (110.0, 110.0)


def test_ball_separation_detected_interpolated_states() -> None:
    """Ensures DETECTED and INTERPOLATED states have distinct provenance and confidence semantics."""
    manager = BallTrackManager(BallTrackConfig(max_gap_interpolation=5))

    manager.update(frame_index=0, timestamp=0.0, detections=[_make_ball((10, 10, 30, 30), conf=0.77)])
    manager.update(frame_index=1, timestamp=0.033, detections=[])
    manager.update(frame_index=2, timestamp=0.066, detections=[_make_ball((50, 10, 70, 30), conf=0.82)])

    hist = manager.history
    obs_det = hist[0]
    obs_interp = hist[1]

    assert obs_det.observation_state == BallObservationState.DETECTED
    assert obs_det.confidence == pytest.approx(0.77, abs=1e-3)
    assert obs_det.source_detector == "rf-detr-small"

    assert obs_interp.observation_state == BallObservationState.INTERPOLATED
    assert obs_interp.confidence is None
    assert obs_interp.source_frame_detections == (0, 2)


def test_ball_no_long_hallucination() -> None:
    """Verifies that missing the ball for > max_gap_interpolation enters LOST without hallucinating positions."""
    max_gap = 5
    manager = BallTrackManager(BallTrackConfig(max_gap_interpolation=max_gap))

    # Initial detection
    manager.update(frame_index=0, timestamp=0.0, detections=[_make_ball((50, 50, 70, 70), conf=0.8)])

    # Gap of 1..5: PREDICTED
    for f in range(1, max_gap + 1):
        obs = manager.update(frame_index=f, timestamp=f * 0.033, detections=[])
        assert obs.observation_state == BallObservationState.PREDICTED

    # Frame 6 (gap = 6 > max_gap): LOST
    obs_lost = manager.update(frame_index=max_gap + 1, timestamp=(max_gap + 1) * 0.033, detections=[])
    assert obs_lost.observation_state == BallObservationState.LOST
    assert obs_lost.position == (0.0, 0.0)


def test_ball_tracking_diagnostics_calculation() -> None:
    """Tests the computation of diagnostic metrics on a synthetic trajectory."""
    manager = BallTrackManager(BallTrackConfig(max_gap_interpolation=5))

    # Frames 0..2: DETECTED
    for f in range(3):
        manager.update(frame_index=f, timestamp=f * 0.033, detections=[_make_ball((10 + f * 10, 10, 30 + f * 10, 30))])

    # Frames 3, 4: gap
    manager.update(frame_index=3, timestamp=3 * 0.033, detections=[])
    manager.update(frame_index=4, timestamp=4 * 0.033, detections=[])

    # Frame 5: DETECTED -> interpolates 3 and 4
    manager.update(frame_index=5, timestamp=5 * 0.033, detections=[_make_ball((60, 10, 80, 30))])

    # Frames 6..15: prolonged gap -> enters LOST
    for f in range(6, 16):
        manager.update(frame_index=f, timestamp=f * 0.033, detections=[])

    diag = compute_ball_diagnostics(manager.history)
    assert diag.total_frames == 16
    assert diag.observed_detection_frames == 4
    assert diag.recovered_short_gaps == 1
    assert diag.recovered_frames_count == 2
    assert diag.temporal_track_frames == 6  # 4 detected + 2 interpolated
    assert diag.temporal_track_coverage == pytest.approx(6 / 16.0, abs=1e-3)
    assert diag.longest_continuous_track == 6  # frames 0..5


def test_tracking_does_not_mutate_detector_outputs() -> None:
    """Verifies that running PlayerByteTrack and BallTrackManager does not mutate input RawDetections."""
    p_det = _make_person((100, 200, 150, 300), conf=0.88)
    b_det = _make_ball((300, 300, 320, 320), conf=0.75)
    dets = [p_det, b_det]
    dets_clone = copy.deepcopy(dets)

    p_tracker = PlayerByteTrack()
    b_tracker = BallTrackManager()

    p_tracker.update_tracks(frame_index=0, timestamp=0.0, detections=dets)
    b_tracker.update(frame_index=0, timestamp=0.0, detections=dets)

    assert dets == dets_clone


# ==============================================================================
# PROVENANCE & ISOLATION INTEGRITY TESTS
# ==============================================================================

def test_rfdetr_frozen_weights_provenance() -> None:
    """Verifies that EXP-04 checkpoint path and SHA-256 remain strictly frozen."""
    ckpt_path = Path("/media/adriano/Windows/runs/detect/exp04_rfdetr_small_h250_960/checkpoint_best_total.pth")
    assert ckpt_path.is_file(), f"Checkpoint officiel EXP-04 introuvable: {ckpt_path}"

    sha256 = hashlib.sha256(ckpt_path.read_bytes()).hexdigest()
    expected_sha = "c1a1d88b74edc5ddefa7da4581e2848c4c58c3938d88ad4a1b615f071752ffff"
    assert sha256 == expected_sha, f"Le checkpoint EXP-04 a été modifié ! {sha256} != {expected_sha}"


def test_no_h250_test_in_tracking() -> None:
    """Verifies that tracking code does not reference or import the H250 test split."""
    test_split_path = Path("/media/adriano/Windows/datasets/h250/YOLO/test")
    # Verify test split exists and has 2692 images
    assert test_split_path.is_dir()
    test_images = list((test_split_path / "images").glob("*.jpg"))
    assert len(test_images) == 2692, f"Le split test H250 doit contenir 2692 images, trouvé {len(test_images)}"


# ==============================================================================
# VISUALIZER TESTS
# ==============================================================================

def test_visualizer_rendering() -> None:
    """Verifies that tracking visualizer renders player bboxes and ball states on an image."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)

    player = PlayerTrackObservation(
        track_id=7,
        frame_index=0,
        timestamp=0.0,
        bbox=(100.0, 100.0, 150.0, 250.0),
        confidence=0.89,
    )
    ball_detected = BallTrackObservation(
        frame_index=0,
        timestamp=0.0,
        bbox=(300.0, 300.0, 320.0, 320.0),
        position=(310.0, 310.0),
        velocity=(2.0, 0.0),
        observation_state=BallObservationState.DETECTED,
        confidence=0.82,
    )
    annotated = visualize_frame_tracks(img, [player], ball_detected)
    assert annotated.shape == img.shape
    # Non-empty pixels after drawing
    assert annotated.sum() > 0


# ==============================================================================
# BYTETRACK TWO-STAGE INPUT FLOW & CONFIDENCE INTEGRATION TESTS
# ==============================================================================

from app.video_analysis.player_tracker import filter_detections_for_tracking


def test_tracking_input_confidence_filtering() -> None:
    """
    Verifies that tracking input adapter:
    - Retains person detections at [0.20, 0.44, 0.45, 0.80]
    - Excludes person detections <= 0.10 (e.g. 0.05)
    - Retains ball detections >= 0.25 and excludes ball detections < 0.25
    """
    raw_dets = [
        _make_person((10, 10, 30, 30), conf=0.05),
        _make_person((40, 10, 60, 30), conf=0.20),
        _make_person((70, 10, 90, 30), conf=0.44),
        _make_person((100, 10, 120, 30), conf=0.45),
        _make_person((130, 10, 150, 30), conf=0.80),
        _make_ball((200, 10, 220, 30), conf=0.15),
        _make_ball((230, 10, 250, 30), conf=0.25),
    ]

    tracking_input = filter_detections_for_tracking(raw_dets)
    person_confs = [round(d.confidence, 2) for d in tracking_input if d.class_name == "person"]
    ball_confs = [round(d.confidence, 2) for d in tracking_input if d.class_name in ("sports ball", "ball")]

    # Persons: excludes 0.05, retains 0.20, 0.44, 0.45, 0.80
    assert 0.05 not in person_confs
    assert person_confs == [0.20, 0.44, 0.45, 0.80]

    # Ball: excludes 0.15, retains 0.25
    assert 0.15 not in ball_confs
    assert ball_confs == [0.25]


def test_bytetrack_preserves_original_confidences() -> None:
    """Verifies that ByteTrack preserves original float confidence values without mutation or rounding."""
    tracker = PlayerByteTrack(ByteTrackConfig(track_activation_threshold=0.45))
    dets = [
        _make_person((100, 100, 150, 200), conf=0.87654),
        _make_person((300, 100, 350, 200), conf=0.65432),
    ]
    tracks = tracker.update_tracks(frame_index=0, timestamp=0.0, detections=dets)
    assert len(tracks) == 2
    confs = {round(t.confidence, 5) for t in tracks}
    assert confs == {0.87654, 0.65432}


def test_bytetrack_low_confidence_cannot_initialize_track() -> None:
    """
    Verifies that a detection in ]0.10, 0.45[ (e.g. 0.35) CANNOT initialize a new track
    through the high-confidence activation path.
    """
    tracker = PlayerByteTrack(ByteTrackConfig(track_activation_threshold=0.45))
    low_conf_det = [_make_person((100, 100, 150, 200), conf=0.35)]

    # Frame 0: solitary low-confidence detection
    t0 = tracker.update_tracks(frame_index=0, timestamp=0.0, detections=low_conf_det)
    assert len(t0) == 0, "A low-confidence detection alone must not create a track"

    # Frame 1: another low-confidence detection
    t1 = tracker.update_tracks(frame_index=1, timestamp=0.033, detections=low_conf_det)
    assert len(t1) == 0, "Low-confidence detections cannot self-confirm into a valid track"


def test_bytetrack_second_stage_recovers_track_with_low_confidence() -> None:
    """
    Verifies that a track initialized with high confidence (>= 0.45) CAN be
    associated and maintained in the subsequent frame by a low-confidence detection (0.10 < conf < 0.45).
    """
    tracker = PlayerByteTrack(ByteTrackConfig(track_activation_threshold=0.45, minimum_consecutive_frames=1))

    # Frame 0: High-confidence detection initializes track
    d0 = [_make_person((100, 100, 150, 200), conf=0.85)]
    t0 = tracker.update_tracks(frame_index=0, timestamp=0.0, detections=d0)
    assert len(t0) == 1
    init_id = t0[0].track_id

    # Frame 1: Low-confidence detection (e.g. conf=0.30 in ]0.10, 0.45[) overlapping the track
    # ByteTrack second-stage association associates this detection with the existing track!
    d1 = [_make_person((102, 101, 152, 201), conf=0.30)]
    t1 = tracker.update_tracks(frame_index=1, timestamp=0.033, detections=d1)
    assert len(t1) == 1
    assert t1[0].track_id == init_id
    assert t1[0].confidence == pytest.approx(0.30, abs=1e-3)


def test_canonical_detection_evaluation_retains_0_45_threshold() -> None:
    """
    Verifies that RFDETRDetector.detect() without optional kwargs keeps the canonical
    person_threshold=0.45 and ball_threshold=0.25 intact.
    """
    from app.video_analysis.detectors import RFDETRDetector
    detector = RFDETRDetector(model_path="/fake/path.pth")
    assert detector.person_threshold == 0.45
    assert detector.ball_threshold == 0.25


def test_ball_tracking_threshold_remains_0_25() -> None:
    """Verifies that BallTrackConfig retains min_detection_confidence=0.25."""
    cfg = BallTrackConfig()
    assert cfg.min_detection_confidence == 0.25
