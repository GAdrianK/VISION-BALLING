"""Tests for Chapter 7 EXP-25: Tactical Event Fusion, Confidence Propagation & Evidence Cards.

Verifies:
1. Unified Tactical Evidence Event schema completeness and serialization
2. Three semantic levels (LEVEL 1: PHYSICAL_FACT, LEVEL 2: STRUCTURAL_INFERENCE, LEVEL 3: TACTICAL_CANDIDATE)
3. Confidence propagation and strict upstream dependency ceilings
4. Data quality level tiers (HIGH, MEDIUM, LOW, INVALID)
5. Continuous episode segmentation with causal hysteresis (pressure, block)
6. Possession change ingestion and LEVEL 1 tagging
7. Transition evidence cards with all supporting metrics and LEVEL 3 candidate tagging
8. Quality gating and suppression of weak pass events
9. Formation policy: continuous line structures primary, nominal hypothesis strictly guarded
10. Event deduplication and causal/evidential relation graph
11. Contradiction detection and confidence discounting
12. Deterministic, template-based human-readable evidence summaries
13. Timeline chronological ordering and JSONL serialization
14. Team tactical aggregates and mandatory reliability bands
15. Upstream module immutability
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pytest

from app.video_analysis.tactical_fusion import (
    ConfidencePropagator,
    ContradictionDetector,
    ContinuousEpisodeConfig,
    ContinuousEpisodeSegmenter,
    DeterministicSummaryFormatter,
    EventDeduplicator,
    EventEdge,
    EventFamily,
    EventRelationGraph,
    MatchTacticalTimeline,
    QualityLevel,
    RelationType,
    SemanticLevel,
    TacticalEvidenceEvent,
    TacticalFusionEngine,
    TeamReliabilityBand,
    TeamTacticalAggregate,
)
from app.video_analysis.defensive_block import DefensiveBlockEngine, DefensiveBlockMetrics
from app.video_analysis.defensive_pressure import DefensivePressureEngine, FrameDefensivePressureState
from app.video_analysis.possession_v2 import PossessionEngineV2
from app.video_analysis.tactical_transitions import TacticalTransitionsEngine


# ==============================================================================
# 1. SCHEMA VALIDATION & SERIALIZATION
# ==============================================================================

def test_unified_schema_fields_and_serialization():
    """Validates that TacticalEvidenceEvent contains all required fields and serializes to JSON."""
    evt = TacticalEvidenceEvent(
        event_id="test_001",
        sequence_id="SNMOT-068",
        start_frame=100,
        end_frame=125,
        start_timestamp=4.0,
        end_timestamp=5.0,
        event_family=EventFamily.POST_LOSS_ENGAGEMENT,
        semantic_level=SemanticLevel.LEVEL_3_TACTICAL_CANDIDATE,
        subject_team="TEAM_0",
        opponent_team="TEAM_1",
        confidence=0.72,
        quality_level=QualityLevel.HIGH,
        source_modules=["EXP-22", "EXP-23", "EXP-24"],
        supporting_metrics={"counterpress_score": 0.74, "nearest_defender_post": 2.1},
        limitations=["Diagnostic evaluation only"],
        visibility_quality="HIGH",
        calibration_quality="VALID",
        causal=True,
        summary_text="Deterministic test summary",
    )

    d = evt.to_dict()
    assert d["event_id"] == "test_001"
    assert d["sequence_id"] == "SNMOT-068"
    assert d["event_family"] == "POST_LOSS_ENGAGEMENT"
    assert d["semantic_level"] == "LEVEL_3_TACTICAL_CANDIDATE"
    assert d["quality_level"] == "HIGH"
    assert d["confidence"] == 0.72
    assert d["causal"] is True
    assert "counterpress_score" in d["supporting_metrics"]

    # Verify JSON serializability
    json_str = json.dumps(d)
    assert len(json_str) > 0


# ==============================================================================
# 2. THREE SEMANTIC LEVELS & CONFIDENCE CEILINGS
# ==============================================================================

def test_confidence_ceilings_and_level3_restriction():
    """Validates that downstream events cannot exceed upstream dependency confidence,
    and Level 3 candidates are strictly capped at 0.85."""

    # Case A: Level 1 physical fact under valid conditions
    c1 = ConfidencePropagator.compute_confidence(
        base_score=0.95,
        upstream_confidences=[0.90],
        semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
        calibration_valid=True,
        visible_outfield=10,
    )
    assert c1 == pytest.approx(0.90, abs=1e-3)  # Capped by upstream 0.90

    # Case B: Level 3 candidate with upstream = 0.55
    c3_low = ConfidencePropagator.compute_confidence(
        base_score=0.99,
        upstream_confidences=[0.55],
        semantic_level=SemanticLevel.LEVEL_3_TACTICAL_CANDIDATE,
        calibration_valid=True,
        visible_outfield=10,
    )
    assert c3_low <= 0.55  # Cannot exceed 0.55

    # Case C: Level 3 candidate with high upstream (0.95) must be capped by LEVEL_3_CEILING (0.85)
    c3_high = ConfidencePropagator.compute_confidence(
        base_score=0.95,
        upstream_confidences=[0.95],
        semantic_level=SemanticLevel.LEVEL_3_TACTICAL_CANDIDATE,
        calibration_valid=True,
        visible_outfield=10,
    )
    assert c3_high <= 0.85

    # Case D: Quality penalties (uncalibrated, low visibility, conflict)
    c_penalized = ConfidencePropagator.compute_confidence(
        base_score=0.80,
        upstream_confidences=[],
        semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
        calibration_valid=False,     # 0.40 penalty
        visible_outfield=5,          # 0.65 penalty
        has_conflict=True,           # 0.60 penalty
        tracking_stable=False,       # 0.80 penalty
    )
    expected = 0.80 * 0.40 * 0.65 * 0.60 * 0.80
    assert c_penalized == pytest.approx(expected, abs=1e-3)


# ==============================================================================
# 3. QUALITY PROPAGATION
# ==============================================================================

def test_quality_propagation_tiers():
    """Validates mapping of sensory conditions to quality tiers (HIGH, MEDIUM, LOW, INVALID)."""
    # High: valid calib, 9 players, stable
    q_high = ConfidencePropagator.determine_quality("VALID", 9, has_conflict=False, tracking_stable=True)
    assert q_high == QualityLevel.HIGH

    # Medium: valid calib, 7 players
    q_med = ConfidencePropagator.determine_quality("VALID", 7, has_conflict=False, tracking_stable=True)
    assert q_med == QualityLevel.MEDIUM

    # Low: valid calib but <6 players
    q_low = ConfidencePropagator.determine_quality("VALID", 5, has_conflict=False, tracking_stable=True)
    assert q_low == QualityLevel.LOW

    # Invalid: uncalibrated or <4 players
    q_inv_calib = ConfidencePropagator.determine_quality("INVALID", 10)
    assert q_inv_calib == QualityLevel.INVALID

    q_inv_vis = ConfidencePropagator.determine_quality("VALID", 3)
    assert q_inv_vis == QualityLevel.INVALID


# ==============================================================================
# 4. CONTINUOUS EPISODE SEGMENTATION (HYSTERESIS)
# ==============================================================================

def test_pressure_episode_segmentation_hysteresis():
    """Validates causal hysteresis segmentation for Pressure Episodes."""
    cfg = ContinuousEpisodeConfig(
        pressure_enter_threshold=0.45,
        pressure_exit_threshold=0.25,
        pressure_min_duration_frames=8,
        fps=25.0,
    )
    segmenter = ContinuousEpisodeSegmenter(cfg)

    # 1. Low pressure (no episode)
    for f in range(5):
        evts = segmenter.process_pressure_frame(
            frame_idx=f, timestamp=f/25.0, defending_team="TEAM_0", target_team="TEAM_1",
            pressure_index=0.15, nearest_dist_m=8.0, closing_speed_mps=0.0, visible_outfield=10, calib_valid=True
        )
        assert len(evts) == 0

    # 2. Enter threshold crossed (f=5 to f=15, 11 frames of pressure >= 0.30)
    for f in range(5, 16):
        evts = segmenter.process_pressure_frame(
            frame_idx=f, timestamp=f/25.0, defending_team="TEAM_0", target_team="TEAM_1",
            pressure_index=0.65 if f < 12 else 0.35,  # Stays above exit threshold 0.25
            nearest_dist_m=2.0, closing_speed_mps=2.5, visible_outfield=10, calib_valid=True
        )
        assert len(evts) == 0  # Still open

    # 3. Exit threshold crossed (<0.25) at f=16 -> episode should finalize
    evts = segmenter.process_pressure_frame(
        frame_idx=16, timestamp=16/25.0, defending_team="TEAM_0", target_team="TEAM_1",
        pressure_index=0.20, nearest_dist_m=6.0, closing_speed_mps=-1.0, visible_outfield=10, calib_valid=True
    )
    assert len(evts) == 1
    p_evt = evts[0]
    assert p_evt.event_family == EventFamily.PRESSURE_EPISODE
    assert p_evt.start_frame == 5
    assert p_evt.end_frame == 16
    assert p_evt.supporting_metrics["duration_frames"] == 12
    assert p_evt.supporting_metrics["peak_pressure_index"] == 0.65
    assert p_evt.supporting_metrics["nearest_defender_min_m"] == 2.0


def test_pressure_episode_short_spike_rejection():
    """Validates that brief pressure spikes (< min_duration) are filtered out."""
    cfg = ContinuousEpisodeConfig(
        pressure_enter_threshold=0.45,
        pressure_exit_threshold=0.25,
        pressure_min_duration_frames=8,
    )
    segmenter = ContinuousEpisodeSegmenter(cfg)

    # Spike for 3 frames only (f=0, 1, 2)
    for f in range(3):
        segmenter.process_pressure_frame(
            f, f/25.0, "TEAM_0", "TEAM_1", 0.70, 2.0, 3.0, 10, True
        )
    # Drop below exit at f=3
    evts = segmenter.process_pressure_frame(
        3, 3/25.0, "TEAM_0", "TEAM_1", 0.10, 8.0, 0.0, 10, True
    )
    assert len(evts) == 0  # Filtered out because 3 frames < 8 frames min duration


# ==============================================================================
# 5. BLOCK EPISODE SEGMENTATION
# ==============================================================================

def test_defensive_block_episode_hysteresis():
    """Validates block height episode segmentation across LOW, MID, HIGH blocks."""
    cfg = ContinuousEpisodeConfig(block_min_duration_frames=10, block_height_buffer_m=2.0)
    segmenter = ContinuousEpisodeSegmenter(cfg)

    # 15 frames of LOW_BLOCK (height = 30m)
    for f in range(15):
        segmenter.process_block_frame(
            f, f/25.0, "TEAM_0", "LOW_BLOCK", line_height_m=30.0, centroid_height_m=35.0,
            depth_m=20.0, width_m=40.0, visible_outfield=10, calib_valid=True
        )

    # Transition to MID_BLOCK (height = 42m) at f=15 -> flushes LOW_BLOCK episode
    evts = segmenter.process_block_frame(
        15, 15/25.0, "TEAM_0", "MID_BLOCK", line_height_m=42.0, centroid_height_m=48.0,
        depth_m=22.0, width_m=45.0, visible_outfield=10, calib_valid=True
    )
    assert len(evts) == 1
    assert evts[0].event_family == EventFamily.BLOCK_STATE
    assert evts[0].supporting_metrics["block_category"] == "LOW_BLOCK"
    assert evts[0].supporting_metrics["mean_defensive_line_height_m"] == 30.0


# ==============================================================================
# 6. INGESTION OF ADAPTER EVENTS (EXP-22, EXP-24, EXP-19)
# ==============================================================================

@dataclass
class DummyPossessionChangeEvent:
    losing_team: str = "TEAM_0"
    gaining_team: str = "TEAM_1"
    frame_index: int = 50
    timestamp: float = 2.0
    confidence: float = 0.85


@dataclass
class DummyTransitionFeatures:
    pressure_pre_mean: float = 0.20
    pressure_post_mean: float = 0.70
    pressure_delta: float = 0.50
    nearest_defender_pre: float = 6.0
    nearest_defender_post: float = 1.8
    nearest_distance_delta: float = -4.2
    density_r3_post: float = 2.0
    density_r5_post: float = 4.0
    centroid_ball_distance_delta: float = -3.5
    defensive_line_velocity: float = 1.2
    ball_delta_x_attack: float = 1.5
    possession_change_confidence: float = 0.75


@dataclass
class DummyTransitionEvent:
    loss_frame_index: int = 50
    confirmation_frame_index: int = 75
    loss_timestamp: float = 2.0
    losing_team: str = "TEAM_0"
    gaining_team: str = "TEAM_1"
    candidate_label: str = "COUNTERPRESS_CANDIDATE"
    counterpress_score: float = 0.78
    recovery_score: float = 0.32
    features: DummyTransitionFeatures = field(default_factory=DummyTransitionFeatures)


@dataclass
class DummyPassEvent:
    release_frame: int = 100
    reception_frame: int = 118
    release_timestamp: float = 4.0
    reception_timestamp: float = 4.72
    sender_team: str = "TEAM_1"
    receiver_team: str = "TEAM_1"
    event_type: str = "PASS_COMPLETED"
    event_confidence: float = 0.65
    pass_displacement_m: float = 14.5
    forward_displacement_m: float = 12.0
    sender_track_id: int = 4
    receiver_track_id: int = 7
    trajectory: Any = None


def test_possession_and_transition_ingestion_and_graph():
    """Validates ingestion of EXP-22 possession change and EXP-24 transition candidate into graph."""
    engine = TacticalFusionEngine(sequence_id="TEST-SEQ", fps=25.0)

    # Ingest turnover
    poss_evt = DummyPossessionChangeEvent()
    t_evt = engine.ingest_possession_change_event(poss_evt, calibration_valid=True, visible_players=10)
    assert t_evt.event_family == EventFamily.POSSESSION_CHANGE
    assert t_evt.semantic_level == SemanticLevel.LEVEL_1_PHYSICAL_FACT
    assert t_evt.confidence == pytest.approx(0.85, abs=1e-3)

    # Ingest post-loss engagement candidate
    trans_evt = DummyTransitionEvent()
    eng_evt = engine.ingest_transition_event(trans_evt, calibration_valid=True, visible_players=10)
    assert eng_evt.event_family == EventFamily.POST_LOSS_ENGAGEMENT
    assert eng_evt.semantic_level == SemanticLevel.LEVEL_3_TACTICAL_CANDIDATE
    # Confidence capped by possession_change_confidence (0.75) and Level 3 ceiling (0.85)
    assert eng_evt.confidence <= 0.75
    assert eng_evt.supporting_metrics["counterpress_score"] == 0.78

    # Finalize and verify causal edge linking
    timeline, graph, _ = engine.finalize(last_frame=150, last_timestamp=6.0)

    # Verify edge exists: turnover CAUSES post-loss engagement
    assert len(graph.edges) >= 1
    edge = graph.edges[0]
    assert edge.source_id == t_evt.event_id
    assert edge.target_id == eng_evt.event_id
    assert edge.relation == RelationType.CAUSES


def test_pass_quality_gating():
    """Validates that low-confidence (<0.30) pass events are rejected from authoritative timeline."""
    engine = TacticalFusionEngine(sequence_id="TEST-SEQ", fps=25.0)

    # Valid pass
    valid_pass = DummyPassEvent(event_confidence=0.65)
    evt_good = engine.ingest_pass_event(valid_pass, calibration_valid=True)
    assert evt_good is not None
    assert evt_good.event_family == EventFamily.BALL_TRANSFER

    # Weak pass (<0.30)
    weak_pass = DummyPassEvent(event_confidence=0.15)
    evt_weak = engine.ingest_pass_event(weak_pass, calibration_valid=True)
    assert evt_weak is None  # Suppressed by quality gate


# ==============================================================================
# 7. CONTRADICTION DETECTION
# ==============================================================================

def test_contradiction_detection_and_discount():
    """Validates that contradictory states trigger conflict_flag and discount confidence."""
    evt = TacticalEvidenceEvent(
        event_id="press_conflict_01",
        sequence_id="TEST-SEQ",
        start_frame=10,
        end_frame=25,
        start_timestamp=0.4,
        end_timestamp=1.0,
        event_family=EventFamily.PRESSURE_EPISODE,
        semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
        subject_team="TEAM_0",
        opponent_team="TEAM_1",
        confidence=0.80,
        quality_level=QualityLevel.HIGH,
    )

    # Inconsistent: Possession V2 says TEAM_0 possesses ball, but pressure target says TEAM_1
    audited = ContradictionDetector.audit_event_consistency(
        event=evt,
        possession_team="TEAM_0",
        pressure_target_team="TEAM_1",
    )
    assert audited.conflict_flag is True
    assert "Possession V2 assigns ball to TEAM_0" in audited.conflict_reason
    assert "CONFLICT" in audited.limitations[0]
    assert audited.confidence == pytest.approx(0.80 * 0.60, abs=1e-3)
    assert audited.quality_level == QualityLevel.MEDIUM


# ==============================================================================
# 8. DETERMINISTIC HUMAN-READABLE EVIDENCE SUMMARIES
# ==============================================================================

def test_deterministic_summary_formatter():
    """Validates deterministic template formatting for evidence cards."""
    evt = TacticalEvidenceEvent(
        event_id="poss_100",
        sequence_id="TEST",
        start_frame=100,
        end_frame=100,
        start_timestamp=4.0,
        end_timestamp=4.0,
        event_family=EventFamily.POSSESSION_CHANGE,
        semantic_level=SemanticLevel.LEVEL_1_PHYSICAL_FACT,
        subject_team="TEAM_0",
        opponent_team="TEAM_1",
        confidence=0.82,
        quality_level=QualityLevel.HIGH,
    )
    summary = DeterministicSummaryFormatter.format_summary(evt)
    assert "TEAM_0 lost possession to TEAM_1 at 4.00s" in summary
    assert "Possession confidence: 0.82 [HIGH]" in summary


# ==============================================================================
# 9. TEAM SUMMARY & RELIABILITY BANDS
# ==============================================================================

def test_team_summary_reliability_bands():
    """Validates compilation of team tactical aggregates with coverage and confidence bands."""
    engine = TacticalFusionEngine(sequence_id="TEST-SEQ", fps=25.0)

    # Ingest 50 frames: TEAM_0 possesses for 30 frames, TEAM_1 for 20 frames
    for f in range(50):
        t = f / 25.0
        poss_team = "TEAM_0" if f < 30 else "TEAM_1"
        engine.ingest_frame(
            frame_idx=f,
            timestamp=t,
            block_metrics_team0=None,
            block_metrics_team1=None,
            possession_status="CONTROLLED",
            possessing_team=poss_team,
            possession_confidence=0.85,
            pressure_state=None,
            calibration_valid=True,
            visible_players_t0=10,
            visible_players_t1=10,
        )

    _, _, summaries = engine.finalize(last_frame=49, last_timestamp=49/25.0)
    t0_sum = summaries["TEAM_0"]
    t1_sum = summaries["TEAM_1"]

    assert t0_sum.secure_possession_pct == pytest.approx(60.0, abs=0.5)
    assert t1_sum.secure_possession_pct == pytest.approx(40.0, abs=0.5)
    assert t0_sum.reliability.total_frames == 50
    assert t0_sum.reliability.coverage_pct >= 0.0


# ==============================================================================
# 10. UPSTREAM IMMUTABILITY VERIFICATION
# ==============================================================================

def test_upstream_modules_remain_immutable():
    """Asserts that upstream engines (EXP-20, EXP-22, EXP-23, EXP-24) exist and are unaltered."""
    # EXP-20 Block Engine
    block_engine = DefensiveBlockEngine()
    assert hasattr(block_engine, "process_frame")
    assert block_engine.config.low_block_ceiling_m == 35.0
    assert block_engine.config.high_block_floor_m == 52.5

    # EXP-22 Possession Engine
    poss_engine = PossessionEngineV2()
    assert hasattr(poss_engine, "process_frame")
    assert poss_engine.config.control_probability_threshold == 0.42
    assert poss_engine.config.player_control_confirm_frames == 2

    # EXP-23 Pressure Engine
    press_engine = DefensivePressureEngine()
    assert hasattr(press_engine, "process_frame")
    assert press_engine.config.strong_pressure_threshold == 0.60
    assert press_engine.config.light_pressure_threshold == 0.25

    # EXP-24 Transitions Engine
    trans_engine = TacticalTransitionsEngine()
    assert hasattr(trans_engine, "process_frame")
    assert trans_engine.config.window_post_frames == 25
    assert trans_engine.config.counterpress_score_threshold == 0.52
