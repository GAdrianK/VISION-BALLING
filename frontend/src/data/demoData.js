// Precomputed ground truth match evidence for DEMO sequences (EXP-25 & EXP-26)
// Generated from authoritative sealed benchmarks

export const DEMO_SEQUENCES = {
  'SNMOT-068': {
    id: 'SNMOT-068',
    title: 'SNMOT-068 (Référence Consolidée)',
    subtitle: 'Séquence SoccerNet Tracking 2023 train split',
    durationSeconds: 14.0,
    fps: 25.0,
    framesAnalyzed: 350,
    mode: 'QUALITY',
    throughputFps: 11.4,
    strict25Fps: false,
    videoUrl: "/demo_videos/SNMOT-068.mp4",
    posterUrl: "/demo_videos/SNMOT-068_poster.jpg",
    summary: {
    "TEAM_0": {
        "team_id": "TEAM_0",
        "reliability": {
            "coverage_pct": 100.0,
            "valid_frames": 350,
            "total_frames": 350,
            "confidence_mean": 0.542,
            "confidence_p10": 0.443,
            "quality_distribution": {
                "MEDIUM": 53,
                "LOW": 100,
                "INVALID": 2,
                "HIGH": 195
            }
        },
        "secure_possession_duration_s": 2.6,
        "secure_possession_pct": 18.6,
        "possession_change_count": 3,
        "mean_defensive_line_height_m": 65.7,
        "mean_team_depth_m": 24.72,
        "mean_team_width_m": 19.63,
        "mean_hull_area_m2": 219.87,
        "mean_pressure_index": 0.264,
        "peak_pressure_index": 0.775,
        "high_quality_pressure_episode_count": 3,
        "post_loss_counterpress_mean": 0.529,
        "defensive_recovery_mean": 0.194,
        "net_forward_progression_m": 0.0,
        "completed_pass_count": 0,
        "observed_line_structures": [],
        "formation_hypothesis": null
    },
    "TEAM_1": {
        "team_id": "TEAM_1",
        "reliability": {
            "coverage_pct": 100.0,
            "valid_frames": 350,
            "total_frames": 350,
            "confidence_mean": 0.552,
            "confidence_p10": 0.443,
            "quality_distribution": {
                "HIGH": 303,
                "MEDIUM": 47
            }
        },
        "secure_possession_duration_s": 6.12,
        "secure_possession_pct": 43.7,
        "possession_change_count": 1,
        "mean_defensive_line_height_m": 22.55,
        "mean_team_depth_m": 22.71,
        "mean_team_width_m": 15.39,
        "mean_hull_area_m2": 135.93,
        "mean_pressure_index": 0.461,
        "peak_pressure_index": 1.0,
        "high_quality_pressure_episode_count": 3,
        "post_loss_counterpress_mean": 0.0,
        "defensive_recovery_mean": 0.0,
        "net_forward_progression_m": 0.0,
        "completed_pass_count": 0,
        "observed_line_structures": [],
        "formation_hypothesis": null
    }
},
    events: [
    {
        "event_id": "pass_53_55_TEAM_0_PASS_INTERCEPTED",
        "sequence_id": "SNMOT-068",
        "start_frame": 53,
        "end_frame": 55,
        "start_timestamp": 2.08,
        "end_timestamp": 2.16,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.8624999999999999,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_INTERCEPTED",
            "pass_distance_m": 1.61,
            "forward_displacement_m": 0.0,
            "sender_track_id": 1,
            "receiver_track_id": 13
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 ball transfer completed (2.08\u20132.16s). Distance: 1.6m, forward displacement: +0.0m [Confidence: 0.86].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_53_243_TEAM_1",
        "sequence_id": "SNMOT-068",
        "start_frame": 53,
        "end_frame": 243,
        "start_timestamp": 2.08,
        "end_timestamp": 9.68,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.4427742365028949,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.443,
            "peak_pressure_index": 0.761,
            "duration_frames": 191,
            "nearest_defender_min_m": 0.52,
            "max_closing_speed_mps": 3.65
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08\u20139.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m.",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "poss_change_55_TEAM_0_to_TEAM_1",
        "sequence_id": "SNMOT-068",
        "start_frame": 55,
        "end_frame": 55,
        "start_timestamp": 2.16,
        "end_timestamp": 2.16,
        "event_family": "POSSESSION_CHANGE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.3872824251651764,
        "quality_level": "LOW",
        "source_modules": [
            "EXP-22 possession_v2"
        ],
        "supporting_metrics": {
            "turnover_frame": 55,
            "losing_team": "TEAM_0",
            "gaining_team": "TEAM_1",
            "upstream_confidence": 0.5958191156387329
        },
        "limitations": [],
        "visibility_quality": "LOW",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 lost possession to TEAM_1 at 2.16s (frame 55). Possession confidence: 0.39 [LOW].",
        "related_event_ids": [
            "trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE",
        "sequence_id": "SNMOT-068",
        "start_frame": 55,
        "end_frame": 80,
        "start_timestamp": 2.16,
        "end_timestamp": 3.2,
        "event_family": "POST_LOSS_ENGAGEMENT",
        "semantic_level": "LEVEL_3_TACTICAL_CANDIDATE",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.5958191156387329,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2",
            "EXP-23 defensive_pressure",
            "EXP-24 tactical_transitions"
        ],
        "supporting_metrics": {
            "counterpress_score": 0.603,
            "recovery_score": 0.202,
            "candidate_label": "COUNTERPRESS_CANDIDATE",
            "pressure_pre_mean": 0.081,
            "pressure_post_mean": 0.262,
            "pressure_delta": 0.181,
            "nearest_defender_pre": 1.93,
            "nearest_defender_post": 4.02,
            "nearest_distance_delta": 2.09,
            "density_r3_post": 0.23,
            "density_r5_post": 0.65,
            "centroid_ball_distance_delta": -7.16,
            "defensive_line_velocity": 4.01,
            "ball_delta_x_attack": 0.0
        },
        "limitations": [
            "Diagnostic candidate semantics; physics-derived GT evaluation"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 engaged in post-loss pressing against TEAM_1 (2.16\u20133.20s, \u0394t=1.04s). Nearest defender closed from 1.9m to 4.0m; PressureIndex changed from 0.08 to 0.26. CounterpressScore: 0.60 [Confidence: 0.60].",
        "related_event_ids": [
            "poss_change_55_TEAM_0_to_TEAM_1"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_196_207_TEAM_0",
        "sequence_id": "SNMOT-068",
        "start_frame": 196,
        "end_frame": 207,
        "start_timestamp": 7.8,
        "end_timestamp": 8.24,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.3728692740395123,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.373,
            "peak_pressure_index": 0.544,
            "duration_frames": 12,
            "nearest_defender_min_m": 1.68,
            "max_closing_speed_mps": 1.77
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 applied continuous defensive pressure on TEAM_1 (7.80\u20138.24s, dur: 0.44s). Mean PressureIndex: 0.37 (peak: 0.54), min defender proximity: 1.7m.",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_248_287_TEAM_1",
        "sequence_id": "SNMOT-068",
        "start_frame": 248,
        "end_frame": 287,
        "start_timestamp": 9.88,
        "end_timestamp": 11.44,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.4556707932638774,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.456,
            "peak_pressure_index": 0.662,
            "duration_frames": 40,
            "nearest_defender_min_m": 1.4,
            "max_closing_speed_mps": 3.41
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 applied continuous defensive pressure on TEAM_0 (9.88\u201311.44s, dur: 1.56s). Mean PressureIndex: 0.46 (peak: 0.66), min defender proximity: 1.4m.",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "poss_change_256_TEAM_0_to_TEAM_1",
        "sequence_id": "SNMOT-068",
        "start_frame": 256,
        "end_frame": 256,
        "start_timestamp": 10.2,
        "end_timestamp": 10.2,
        "event_family": "POSSESSION_CHANGE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.4769885540008545,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2"
        ],
        "supporting_metrics": {
            "turnover_frame": 256,
            "losing_team": "TEAM_0",
            "gaining_team": "TEAM_1",
            "upstream_confidence": 0.4769885540008545
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 lost possession to TEAM_1 at 10.20s (frame 256). Possession confidence: 0.48 [HIGH].",
        "related_event_ids": [
            "trans_256_281_TEAM_0_NEUTRAL_TRANSITION"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_256_270_TEAM_0",
        "sequence_id": "SNMOT-068",
        "start_frame": 256,
        "end_frame": 270,
        "start_timestamp": 10.2,
        "end_timestamp": 10.76,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.4539799174762027,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.454,
            "peak_pressure_index": 0.643,
            "duration_frames": 15,
            "nearest_defender_min_m": 1.36,
            "max_closing_speed_mps": 2.04
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 applied continuous defensive pressure on TEAM_1 (10.20\u201310.76s, dur: 0.56s). Mean PressureIndex: 0.45 (peak: 0.64), min defender proximity: 1.4m.",
        "related_event_ids": [
            "trans_256_281_TEAM_0_NEUTRAL_TRANSITION"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "trans_256_281_TEAM_0_NEUTRAL_TRANSITION",
        "sequence_id": "SNMOT-068",
        "start_frame": 256,
        "end_frame": 281,
        "start_timestamp": 10.2,
        "end_timestamp": 11.24,
        "event_family": "POST_LOSS_ENGAGEMENT",
        "semantic_level": "LEVEL_3_TACTICAL_CANDIDATE",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.4547176174261669,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2",
            "EXP-23 defensive_pressure",
            "EXP-24 tactical_transitions"
        ],
        "supporting_metrics": {
            "counterpress_score": 0.455,
            "recovery_score": 0.185,
            "candidate_label": "NEUTRAL_TRANSITION",
            "pressure_pre_mean": 0.212,
            "pressure_post_mean": 0.291,
            "pressure_delta": 0.079,
            "nearest_defender_pre": 3.1,
            "nearest_defender_post": 3.25,
            "nearest_distance_delta": 0.15,
            "density_r3_post": 0.46,
            "density_r5_post": 0.69,
            "centroid_ball_distance_delta": -0.52,
            "defensive_line_velocity": 2.54,
            "ball_delta_x_attack": 7.03
        },
        "limitations": [
            "Diagnostic candidate semantics; physics-derived GT evaluation"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 engaged in post-loss pressing against TEAM_1 (10.20\u201311.24s, \u0394t=1.04s). Nearest defender closed from 3.1m to 3.2m; PressureIndex changed from 0.21 to 0.29. CounterpressScore: 0.46 [Confidence: 0.45].",
        "related_event_ids": [
            "poss_change_256_TEAM_0_to_TEAM_1",
            "press_256_270_TEAM_0"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_311_350_TEAM_1",
        "sequence_id": "SNMOT-068",
        "start_frame": 311,
        "end_frame": 350,
        "start_timestamp": 12.4,
        "end_timestamp": 13.96,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.6059327874453587,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.606,
            "peak_pressure_index": 1.0,
            "duration_frames": 40,
            "nearest_defender_min_m": 0.2,
            "max_closing_speed_mps": 4.4
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 applied continuous defensive pressure on TEAM_0 (12.40\u201313.96s, dur: 1.56s). Mean PressureIndex: 0.61 (peak: 1.00), min defender proximity: 0.2m.",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "pass_324_327_TEAM_0_PASS_INTERCEPTED",
        "sequence_id": "SNMOT-068",
        "start_frame": 324,
        "end_frame": 327,
        "start_timestamp": 12.92,
        "end_timestamp": 13.04,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.8624999999999999,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_INTERCEPTED",
            "pass_distance_m": 2.63,
            "forward_displacement_m": 0.0,
            "sender_track_id": 21,
            "receiver_track_id": 10
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 ball transfer completed (12.92\u201313.04s). Distance: 2.6m, forward displacement: +0.0m [Confidence: 0.86].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "poss_change_327_TEAM_0_to_TEAM_1",
        "sequence_id": "SNMOT-068",
        "start_frame": 327,
        "end_frame": 327,
        "start_timestamp": 13.04,
        "end_timestamp": 13.04,
        "event_family": "POSSESSION_CHANGE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.9348344802856445,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2"
        ],
        "supporting_metrics": {
            "turnover_frame": 327,
            "losing_team": "TEAM_0",
            "gaining_team": "TEAM_1",
            "upstream_confidence": 0.9348344802856445
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 lost possession to TEAM_1 at 13.04s (frame 327). Possession confidence: 0.93 [HIGH].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_327_350_TEAM_0",
        "sequence_id": "SNMOT-068",
        "start_frame": 327,
        "end_frame": 350,
        "start_timestamp": 13.04,
        "end_timestamp": 13.96,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.6582602827149018,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.658,
            "peak_pressure_index": 0.775,
            "duration_frames": 24,
            "nearest_defender_min_m": 1.05,
            "max_closing_speed_mps": 5.92
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 applied continuous defensive pressure on TEAM_1 (13.04\u201313.96s, dur: 0.92s). Mean PressureIndex: 0.66 (peak: 0.78), min defender proximity: 1.1m.",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "pass_331_341_TEAM_1_PASS_INTERCEPTED",
        "sequence_id": "SNMOT-068",
        "start_frame": 331,
        "end_frame": 341,
        "start_timestamp": 13.2,
        "end_timestamp": 13.6,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.8624999999999999,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_INTERCEPTED",
            "pass_distance_m": 3.39,
            "forward_displacement_m": 0.0,
            "sender_track_id": 10,
            "receiver_track_id": 9
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 ball transfer completed (13.20\u201313.60s). Distance: 3.4m, forward displacement: +0.0m [Confidence: 0.86].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "poss_change_341_TEAM_1_to_TEAM_0",
        "sequence_id": "SNMOT-068",
        "start_frame": 341,
        "end_frame": 341,
        "start_timestamp": 13.6,
        "end_timestamp": 13.6,
        "event_family": "POSSESSION_CHANGE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.9714266061782837,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2"
        ],
        "supporting_metrics": {
            "turnover_frame": 341,
            "losing_team": "TEAM_1",
            "gaining_team": "TEAM_0",
            "upstream_confidence": 0.9714266061782837
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 lost possession to TEAM_0 at 13.60s (frame 341). Possession confidence: 0.97 [HIGH].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "pass_348_350_TEAM_0_PASS_INTERCEPTED",
        "sequence_id": "SNMOT-068",
        "start_frame": 348,
        "end_frame": 350,
        "start_timestamp": 13.88,
        "end_timestamp": 13.96,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.8375,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_INTERCEPTED",
            "pass_distance_m": 1.64,
            "forward_displacement_m": 0.0,
            "sender_track_id": 9,
            "receiver_track_id": 13
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 ball transfer completed (13.88\u201313.96s). Distance: 1.6m, forward displacement: +0.0m [Confidence: 0.84].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    }
],
    report: "# RAPPORT D'INTELLIGENCE TACTIQUE VID\u00c9O : S\u00c9QUENCE `SNMOT-068`\n> [!NOTE] Ce rapport d'analyse est g\u00e9n\u00e9r\u00e9 exclusivement \u00e0 partir d'\u00e9vidences visuelles valid\u00e9es (EXP-25) et de primitives g\u00e9om\u00e9triques mesur\u00e9es. Aucune extrapolation sp\u00e9culative ou formation rigide n'est affirm\u00e9e sans support probatoire direct.\n\n## 1. VUE D'ENSEMBLE DU MATCH & COUVERTURE D'\u00c9VIDENCE\nLa s\u00e9quence analys\u00e9e s'\u00e9tend de 2.08s \u00e0 13.96s (dur\u00e9e active observ\u00e9e : 11.88s).\nLe pipeline de fusion d'\u00e9vidences tactiques a extrait un total de 16 \u00e9v\u00e9nements probants sur la s\u00e9quence.\nLa distribution \u00e9pist\u00e9mique comprend 14 faits physiques mesur\u00e9s (Niveau 1), 0 tendances structurelles (Niveau 2), et 2 candidats tactiques qualifi\u00e9s (Niveau 3).\n\n## 2. CONTR\u00d4LE DU BALLON & CONTINUIT\u00c9 DE POSSESSION\n> [!IMPORTANT] L'estimateur de possession EXP-22 op\u00e8re sur des trajectoires de d\u00e9tection soumises aux troncatures broadcast. Les pourcentages ci-dessous refl\u00e8tent le temps de possession s\u00e9curis\u00e9e mesur\u00e9 sur les frames analys\u00e9es, et non une statistique absolue de match.\n- **TEAM_0** : Sur les images exploitables, l'estimateur a mesur\u00e9 18.6% de possession s\u00e9curis\u00e9e (dur\u00e9e cumul\u00e9e : 2.60s, transitions/pertes enregistr\u00e9es : 3) [source:team_summary/TEAM_0/possession | cov=100% | conf=0.54].\n- **TEAM_1** : Sur les images exploitables, l'estimateur a mesur\u00e9 43.7% de possession s\u00e9curis\u00e9e (dur\u00e9e cumul\u00e9e : 6.12s, transitions/pertes enregistr\u00e9es : 1) [source:team_summary/TEAM_1/possession | cov=100% | conf=0.55].\n\n## 3. ORGANISATION D\u00c9FENSIVE, BLOC & COMPACIT\u00c9\n> [!TIP] Conform\u00e9ment \u00e0 la politique EXP-21/EXP-25, les d\u00e9formations tactiques fluides sont d\u00e9crites par leurs coordonn\u00e9es continues (hauteur de ligne, largeur, profondeur) plut\u00f4t que par des \u00e9tiquettes de formation nominales (4-3-3 ou 4-4-2).\n- **TEAM_0** : La ligne d\u00e9fensive s'est positionn\u00e9e \u00e0 une hauteur moyenne mesur\u00e9e de 65.7m du but d\u00e9fendu, correspondant \u00e0 un bloc haut (sup\u00e9rieur \u00e0 la ligne m\u00e9diane) [source:team_summary/TEAM_0/defensive_line | cov=100% | conf=0.54].\n  La structure spatiale pr\u00e9sentait une profondeur moyenne de 24.7m, une largeur de 19.6m et une surface d'enveloppe convexe moyenne de 219.9m\u00b2 [source:team_summary/TEAM_0/compactness | conf=0.54].\n- **TEAM_1** : La ligne d\u00e9fensive s'est positionn\u00e9e \u00e0 une hauteur moyenne mesur\u00e9e de 22.6m du but d\u00e9fendu, correspondant \u00e0 un bloc bas [source:team_summary/TEAM_1/defensive_line | cov=100% | conf=0.55].\n  La structure spatiale pr\u00e9sentait une profondeur moyenne de 22.7m, une largeur de 15.4m et une surface d'enveloppe convexe moyenne de 135.9m\u00b2 [source:team_summary/TEAM_1/compactness | conf=0.55].\n\n## 4. PRESSION D\u00c9FENSIVE & HARC\u00c8LEMENT CONTINU\n> [!NOTE] Les indices de pression reposent sur les primitives continues de l'EXP-23 (proximit\u00e9, vitesse de fermeture g\u00e9om\u00e9trique et densit\u00e9 locale).\n- **TEAM_0** : Pression moyenne exerc\u00e9e de 0.264 (pic mesur\u00e9 \u00e0 0.775), avec 3 \u00e9pisodes de pression \u00e0 haute intensit\u00e9 document\u00e9s [source:team_summary/TEAM_0/pressure | conf=0.54].\n- **TEAM_1** : Pression moyenne exerc\u00e9e de 0.461 (pic mesur\u00e9 \u00e0 1.000), avec 3 \u00e9pisodes de pression \u00e0 haute intensit\u00e9 document\u00e9s [source:team_summary/TEAM_1/pressure | conf=0.55].\n\n## 5. TRANSITIONS APR\u00c8S PERTE DE BALLE & CANDIDATS CONTRE-PRESSING\n> [!CAUTION] Les d\u00e9tections de transitions (Niveau 3) sont des candidats diagnostiques qualifi\u00e9s par des heuristiques de physique du jeu. Elles ne constituent pas des annotations tactiques humaines ind\u00e9pendantes certifi\u00e9es.\n- **TEAM_0** : Apr\u00e8s perte de balle, les signaux physiques mesur\u00e9s sont compatibles avec un candidat de contre-pressing (score moyen : 0.529) et un indice de repli d\u00e9fensif de 0.194 [source:team_summary/TEAM_0/transitions | conf=0.54].\n- **TEAM_1** : Aucun \u00e9pisode de transition agressive post-perte significative n'a \u00e9t\u00e9 d\u00e9tect\u00e9 [source:team_summary/TEAM_1/transitions | conf=0.55].\n\n## 6. TRANSMISSIONS DE BALLE & DISPLACEMENTS OBSERV\u00c9S\n- **TEAM_0** : Transmissions de balle directes valid\u00e9es par filtrage qualit\u00e9 : 0 (d\u00e9placement longitudinal net : +0.0m) [source:team_summary/TEAM_0/ball_transfers | conf=0.54].\n- **TEAM_1** : Transmissions de balle directes valid\u00e9es par filtrage qualit\u00e9 : 0 (d\u00e9placement longitudinal net : +0.0m) [source:team_summary/TEAM_1/ball_transfers | conf=0.55].\n\n## 7. CHRONOLOGIE DES \u00c9V\u00c9NEMENTS PROBANTS CL\u00c9S\n- **2.08s \u2013 2.16s** (Fait physique) : TEAM_0 ball transfer completed (2.08\u20132.16s). Distance: 1.6m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]\n- **2.08s \u2013 9.68s** (Fait physique) : TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08\u20139.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m. [event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]\n- **2.16s \u2013 2.16s** (Fait physique) : TEAM_0 lost possession to TEAM_1 at 2.16s (frame 55). Possession confidence: 0.39 [LOW]. [event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]\n- **2.16s \u2013 3.20s** (Candidat qualifi\u00e9) : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (2.16\u20133.20s, \u0394t=1.04s). Nearest defender closed from 1.9m to 4.0m; PressureIndex changed from 0.08 to 0.26. CounterpressScore: 0.60 [Confidence: 0.60]. [event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]\n- **7.80s \u2013 8.24s** (Fait physique) : TEAM_0 applied continuous defensive pressure on TEAM_1 (7.80\u20138.24s, dur: 0.44s). Mean PressureIndex: 0.37 (peak: 0.54), min defender proximity: 1.7m. [event:press_196_207_TEAM_0 | t=7.80s | conf=0.37 | HIGH]\n- **9.88s \u2013 11.44s** (Fait physique) : TEAM_1 applied continuous defensive pressure on TEAM_0 (9.88\u201311.44s, dur: 1.56s). Mean PressureIndex: 0.46 (peak: 0.66), min defender proximity: 1.4m. [event:press_248_287_TEAM_1 | t=9.88s | conf=0.46 | HIGH]\n- **10.20s \u2013 10.20s** (Fait physique) : TEAM_0 lost possession to TEAM_1 at 10.20s (frame 256). Possession confidence: 0.48 [HIGH]. [event:poss_change_256_TEAM_0_to_TEAM_1 | t=10.20s | conf=0.48 | HIGH]\n- **10.20s \u2013 10.76s** (Fait physique) : TEAM_0 applied continuous defensive pressure on TEAM_1 (10.20\u201310.76s, dur: 0.56s). Mean PressureIndex: 0.45 (peak: 0.64), min defender proximity: 1.4m. [event:press_256_270_TEAM_0 | t=10.20s | conf=0.45 | HIGH]\n- **10.20s \u2013 11.24s** (Candidat qualifi\u00e9) : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (10.20\u201311.24s, \u0394t=1.04s). Nearest defender closed from 3.1m to 3.2m; PressureIndex changed from 0.21 to 0.29. CounterpressScore: 0.46 [Confidence: 0.45]. [event:trans_256_281_TEAM_0_NEUTRAL_TRANSITION | t=10.20s | conf=0.45 | HIGH]\n- **12.40s \u2013 13.96s** (Fait physique) : TEAM_1 applied continuous defensive pressure on TEAM_0 (12.40\u201313.96s, dur: 1.56s). Mean PressureIndex: 0.61 (peak: 1.00), min defender proximity: 0.2m. [event:press_311_350_TEAM_1 | t=12.40s | conf=0.61 | HIGH]\n- **12.92s \u2013 13.04s** (Fait physique) : TEAM_0 ball transfer completed (12.92\u201313.04s). Distance: 2.6m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_324_327_TEAM_0_PASS_INTERCEPTED | t=12.92s | conf=0.86 | HIGH]\n- **13.04s \u2013 13.04s** (Fait physique) : TEAM_0 lost possession to TEAM_1 at 13.04s (frame 327). Possession confidence: 0.93 [HIGH]. [event:poss_change_327_TEAM_0_to_TEAM_1 | t=13.04s | conf=0.93 | HIGH]\n- **13.04s \u2013 13.96s** (Fait physique) : TEAM_0 applied continuous defensive pressure on TEAM_1 (13.04\u201313.96s, dur: 0.92s). Mean PressureIndex: 0.66 (peak: 0.78), min defender proximity: 1.1m. [event:press_327_350_TEAM_0 | t=13.04s | conf=0.66 | HIGH]\n- **13.20s \u2013 13.60s** (Fait physique) : TEAM_1 ball transfer completed (13.20\u201313.60s). Distance: 3.4m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_331_341_TEAM_1_PASS_INTERCEPTED | t=13.20s | conf=0.86 | HIGH]\n- **13.60s \u2013 13.60s** (Fait physique) : TEAM_1 lost possession to TEAM_0 at 13.60s (frame 341). Possession confidence: 0.97 [HIGH]. [event:poss_change_341_TEAM_1_to_TEAM_0 | t=13.60s | conf=0.97 | HIGH]\n\n## 8. QUALIT\u00c9 DES DONN\u00c9ES & LIMITES M\u00c9THODOLOGIQUES\n- L'analyse est soumise \u00e0 la troncature du champ de vision propre aux retransmissions t\u00e9l\u00e9vis\u00e9es standard.\n- Les inf\u00e9rences de pressing et de transition restent des proxies physiques sans validation s\u00e9mantique humaine ind\u00e9pendante.\n- L'exactitude des cha\u00eenes de passes est d\u00e9pendante du bruit de tracking sur le porteur du ballon.\n\n**Avertissements sp\u00e9cifiques \u00e0 cette s\u00e9quence :**\n- Diagnostic candidate semantics; physics-derived GT evaluation\n- Downstream of pass detector baseline; precision limited by tracking flicker\n",
    qaExamples: [
    {
        "id": "fact_01",
        "category": "EXACT_FACT",
        "analysis_id": "SNMOT-068",
        "query": "Quelle \u00e9quipe a perdu le ballon \u00e0 2.16s ?",
        "query_scope": "MATCH_COMPARISON",
        "confidence": 0.572,
        "answer": "### \ud83d\udcca Comparaison des \u00c9quipes (Agr\u00e9gats Vid\u00e9o)\n**\u00c9quipe TEAM_0** :\n- Possession contr\u00f4l\u00e9e : 18.6% (dur\u00e9e: 2.60s, pertes/gains: 3) *(couverture: 100%, conf: 0.54)*\n- Hauteur moyenne du bloc : 65.7m (profondeur: 24.7m, largeur: 19.6m)\n- Pression d\u00e9fensive : indice moyen 0.264 (pic: 0.775, \u00e9pisodes intenses: 3)\n- R\u00e9activit\u00e9 \u00e0 la perte (candidat contre-pressing) : indice moyen 0.529 *(diagnostic)*\n\n**\u00c9quipe TEAM_1** :\n- Possession contr\u00f4l\u00e9e : 43.7% (dur\u00e9e: 6.12s, pertes/gains: 1) *(couverture: 100%, conf: 0.55)*\n- Hauteur moyenne du bloc : 22.6m (profondeur: 22.7m, largeur: 15.4m)\n- Pression d\u00e9fensive : indice moyen 0.461 (pic: 1.000, \u00e9pisodes intenses: 3)\n\n\n**Limites m\u00e9thodologiques :**\n- *Diagnostic candidate semantics; physics-derived GT evaluation*\n- *Downstream of pass detector baseline; precision limited by tracking flicker*",
        "evidence_citations": [
            "[event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]",
            "[event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]",
            "[event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]",
            "[event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]"
        ],
        "knowledge_citations": [],
        "is_abstention": false
    },
    {
        "id": "fact_02",
        "category": "EXACT_FACT",
        "analysis_id": "SNMOT-068",
        "query": "Y a-t-il eu un \u00e9pisode de pression d\u00e9fensive \u00e0 2.08s ?",
        "query_scope": "MATCH_TIMELINE",
        "confidence": 0.572,
        "answer": "### \u23f1\ufe0f \u00c9v\u00e9nements et Preuves Vid\u00e9o\n- **2.08s \u2013 2.16s** : TEAM_0 ball transfer completed (2.08\u20132.16s). Distance: 1.6m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]\n- **2.08s \u2013 9.68s** : TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08\u20139.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m. [event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]\n- **2.16s \u2013 2.16s** : TEAM_0 lost possession to TEAM_1 at 2.16s (frame 55). Possession confidence: 0.39 [LOW]. [event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]\n- **2.16s \u2013 3.20s** : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (2.16\u20133.20s, \u0394t=1.04s). Nearest defender closed from 1.9m to 4.0m; PressureIndex changed from 0.08 to 0.26. CounterpressScore: 0.60 [Confidence: 0.60]. [event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]\n\n**Limites m\u00e9thodologiques :**\n- *Diagnostic candidate semantics; physics-derived GT evaluation*\n- *Downstream of pass detector baseline; precision limited by tracking flicker*",
        "evidence_citations": [
            "[event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]",
            "[event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]",
            "[event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]",
            "[event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]"
        ],
        "knowledge_citations": [],
        "is_abstention": false
    },
    {
        "id": "fact_03",
        "category": "EXACT_FACT",
        "analysis_id": "SNMOT-068",
        "query": "Quelle est la distance du transfert de balle \u00e0 2.08s ?",
        "query_scope": "MATCH_TIMELINE",
        "confidence": 0.572,
        "answer": "### \u23f1\ufe0f \u00c9v\u00e9nements et Preuves Vid\u00e9o\n- **2.08s \u2013 2.16s** : TEAM_0 ball transfer completed (2.08\u20132.16s). Distance: 1.6m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]\n- **2.08s \u2013 9.68s** : TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08\u20139.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m. [event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]\n- **2.16s \u2013 2.16s** : TEAM_0 lost possession to TEAM_1 at 2.16s (frame 55). Possession confidence: 0.39 [LOW]. [event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]\n- **2.16s \u2013 3.20s** : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (2.16\u20133.20s, \u0394t=1.04s). Nearest defender closed from 1.9m to 4.0m; PressureIndex changed from 0.08 to 0.26. CounterpressScore: 0.60 [Confidence: 0.60]. [event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]\n\n**Limites m\u00e9thodologiques :**\n- *Diagnostic candidate semantics; physics-derived GT evaluation*\n- *Downstream of pass detector baseline; precision limited by tracking flicker*",
        "evidence_citations": [
            "[event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]",
            "[event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]",
            "[event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]",
            "[event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]"
        ],
        "knowledge_citations": [],
        "is_abstention": false
    },
    {
        "id": "fact_06",
        "category": "EXACT_FACT",
        "analysis_id": "SNMOT-068",
        "query": "Qui exerce la pression d\u00e9fensive \u00e0 9.5s ?",
        "query_scope": "MATCH_TIMELINE",
        "confidence": 0.449,
        "answer": "### \u23f1\ufe0f \u00c9v\u00e9nements et Preuves Vid\u00e9o\n- **2.08s \u2013 9.68s** : TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08\u20139.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m. [event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]\n- **9.88s \u2013 11.44s** : TEAM_1 applied continuous defensive pressure on TEAM_0 (9.88\u201311.44s, dur: 1.56s). Mean PressureIndex: 0.46 (peak: 0.66), min defender proximity: 1.4m. [event:press_248_287_TEAM_1 | t=9.88s | conf=0.46 | HIGH]",
        "evidence_citations": [
            "[event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]",
            "[event:press_248_287_TEAM_1 | t=9.88s | conf=0.46 | HIGH]"
        ],
        "knowledge_citations": [],
        "is_abstention": false
    },
    {
        "id": "fact_08",
        "category": "EXACT_FACT",
        "analysis_id": "SNMOT-068",
        "query": "Quel est le porteur de balle initial au d\u00e9but de la s\u00e9quence ?",
        "query_scope": "MATCH_FACT",
        "confidence": 0.506,
        "answer": "### \u23f1\ufe0f \u00c9v\u00e9nements et Preuves Vid\u00e9o\n- **2.08s \u2013 2.16s** : TEAM_0 ball transfer completed (2.08\u20132.16s). Distance: 1.6m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]\n- **2.08s \u2013 9.68s** : TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08\u20139.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m. [event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]\n- **2.16s \u2013 2.16s** : TEAM_0 lost possession to TEAM_1 at 2.16s (frame 55). Possession confidence: 0.39 [LOW]. [event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]\n- **2.16s \u2013 3.20s** : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (2.16\u20133.20s, \u0394t=1.04s). Nearest defender closed from 1.9m to 4.0m; PressureIndex changed from 0.08 to 0.26. CounterpressScore: 0.60 [Confidence: 0.60]. [event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]\n- **7.80s \u2013 8.24s** : TEAM_0 applied continuous defensive pressure on TEAM_1 (7.80\u20138.24s, dur: 0.44s). Mean PressureIndex: 0.37 (peak: 0.54), min defender proximity: 1.7m. [event:press_196_207_TEAM_0 | t=7.80s | conf=0.37 | HIGH]\n- **9.88s \u2013 11.44s** : TEAM_1 applied continuous defensive pressure on TEAM_0 (9.88\u201311.44s, dur: 1.56s). Mean PressureIndex: 0.46 (peak: 0.66), min defender proximity: 1.4m. [event:press_248_287_TEAM_1 | t=9.88s | conf=0.46 | HIGH]\n- **10.20s \u2013 10.20s** : TEAM_0 lost possession to TEAM_1 at 10.20s (frame 256). Possession confidence: 0.48 [HIGH]. [event:poss_change_256_TEAM_0_to_TEAM_1 | t=10.20s | conf=0.48 | HIGH]\n- **10.20s \u2013 10.76s** : TEAM_0 applied continuous defensive pressure on TEAM_1 (10.20\u201310.76s, dur: 0.56s). Mean PressureIndex: 0.45 (peak: 0.64), min defender proximity: 1.4m. [event:press_256_270_TEAM_0 | t=10.20s | conf=0.45 | HIGH]\n\n**Limites m\u00e9thodologiques :**\n- *Diagnostic candidate semantics; physics-derived GT evaluation*\n- *Downstream of pass detector baseline; precision limited by tracking flicker*",
        "evidence_citations": [
            "[event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]",
            "[event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]",
            "[event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]",
            "[event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]",
            "[event:press_196_207_TEAM_0 | t=7.80s | conf=0.37 | HIGH]",
            "[event:press_248_287_TEAM_1 | t=9.88s | conf=0.46 | HIGH]",
            "[event:poss_change_256_TEAM_0_to_TEAM_1 | t=10.20s | conf=0.48 | HIGH]",
            "[event:press_256_270_TEAM_0 | t=10.20s | conf=0.45 | HIGH]"
        ],
        "knowledge_citations": [],
        "is_abstention": false
    },
    {
        "id": "fact_10",
        "category": "EXACT_FACT",
        "analysis_id": "SNMOT-068",
        "query": "Quel \u00e9v\u00e9nement survient exactement \u00e0 8.0 secondes ?",
        "query_scope": "MATCH_TIMELINE",
        "confidence": 0.408,
        "answer": "### \u23f1\ufe0f \u00c9v\u00e9nements et Preuves Vid\u00e9o\n- **2.08s \u2013 9.68s** : TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08\u20139.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m. [event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]\n- **7.80s \u2013 8.24s** : TEAM_0 applied continuous defensive pressure on TEAM_1 (7.80\u20138.24s, dur: 0.44s). Mean PressureIndex: 0.37 (peak: 0.54), min defender proximity: 1.7m. [event:press_196_207_TEAM_0 | t=7.80s | conf=0.37 | HIGH]",
        "evidence_citations": [
            "[event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]",
            "[event:press_196_207_TEAM_0 | t=7.80s | conf=0.37 | HIGH]"
        ],
        "knowledge_citations": [],
        "is_abstention": false
    },
    {
        "id": "time_01",
        "category": "TIMESTAMP",
        "analysis_id": "SNMOT-068",
        "query": "Que se passe-t-il \u00e0 2.16 secondes ?",
        "query_scope": "MATCH_TIMELINE",
        "confidence": 0.572,
        "answer": "### \u23f1\ufe0f \u00c9v\u00e9nements et Preuves Vid\u00e9o\n- **2.08s \u2013 2.16s** : TEAM_0 ball transfer completed (2.08\u20132.16s). Distance: 1.6m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]\n- **2.08s \u2013 9.68s** : TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08\u20139.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m. [event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]\n- **2.16s \u2013 2.16s** : TEAM_0 lost possession to TEAM_1 at 2.16s (frame 55). Possession confidence: 0.39 [LOW]. [event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]\n- **2.16s \u2013 3.20s** : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (2.16\u20133.20s, \u0394t=1.04s). Nearest defender closed from 1.9m to 4.0m; PressureIndex changed from 0.08 to 0.26. CounterpressScore: 0.60 [Confidence: 0.60]. [event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]\n\n**Limites m\u00e9thodologiques :**\n- *Diagnostic candidate semantics; physics-derived GT evaluation*\n- *Downstream of pass detector baseline; precision limited by tracking flicker*",
        "evidence_citations": [
            "[event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]",
            "[event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]",
            "[event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]",
            "[event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]"
        ],
        "knowledge_citations": [],
        "is_abstention": false
    },
    {
        "id": "time_02",
        "category": "TIMESTAMP",
        "analysis_id": "SNMOT-068",
        "query": "Quels \u00e9v\u00e9nements se d\u00e9roulent entre 2.0s et 4.0s ?",
        "query_scope": "MATCH_TIMELINE",
        "confidence": 0.572,
        "answer": "### \u23f1\ufe0f \u00c9v\u00e9nements et Preuves Vid\u00e9o\n- **2.08s \u2013 2.16s** : TEAM_0 ball transfer completed (2.08\u20132.16s). Distance: 1.6m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]\n- **2.08s \u2013 9.68s** : TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08\u20139.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m. [event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]\n- **2.16s \u2013 2.16s** : TEAM_0 lost possession to TEAM_1 at 2.16s (frame 55). Possession confidence: 0.39 [LOW]. [event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]\n- **2.16s \u2013 3.20s** : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (2.16\u20133.20s, \u0394t=1.04s). Nearest defender closed from 1.9m to 4.0m; PressureIndex changed from 0.08 to 0.26. CounterpressScore: 0.60 [Confidence: 0.60]. [event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]\n\n**Limites m\u00e9thodologiques :**\n- *Diagnostic candidate semantics; physics-derived GT evaluation*\n- *Downstream of pass detector baseline; precision limited by tracking flicker*",
        "evidence_citations": [
            "[event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]",
            "[event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]",
            "[event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]",
            "[event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]"
        ],
        "knowledge_citations": [],
        "is_abstention": false
    },
    {
        "id": "time_03",
        "category": "TIMESTAMP",
        "analysis_id": "SNMOT-068",
        "query": "Que font les \u00e9quipes \u00e0 10.0 secondes ?",
        "query_scope": "MATCH_TIMELINE",
        "confidence": 0.457,
        "answer": "### \u23f1\ufe0f \u00c9v\u00e9nements et Preuves Vid\u00e9o\n- **2.08s \u2013 9.68s** : TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08\u20139.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m. [event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]\n- **9.88s \u2013 11.44s** : TEAM_1 applied continuous defensive pressure on TEAM_0 (9.88\u201311.44s, dur: 1.56s). Mean PressureIndex: 0.46 (peak: 0.66), min defender proximity: 1.4m. [event:press_248_287_TEAM_1 | t=9.88s | conf=0.46 | HIGH]\n- **10.20s \u2013 10.20s** : TEAM_0 lost possession to TEAM_1 at 10.20s (frame 256). Possession confidence: 0.48 [HIGH]. [event:poss_change_256_TEAM_0_to_TEAM_1 | t=10.20s | conf=0.48 | HIGH]\n- **10.20s \u2013 10.76s** : TEAM_0 applied continuous defensive pressure on TEAM_1 (10.20\u201310.76s, dur: 0.56s). Mean PressureIndex: 0.45 (peak: 0.64), min defender proximity: 1.4m. [event:press_256_270_TEAM_0 | t=10.20s | conf=0.45 | HIGH]\n- **10.20s \u2013 11.24s** : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (10.20\u201311.24s, \u0394t=1.04s). Nearest defender closed from 3.1m to 3.2m; PressureIndex changed from 0.21 to 0.29. CounterpressScore: 0.46 [Confidence: 0.45]. [event:trans_256_281_TEAM_0_NEUTRAL_TRANSITION | t=10.20s | conf=0.45 | HIGH]\n\n**Limites m\u00e9thodologiques :**\n- *Diagnostic candidate semantics; physics-derived GT evaluation*",
        "evidence_citations": [
            "[event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]",
            "[event:press_248_287_TEAM_1 | t=9.88s | conf=0.46 | HIGH]",
            "[event:poss_change_256_TEAM_0_to_TEAM_1 | t=10.20s | conf=0.48 | HIGH]",
            "[event:press_256_270_TEAM_0 | t=10.20s | conf=0.45 | HIGH]",
            "[event:trans_256_281_TEAM_0_NEUTRAL_TRANSITION | t=10.20s | conf=0.45 | HIGH]"
        ],
        "knowledge_citations": [],
        "is_abstention": false
    }
]
  },
  'SNMOT-069': {
    id: 'SNMOT-069',
    title: 'SNMOT-069 (Holdout Benchmark)',
    subtitle: 'Séquence SoccerNet Tracking 2023 holdout partition',
    durationSeconds: 14.0,
    fps: 25.0,
    framesAnalyzed: 350,
    mode: 'QUALITY',
    throughputFps: 11.4,
    strict25Fps: false,
    videoUrl: "/demo_videos/SNMOT-069.mp4",
    posterUrl: "/demo_videos/SNMOT-069_poster.jpg",
    summary: {
    "TEAM_0": {
        "team_id": "TEAM_0",
        "reliability": {
            "coverage_pct": 100.0,
            "valid_frames": 350,
            "total_frames": 350,
            "confidence_mean": 0.65,
            "confidence_p10": 0.49,
            "quality_distribution": {
                "HIGH": 327,
                "MEDIUM": 23
            }
        },
        "secure_possession_duration_s": 7.32,
        "secure_possession_pct": 52.3,
        "possession_change_count": 4,
        "mean_defensive_line_height_m": 54.36,
        "mean_team_depth_m": 18.68,
        "mean_team_width_m": 19.95,
        "mean_hull_area_m2": 227.18,
        "mean_pressure_index": 0.425,
        "peak_pressure_index": 0.852,
        "high_quality_pressure_episode_count": 4,
        "post_loss_counterpress_mean": 0.423,
        "defensive_recovery_mean": 0.334,
        "net_forward_progression_m": 0.0,
        "completed_pass_count": 3,
        "observed_line_structures": [],
        "formation_hypothesis": null
    },
    "TEAM_1": {
        "team_id": "TEAM_1",
        "reliability": {
            "coverage_pct": 100.0,
            "valid_frames": 350,
            "total_frames": 350,
            "confidence_mean": 0.633,
            "confidence_p10": 0.49,
            "quality_distribution": {
                "MEDIUM": 211,
                "HIGH": 139
            }
        },
        "secure_possession_duration_s": 3.64,
        "secure_possession_pct": 26.0,
        "possession_change_count": 2,
        "mean_defensive_line_height_m": 25.02,
        "mean_team_depth_m": 21.9,
        "mean_team_width_m": 19.1,
        "mean_hull_area_m2": 229.45,
        "mean_pressure_index": 0.393,
        "peak_pressure_index": 0.94,
        "high_quality_pressure_episode_count": 2,
        "post_loss_counterpress_mean": 0.443,
        "defensive_recovery_mean": 0.105,
        "net_forward_progression_m": 0.0,
        "completed_pass_count": 3,
        "observed_line_structures": [],
        "formation_hypothesis": null
    }
},
    events: [
    {
        "event_id": "pass_48_49_TEAM_0_PASS_COMPLETED",
        "sequence_id": "SNMOT-069",
        "start_frame": 48,
        "end_frame": 49,
        "start_timestamp": 1.88,
        "end_timestamp": 1.92,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.775,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_COMPLETED",
            "pass_distance_m": 0.41,
            "forward_displacement_m": 0.0,
            "sender_track_id": 19,
            "receiver_track_id": 18
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 ball transfer completed (1.88\u20131.92s). Distance: 0.4m, forward displacement: +0.0m [Confidence: 0.78].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "pass_63_76_TEAM_0_PASS_COMPLETED",
        "sequence_id": "SNMOT-069",
        "start_frame": 63,
        "end_frame": 76,
        "start_timestamp": 2.48,
        "end_timestamp": 3.0,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.8624999999999999,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_COMPLETED",
            "pass_distance_m": 0.36,
            "forward_displacement_m": 0.0,
            "sender_track_id": 18,
            "receiver_track_id": 19
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 ball transfer completed (2.48\u20133.00s). Distance: 0.4m, forward displacement: +0.0m [Confidence: 0.86].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "pass_161_162_TEAM_0_PASS_COMPLETED",
        "sequence_id": "SNMOT-069",
        "start_frame": 161,
        "end_frame": 162,
        "start_timestamp": 6.4,
        "end_timestamp": 6.44,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.775,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_COMPLETED",
            "pass_distance_m": 1.06,
            "forward_displacement_m": 0.0,
            "sender_track_id": 18,
            "receiver_track_id": 19
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 ball transfer completed (6.40\u20136.44s). Distance: 1.1m, forward displacement: +0.0m [Confidence: 0.78].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_187_295_TEAM_1",
        "sequence_id": "SNMOT-069",
        "start_frame": 187,
        "end_frame": 295,
        "start_timestamp": 7.44,
        "end_timestamp": 11.76,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.5941082583948458,
        "quality_level": "MEDIUM",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.699,
            "peak_pressure_index": 0.94,
            "duration_frames": 109,
            "nearest_defender_min_m": 0.4,
            "max_closing_speed_mps": 4.33
        },
        "limitations": [],
        "visibility_quality": "MEDIUM",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 applied continuous defensive pressure on TEAM_0 (7.44\u201311.76s, dur: 4.32s). Mean PressureIndex: 0.70 (peak: 0.94), min defender proximity: 0.4m.",
        "related_event_ids": [
            "trans_206_231_TEAM_1_NEUTRAL_TRANSITION"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "poss_change_203_TEAM_0_to_TEAM_1",
        "sequence_id": "SNMOT-069",
        "start_frame": 203,
        "end_frame": 203,
        "start_timestamp": 8.08,
        "end_timestamp": 8.08,
        "event_family": "POSSESSION_CHANGE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.9620257019996643,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2"
        ],
        "supporting_metrics": {
            "turnover_frame": 203,
            "losing_team": "TEAM_0",
            "gaining_team": "TEAM_1",
            "upstream_confidence": 0.9620257019996643
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 lost possession to TEAM_1 at 8.08s (frame 203). Possession confidence: 0.96 [HIGH].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_203_260_TEAM_0",
        "sequence_id": "SNMOT-069",
        "start_frame": 203,
        "end_frame": 260,
        "start_timestamp": 8.08,
        "end_timestamp": 10.36,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.4038484986507215,
        "quality_level": "MEDIUM",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.475,
            "peak_pressure_index": 0.692,
            "duration_frames": 58,
            "nearest_defender_min_m": 0.59,
            "max_closing_speed_mps": 4.27
        },
        "limitations": [],
        "visibility_quality": "MEDIUM",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 applied continuous defensive pressure on TEAM_1 (8.08\u201310.36s, dur: 2.28s). Mean PressureIndex: 0.47 (peak: 0.69), min defender proximity: 0.6m.",
        "related_event_ids": [
            "trans_236_261_TEAM_0_NEUTRAL_TRANSITION"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "poss_change_206_TEAM_1_to_TEAM_0",
        "sequence_id": "SNMOT-069",
        "start_frame": 206,
        "end_frame": 206,
        "start_timestamp": 8.2,
        "end_timestamp": 8.2,
        "event_family": "POSSESSION_CHANGE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.8118192940950394,
        "quality_level": "MEDIUM",
        "source_modules": [
            "EXP-22 possession_v2"
        ],
        "supporting_metrics": {
            "turnover_frame": 206,
            "losing_team": "TEAM_1",
            "gaining_team": "TEAM_0",
            "upstream_confidence": 0.9550815224647522
        },
        "limitations": [],
        "visibility_quality": "MEDIUM",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 lost possession to TEAM_0 at 8.20s (frame 206). Possession confidence: 0.81 [MEDIUM].",
        "related_event_ids": [
            "trans_206_231_TEAM_1_NEUTRAL_TRANSITION"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "trans_206_231_TEAM_1_NEUTRAL_TRANSITION",
        "sequence_id": "SNMOT-069",
        "start_frame": 206,
        "end_frame": 231,
        "start_timestamp": 8.2,
        "end_timestamp": 9.24,
        "event_family": "POST_LOSS_ENGAGEMENT",
        "semantic_level": "LEVEL_3_TACTICAL_CANDIDATE",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.44306149080013946,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2",
            "EXP-23 defensive_pressure",
            "EXP-24 tactical_transitions"
        ],
        "supporting_metrics": {
            "counterpress_score": 0.443,
            "recovery_score": 0.105,
            "candidate_label": "NEUTRAL_TRANSITION",
            "pressure_pre_mean": 0.62,
            "pressure_post_mean": 0.299,
            "pressure_delta": -0.321,
            "nearest_defender_pre": 1.67,
            "nearest_defender_post": 1.34,
            "nearest_distance_delta": -0.33,
            "density_r3_post": 0.5,
            "density_r5_post": 0.92,
            "centroid_ball_distance_delta": -1.23,
            "defensive_line_velocity": 14.16,
            "ball_delta_x_attack": 0.0
        },
        "limitations": [
            "Diagnostic candidate semantics; physics-derived GT evaluation"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 engaged in post-loss pressing against TEAM_0 (8.20\u20139.24s, \u0394t=1.04s). Nearest defender closed from 1.7m to 1.3m; PressureIndex changed from 0.62 to 0.30. CounterpressScore: 0.44 [Confidence: 0.44].",
        "related_event_ids": [
            "poss_change_206_TEAM_1_to_TEAM_0",
            "press_187_295_TEAM_1"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "pass_220_229_TEAM_0_PASS_INTERCEPTED",
        "sequence_id": "SNMOT-069",
        "start_frame": 220,
        "end_frame": 229,
        "start_timestamp": 8.76,
        "end_timestamp": 9.12,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.8375,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_INTERCEPTED",
            "pass_distance_m": 1.07,
            "forward_displacement_m": 0.0,
            "sender_track_id": 19,
            "receiver_track_id": 13
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 ball transfer completed (8.76\u20139.12s). Distance: 1.1m, forward displacement: +0.0m [Confidence: 0.84].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "poss_change_236_TEAM_0_to_TEAM_1",
        "sequence_id": "SNMOT-069",
        "start_frame": 236,
        "end_frame": 236,
        "start_timestamp": 9.4,
        "end_timestamp": 9.4,
        "event_family": "POSSESSION_CHANGE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.8439995646476746,
        "quality_level": "MEDIUM",
        "source_modules": [
            "EXP-22 possession_v2"
        ],
        "supporting_metrics": {
            "turnover_frame": 236,
            "losing_team": "TEAM_0",
            "gaining_team": "TEAM_1",
            "upstream_confidence": 0.9929406642913818
        },
        "limitations": [],
        "visibility_quality": "MEDIUM",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 lost possession to TEAM_1 at 9.40s (frame 236). Possession confidence: 0.84 [MEDIUM].",
        "related_event_ids": [
            "trans_236_261_TEAM_0_NEUTRAL_TRANSITION"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "trans_236_261_TEAM_0_NEUTRAL_TRANSITION",
        "sequence_id": "SNMOT-069",
        "start_frame": 236,
        "end_frame": 261,
        "start_timestamp": 9.4,
        "end_timestamp": 10.44,
        "event_family": "POST_LOSS_ENGAGEMENT",
        "semantic_level": "LEVEL_3_TACTICAL_CANDIDATE",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.4600037232756071,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2",
            "EXP-23 defensive_pressure",
            "EXP-24 tactical_transitions"
        ],
        "supporting_metrics": {
            "counterpress_score": 0.46,
            "recovery_score": 0.249,
            "candidate_label": "NEUTRAL_TRANSITION",
            "pressure_pre_mean": 0.229,
            "pressure_post_mean": 0.325,
            "pressure_delta": 0.096,
            "nearest_defender_pre": 0.83,
            "nearest_defender_post": 3.69,
            "nearest_distance_delta": 2.85,
            "density_r3_post": 0.81,
            "density_r5_post": 1.58,
            "centroid_ball_distance_delta": -0.73,
            "defensive_line_velocity": 0.79,
            "ball_delta_x_attack": -5.74
        },
        "limitations": [
            "Diagnostic candidate semantics; physics-derived GT evaluation"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 engaged in post-loss pressing against TEAM_1 (9.40\u201310.44s, \u0394t=1.04s). Nearest defender closed from 0.8m to 3.7m; PressureIndex changed from 0.23 to 0.33. CounterpressScore: 0.46 [Confidence: 0.46].",
        "related_event_ids": [
            "poss_change_236_TEAM_0_to_TEAM_1",
            "press_203_260_TEAM_0"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "pass_244_245_TEAM_1_PASS_COMPLETED",
        "sequence_id": "SNMOT-069",
        "start_frame": 244,
        "end_frame": 245,
        "start_timestamp": 9.72,
        "end_timestamp": 9.76,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.775,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_COMPLETED",
            "pass_distance_m": 1.06,
            "forward_displacement_m": 0.0,
            "sender_track_id": 13,
            "receiver_track_id": 1
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 ball transfer completed (9.72\u20139.76s). Distance: 1.1m, forward displacement: +0.0m [Confidence: 0.78].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "pass_251_252_TEAM_1_PASS_COMPLETED",
        "sequence_id": "SNMOT-069",
        "start_frame": 251,
        "end_frame": 252,
        "start_timestamp": 10.0,
        "end_timestamp": 10.04,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.775,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_COMPLETED",
            "pass_distance_m": 0.78,
            "forward_displacement_m": 0.0,
            "sender_track_id": 1,
            "receiver_track_id": 13
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 ball transfer completed (10.00\u201310.04s). Distance: 0.8m, forward displacement: +0.0m [Confidence: 0.78].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "pass_280_286_TEAM_0_PASS_INTERCEPTED",
        "sequence_id": "SNMOT-069",
        "start_frame": 280,
        "end_frame": 286,
        "start_timestamp": 11.16,
        "end_timestamp": 11.4,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.8624999999999999,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_INTERCEPTED",
            "pass_distance_m": 2.04,
            "forward_displacement_m": 0.0,
            "sender_track_id": 15,
            "receiver_track_id": 13
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 ball transfer completed (11.16\u201311.40s). Distance: 2.0m, forward displacement: +0.0m [Confidence: 0.86].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "poss_change_286_TEAM_0_to_TEAM_1",
        "sequence_id": "SNMOT-069",
        "start_frame": 286,
        "end_frame": 286,
        "start_timestamp": 11.4,
        "end_timestamp": 11.4,
        "event_family": "POSSESSION_CHANGE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.7738204598426819,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2"
        ],
        "supporting_metrics": {
            "turnover_frame": 286,
            "losing_team": "TEAM_0",
            "gaining_team": "TEAM_1",
            "upstream_confidence": 0.7738204598426819
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 lost possession to TEAM_1 at 11.40s (frame 286). Possession confidence: 0.77 [HIGH].",
        "related_event_ids": [
            "trans_300_325_TEAM_0_NEUTRAL_TRANSITION"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_286_302_TEAM_0",
        "sequence_id": "SNMOT-069",
        "start_frame": 286,
        "end_frame": 302,
        "start_timestamp": 11.4,
        "end_timestamp": 12.04,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.47421815390731115,
        "quality_level": "MEDIUM",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.558,
            "peak_pressure_index": 0.769,
            "duration_frames": 17,
            "nearest_defender_min_m": 0.61,
            "max_closing_speed_mps": 6.59
        },
        "limitations": [],
        "visibility_quality": "MEDIUM",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 applied continuous defensive pressure on TEAM_1 (11.40\u201312.04s, dur: 0.64s). Mean PressureIndex: 0.56 (peak: 0.77), min defender proximity: 0.6m.",
        "related_event_ids": [
            "trans_300_325_TEAM_0_NEUTRAL_TRANSITION"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "poss_change_288_TEAM_1_to_TEAM_0",
        "sequence_id": "SNMOT-069",
        "start_frame": 288,
        "end_frame": 288,
        "start_timestamp": 11.48,
        "end_timestamp": 11.48,
        "event_family": "POSSESSION_CHANGE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.9500551223754883,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2"
        ],
        "supporting_metrics": {
            "turnover_frame": 288,
            "losing_team": "TEAM_1",
            "gaining_team": "TEAM_0",
            "upstream_confidence": 0.9500551223754883
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 lost possession to TEAM_0 at 11.48s (frame 288). Possession confidence: 0.95 [HIGH].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "pass_288_290_TEAM_1_PASS_INTERCEPTED",
        "sequence_id": "SNMOT-069",
        "start_frame": 288,
        "end_frame": 290,
        "start_timestamp": 11.48,
        "end_timestamp": 11.56,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.8624999999999999,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_INTERCEPTED",
            "pass_distance_m": 0.78,
            "forward_displacement_m": 0.0,
            "sender_track_id": 13,
            "receiver_track_id": 15
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 ball transfer completed (11.48\u201311.56s). Distance: 0.8m, forward displacement: +0.0m [Confidence: 0.86].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_298_350_TEAM_1",
        "sequence_id": "SNMOT-069",
        "start_frame": 298,
        "end_frame": 350,
        "start_timestamp": 11.88,
        "end_timestamp": 13.96,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.6494683695552783,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.649,
            "peak_pressure_index": 0.686,
            "duration_frames": 53,
            "nearest_defender_min_m": 0.93,
            "max_closing_speed_mps": 0.91
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 applied continuous defensive pressure on TEAM_0 (11.88\u201313.96s, dur: 2.08s). Mean PressureIndex: 0.65 (peak: 0.69), min defender proximity: 0.9m.",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "poss_change_300_TEAM_0_to_TEAM_1",
        "sequence_id": "SNMOT-069",
        "start_frame": 300,
        "end_frame": 300,
        "start_timestamp": 11.96,
        "end_timestamp": 11.96,
        "event_family": "POSSESSION_CHANGE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.9873237609863281,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2"
        ],
        "supporting_metrics": {
            "turnover_frame": 300,
            "losing_team": "TEAM_0",
            "gaining_team": "TEAM_1",
            "upstream_confidence": 0.9873237609863281
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 lost possession to TEAM_1 at 11.96s (frame 300). Possession confidence: 0.99 [HIGH].",
        "related_event_ids": [
            "trans_300_325_TEAM_0_NEUTRAL_TRANSITION"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "trans_300_325_TEAM_0_NEUTRAL_TRANSITION",
        "sequence_id": "SNMOT-069",
        "start_frame": 300,
        "end_frame": 325,
        "start_timestamp": 11.96,
        "end_timestamp": 13.0,
        "event_family": "POST_LOSS_ENGAGEMENT",
        "semantic_level": "LEVEL_3_TACTICAL_CANDIDATE",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.4193435319163273,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-22 possession_v2",
            "EXP-23 defensive_pressure",
            "EXP-24 tactical_transitions"
        ],
        "supporting_metrics": {
            "counterpress_score": 0.387,
            "recovery_score": 0.419,
            "candidate_label": "NEUTRAL_TRANSITION",
            "pressure_pre_mean": 0.399,
            "pressure_post_mean": 0.414,
            "pressure_delta": 0.015,
            "nearest_defender_pre": 1.25,
            "nearest_defender_post": 2.78,
            "nearest_distance_delta": 1.53,
            "density_r3_post": 0.96,
            "density_r5_post": 1.23,
            "centroid_ball_distance_delta": 5.91,
            "defensive_line_velocity": -9.81,
            "ball_delta_x_attack": -5.76
        },
        "limitations": [
            "Diagnostic candidate semantics; physics-derived GT evaluation"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 engaged in post-loss pressing against TEAM_1 (11.96\u201313.00s, \u0394t=1.04s). Nearest defender closed from 1.2m to 2.8m; PressureIndex changed from 0.40 to 0.41. CounterpressScore: 0.39 [Confidence: 0.42].",
        "related_event_ids": [
            "poss_change_286_TEAM_0_to_TEAM_1",
            "poss_change_300_TEAM_0_to_TEAM_1",
            "press_286_302_TEAM_0",
            "press_303_311_TEAM_0",
            "press_317_350_TEAM_0"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_303_311_TEAM_0",
        "sequence_id": "SNMOT-069",
        "start_frame": 303,
        "end_frame": 311,
        "start_timestamp": 12.08,
        "end_timestamp": 12.4,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.47290862835641023,
        "quality_level": "MEDIUM",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.556,
            "peak_pressure_index": 0.852,
            "duration_frames": 9,
            "nearest_defender_min_m": 1.37,
            "max_closing_speed_mps": 4.73
        },
        "limitations": [],
        "visibility_quality": "MEDIUM",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 applied continuous defensive pressure on TEAM_1 (12.08\u201312.40s, dur: 0.32s). Mean PressureIndex: 0.56 (peak: 0.85), min defender proximity: 1.4m.",
        "related_event_ids": [
            "trans_300_325_TEAM_0_NEUTRAL_TRANSITION"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "pass_307_311_TEAM_1_PASS_COMPLETED",
        "sequence_id": "SNMOT-069",
        "start_frame": 307,
        "end_frame": 311,
        "start_timestamp": 12.24,
        "end_timestamp": 12.4,
        "event_family": "BALL_TRANSFER",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_1",
        "opponent_team": "TEAM_0",
        "confidence": 0.8624999999999999,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-18/EXP-22 possession",
            "EXP-19 pass_detector"
        ],
        "supporting_metrics": {
            "event_type": "PASS_COMPLETED",
            "pass_distance_m": 6.16,
            "forward_displacement_m": 0.0,
            "sender_track_id": 13,
            "receiver_track_id": 16
        },
        "limitations": [
            "Downstream of pass detector baseline; precision limited by tracking flicker"
        ],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_1 ball transfer completed (12.24\u201312.40s). Distance: 6.2m, forward displacement: +0.0m [Confidence: 0.86].",
        "related_event_ids": [],
        "conflict_flag": false,
        "conflict_reason": null
    },
    {
        "event_id": "press_317_350_TEAM_0",
        "sequence_id": "SNMOT-069",
        "start_frame": 317,
        "end_frame": 350,
        "start_timestamp": 12.64,
        "end_timestamp": 13.96,
        "event_family": "PRESSURE_EPISODE",
        "semantic_level": "LEVEL_1_PHYSICAL_FACT",
        "subject_team": "TEAM_0",
        "opponent_team": "TEAM_1",
        "confidence": 0.448615746928317,
        "quality_level": "HIGH",
        "source_modules": [
            "EXP-23 defensive_pressure"
        ],
        "supporting_metrics": {
            "mean_pressure_index": 0.449,
            "peak_pressure_index": 0.596,
            "duration_frames": 34,
            "nearest_defender_min_m": 1.85,
            "max_closing_speed_mps": 3.65
        },
        "limitations": [],
        "visibility_quality": "HIGH",
        "calibration_quality": "VALID",
        "causal": true,
        "summary_text": "TEAM_0 applied continuous defensive pressure on TEAM_1 (12.64\u201313.96s, dur: 1.32s). Mean PressureIndex: 0.45 (peak: 0.60), min defender proximity: 1.9m.",
        "related_event_ids": [
            "trans_300_325_TEAM_0_NEUTRAL_TRANSITION"
        ],
        "conflict_flag": false,
        "conflict_reason": null
    }
],
    report: "# RAPPORT D'INTELLIGENCE TACTIQUE VID\u00c9O : S\u00c9QUENCE `SNMOT-069`\n> [!NOTE] Ce rapport d'analyse est g\u00e9n\u00e9r\u00e9 exclusivement \u00e0 partir d'\u00e9vidences visuelles valid\u00e9es (EXP-25) et de primitives g\u00e9om\u00e9triques mesur\u00e9es. Aucune extrapolation sp\u00e9culative ou formation rigide n'est affirm\u00e9e sans support probatoire direct.\n\n## 1. VUE D'ENSEMBLE DU MATCH & COUVERTURE D'\u00c9VIDENCE\nLa s\u00e9quence analys\u00e9e s'\u00e9tend de 2.08s \u00e0 13.96s (dur\u00e9e active observ\u00e9e : 11.88s).\nLe pipeline de fusion d'\u00e9vidences tactiques a extrait un total de 16 \u00e9v\u00e9nements probants sur la s\u00e9quence.\nLa distribution \u00e9pist\u00e9mique comprend 14 faits physiques mesur\u00e9s (Niveau 1), 0 tendances structurelles (Niveau 2), et 2 candidats tactiques qualifi\u00e9s (Niveau 3).\n\n## 2. CONTR\u00d4LE DU BALLON & CONTINUIT\u00c9 DE POSSESSION\n> [!IMPORTANT] L'estimateur de possession EXP-22 op\u00e8re sur des trajectoires de d\u00e9tection soumises aux troncatures broadcast. Les pourcentages ci-dessous refl\u00e8tent le temps de possession s\u00e9curis\u00e9e mesur\u00e9 sur les frames analys\u00e9es, et non une statistique absolue de match.\n- **TEAM_0** : Sur les images exploitables, l'estimateur a mesur\u00e9 18.6% de possession s\u00e9curis\u00e9e (dur\u00e9e cumul\u00e9e : 2.60s, transitions/pertes enregistr\u00e9es : 3) [source:team_summary/TEAM_0/possession | cov=100% | conf=0.54].\n- **TEAM_1** : Sur les images exploitables, l'estimateur a mesur\u00e9 43.7% de possession s\u00e9curis\u00e9e (dur\u00e9e cumul\u00e9e : 6.12s, transitions/pertes enregistr\u00e9es : 1) [source:team_summary/TEAM_1/possession | cov=100% | conf=0.55].\n\n## 3. ORGANISATION D\u00c9FENSIVE, BLOC & COMPACIT\u00c9\n> [!TIP] Conform\u00e9ment \u00e0 la politique EXP-21/EXP-25, les d\u00e9formations tactiques fluides sont d\u00e9crites par leurs coordonn\u00e9es continues (hauteur de ligne, largeur, profondeur) plut\u00f4t que par des \u00e9tiquettes de formation nominales (4-3-3 ou 4-4-2).\n- **TEAM_0** : La ligne d\u00e9fensive s'est positionn\u00e9e \u00e0 une hauteur moyenne mesur\u00e9e de 65.7m du but d\u00e9fendu, correspondant \u00e0 un bloc haut (sup\u00e9rieur \u00e0 la ligne m\u00e9diane) [source:team_summary/TEAM_0/defensive_line | cov=100% | conf=0.54].\n  La structure spatiale pr\u00e9sentait une profondeur moyenne de 24.7m, une largeur de 19.6m et une surface d'enveloppe convexe moyenne de 219.9m\u00b2 [source:team_summary/TEAM_0/compactness | conf=0.54].\n- **TEAM_1** : La ligne d\u00e9fensive s'est positionn\u00e9e \u00e0 une hauteur moyenne mesur\u00e9e de 22.6m du but d\u00e9fendu, correspondant \u00e0 un bloc bas [source:team_summary/TEAM_1/defensive_line | cov=100% | conf=0.55].\n  La structure spatiale pr\u00e9sentait une profondeur moyenne de 22.7m, une largeur de 15.4m et une surface d'enveloppe convexe moyenne de 135.9m\u00b2 [source:team_summary/TEAM_1/compactness | conf=0.55].\n\n## 4. PRESSION D\u00c9FENSIVE & HARC\u00c8LEMENT CONTINU\n> [!NOTE] Les indices de pression reposent sur les primitives continues de l'EXP-23 (proximit\u00e9, vitesse de fermeture g\u00e9om\u00e9trique et densit\u00e9 locale).\n- **TEAM_0** : Pression moyenne exerc\u00e9e de 0.264 (pic mesur\u00e9 \u00e0 0.775), avec 3 \u00e9pisodes de pression \u00e0 haute intensit\u00e9 document\u00e9s [source:team_summary/TEAM_0/pressure | conf=0.54].\n- **TEAM_1** : Pression moyenne exerc\u00e9e de 0.461 (pic mesur\u00e9 \u00e0 1.000), avec 3 \u00e9pisodes de pression \u00e0 haute intensit\u00e9 document\u00e9s [source:team_summary/TEAM_1/pressure | conf=0.55].\n\n## 5. TRANSITIONS APR\u00c8S PERTE DE BALLE & CANDIDATS CONTRE-PRESSING\n> [!CAUTION] Les d\u00e9tections de transitions (Niveau 3) sont des candidats diagnostiques qualifi\u00e9s par des heuristiques de physique du jeu. Elles ne constituent pas des annotations tactiques humaines ind\u00e9pendantes certifi\u00e9es.\n- **TEAM_0** : Apr\u00e8s perte de balle, les signaux physiques mesur\u00e9s sont compatibles avec un candidat de contre-pressing (score moyen : 0.529) et un indice de repli d\u00e9fensif de 0.194 [source:team_summary/TEAM_0/transitions | conf=0.54].\n- **TEAM_1** : Aucun \u00e9pisode de transition agressive post-perte significative n'a \u00e9t\u00e9 d\u00e9tect\u00e9 [source:team_summary/TEAM_1/transitions | conf=0.55].\n\n## 6. TRANSMISSIONS DE BALLE & DISPLACEMENTS OBSERV\u00c9S\n- **TEAM_0** : Transmissions de balle directes valid\u00e9es par filtrage qualit\u00e9 : 0 (d\u00e9placement longitudinal net : +0.0m) [source:team_summary/TEAM_0/ball_transfers | conf=0.54].\n- **TEAM_1** : Transmissions de balle directes valid\u00e9es par filtrage qualit\u00e9 : 0 (d\u00e9placement longitudinal net : +0.0m) [source:team_summary/TEAM_1/ball_transfers | conf=0.55].\n\n## 7. CHRONOLOGIE DES \u00c9V\u00c9NEMENTS PROBANTS CL\u00c9S\n- **2.08s \u2013 2.16s** (Fait physique) : TEAM_0 ball transfer completed (2.08\u20132.16s). Distance: 1.6m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_53_55_TEAM_0_PASS_INTERCEPTED | t=2.08s | conf=0.86 | HIGH]\n- **2.08s \u2013 9.68s** (Fait physique) : TEAM_1 applied continuous defensive pressure on TEAM_0 (2.08\u20139.68s, dur: 7.60s). Mean PressureIndex: 0.44 (peak: 0.76), min defender proximity: 0.5m. [event:press_53_243_TEAM_1 | t=2.08s | conf=0.44 | HIGH]\n- **2.16s \u2013 2.16s** (Fait physique) : TEAM_0 lost possession to TEAM_1 at 2.16s (frame 55). Possession confidence: 0.39 [LOW]. [event:poss_change_55_TEAM_0_to_TEAM_1 | t=2.16s | conf=0.39 | LOW]\n- **2.16s \u2013 3.20s** (Candidat qualifi\u00e9) : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (2.16\u20133.20s, \u0394t=1.04s). Nearest defender closed from 1.9m to 4.0m; PressureIndex changed from 0.08 to 0.26. CounterpressScore: 0.60 [Confidence: 0.60]. [event:trans_55_80_TEAM_0_COUNTERPRESS_CANDIDATE | t=2.16s | conf=0.60 | HIGH]\n- **7.80s \u2013 8.24s** (Fait physique) : TEAM_0 applied continuous defensive pressure on TEAM_1 (7.80\u20138.24s, dur: 0.44s). Mean PressureIndex: 0.37 (peak: 0.54), min defender proximity: 1.7m. [event:press_196_207_TEAM_0 | t=7.80s | conf=0.37 | HIGH]\n- **9.88s \u2013 11.44s** (Fait physique) : TEAM_1 applied continuous defensive pressure on TEAM_0 (9.88\u201311.44s, dur: 1.56s). Mean PressureIndex: 0.46 (peak: 0.66), min defender proximity: 1.4m. [event:press_248_287_TEAM_1 | t=9.88s | conf=0.46 | HIGH]\n- **10.20s \u2013 10.20s** (Fait physique) : TEAM_0 lost possession to TEAM_1 at 10.20s (frame 256). Possession confidence: 0.48 [HIGH]. [event:poss_change_256_TEAM_0_to_TEAM_1 | t=10.20s | conf=0.48 | HIGH]\n- **10.20s \u2013 10.76s** (Fait physique) : TEAM_0 applied continuous defensive pressure on TEAM_1 (10.20\u201310.76s, dur: 0.56s). Mean PressureIndex: 0.45 (peak: 0.64), min defender proximity: 1.4m. [event:press_256_270_TEAM_0 | t=10.20s | conf=0.45 | HIGH]\n- **10.20s \u2013 11.24s** (Candidat qualifi\u00e9) : Les signaux sont compatibles avec un candidat : TEAM_0 engaged in post-loss pressing against TEAM_1 (10.20\u201311.24s, \u0394t=1.04s). Nearest defender closed from 3.1m to 3.2m; PressureIndex changed from 0.21 to 0.29. CounterpressScore: 0.46 [Confidence: 0.45]. [event:trans_256_281_TEAM_0_NEUTRAL_TRANSITION | t=10.20s | conf=0.45 | HIGH]\n- **12.40s \u2013 13.96s** (Fait physique) : TEAM_1 applied continuous defensive pressure on TEAM_0 (12.40\u201313.96s, dur: 1.56s). Mean PressureIndex: 0.61 (peak: 1.00), min defender proximity: 0.2m. [event:press_311_350_TEAM_1 | t=12.40s | conf=0.61 | HIGH]\n- **12.92s \u2013 13.04s** (Fait physique) : TEAM_0 ball transfer completed (12.92\u201313.04s). Distance: 2.6m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_324_327_TEAM_0_PASS_INTERCEPTED | t=12.92s | conf=0.86 | HIGH]\n- **13.04s \u2013 13.04s** (Fait physique) : TEAM_0 lost possession to TEAM_1 at 13.04s (frame 327). Possession confidence: 0.93 [HIGH]. [event:poss_change_327_TEAM_0_to_TEAM_1 | t=13.04s | conf=0.93 | HIGH]\n- **13.04s \u2013 13.96s** (Fait physique) : TEAM_0 applied continuous defensive pressure on TEAM_1 (13.04\u201313.96s, dur: 0.92s). Mean PressureIndex: 0.66 (peak: 0.78), min defender proximity: 1.1m. [event:press_327_350_TEAM_0 | t=13.04s | conf=0.66 | HIGH]\n- **13.20s \u2013 13.60s** (Fait physique) : TEAM_1 ball transfer completed (13.20\u201313.60s). Distance: 3.4m, forward displacement: +0.0m [Confidence: 0.86]. [event:pass_331_341_TEAM_1_PASS_INTERCEPTED | t=13.20s | conf=0.86 | HIGH]\n- **13.60s \u2013 13.60s** (Fait physique) : TEAM_1 lost possession to TEAM_0 at 13.60s (frame 341). Possession confidence: 0.97 [HIGH]. [event:poss_change_341_TEAM_1_to_TEAM_0 | t=13.60s | conf=0.97 | HIGH]\n\n## 8. QUALIT\u00c9 DES DONN\u00c9ES & LIMITES M\u00c9THODOLOGIQUES\n- L'analyse est soumise \u00e0 la troncature du champ de vision propre aux retransmissions t\u00e9l\u00e9vis\u00e9es standard.\n- Les inf\u00e9rences de pressing et de transition restent des proxies physiques sans validation s\u00e9mantique humaine ind\u00e9pendante.\n- L'exactitude des cha\u00eenes de passes est d\u00e9pendante du bruit de tracking sur le porteur du ballon.\n\n**Avertissements sp\u00e9cifiques \u00e0 cette s\u00e9quence :**\n- Diagnostic candidate semantics; physics-derived GT evaluation\n- Downstream of pass detector baseline; precision limited by tracking flicker\n",
    qaExamples: [
    {
        "id": "fact_04",
        "category": "EXACT_FACT",
        "analysis_id": "SNMOT-069",
        "query": "Quelle \u00e9quipe a le ballon \u00e0 1.5s ?",
        "query_scope": "MATCH_COMPARISON",
        "confidence": 0.775,
        "answer": "### \ud83d\udcca Comparaison des \u00c9quipes (Agr\u00e9gats Vid\u00e9o)\n**\u00c9quipe TEAM_0** :\n- Possession contr\u00f4l\u00e9e : 52.3% (dur\u00e9e: 7.32s, pertes/gains: 4) *(couverture: 100%, conf: 0.65)*\n- Hauteur moyenne du bloc : 54.4m (profondeur: 18.7m, largeur: 19.9m)\n- Pression d\u00e9fensive : indice moyen 0.425 (pic: 0.852, \u00e9pisodes intenses: 4)\n- R\u00e9activit\u00e9 \u00e0 la perte (candidat contre-pressing) : indice moyen 0.423 *(diagnostic)*\n\n**\u00c9quipe TEAM_1** :\n- Possession contr\u00f4l\u00e9e : 26.0% (dur\u00e9e: 3.64s, pertes/gains: 2) *(couverture: 100%, conf: 0.63)*\n- Hauteur moyenne du bloc : 25.0m (profondeur: 21.9m, largeur: 19.1m)\n- Pression d\u00e9fensive : indice moyen 0.393 (pic: 0.940, \u00e9pisodes intenses: 2)\n- R\u00e9activit\u00e9 \u00e0 la perte (candidat contre-pressing) : indice moyen 0.443 *(diagnostic)*\n\n\n**Limites m\u00e9thodologiques :**\n- *Downstream of pass detector baseline; precision limited by tracking flicker*",
        "evidence_citations": [
            "[event:pass_48_49_TEAM_0_PASS_COMPLETED | t=1.88s | conf=0.78 | HIGH]"
        ],
        "knowledge_citations": [],
        "is_abstention": false
    }
]
  }
};
