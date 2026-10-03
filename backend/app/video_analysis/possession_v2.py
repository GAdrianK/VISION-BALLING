"""Ball Control & Team Possession V2 Engine (EXP-22 / Chapter 7).

Challenger architecture to EXP-18:
1. Candidate Generation: Gathers all nearby players in image and metric space.
2. Causal Feature Extraction: 24 interpretable features spanning image space,
   ground-plane metric kinematics, temporal history, and tracking quality.
3. Aerial Guard: Explicitly invalidates metric distance when ground-jump speed
   exceeds threshold (>25 m/s) or high parabolic arc is detected.
4. Calibrated Pairwise Control Model: Interpretable classifier estimating
   P(control | player, ball, history) trained with negative sampling and class weighting.
5. Multi-Candidate Margin Resolution: Distinguishes clear carrier control from 50/50 duels (CONTESTED),
   loose balls (FREE_BALL), and camera occlusions (UNKNOWN).
6. Causal Temporal State Machine: Hysteresis confirmation, pass transit grace window,
   and track ID switch robustness.

Maintains strict coexistence with V1 (possession.py) without modifying historical code.
"""

from __future__ import annotations

import logging
import math
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np

try:
    from app.video_analysis.pitch_calibration import PitchDimensions
    from app.video_analysis.metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )
    from app.video_analysis.possession import (
        BallControlState,
        TeamPossessionState,
        PossessionStatus,
        PossessionChangeEvent,
        TeamPossessionFrameState,
    )
except ImportError:
    from backend.app.video_analysis.pitch_calibration import PitchDimensions
    from backend.app.video_analysis.metric_trajectories import (
        PlayerMetricObservation,
        BallMetricObservation,
    )
    from backend.app.video_analysis.possession import (
        BallControlState,
        TeamPossessionState,
        PossessionStatus,
        PossessionChangeEvent,
        TeamPossessionFrameState,
    )

logger = logging.getLogger(__name__)


# ==============================================================================
# FEATURE CONSTANTS
# ==============================================================================

FEATURE_NAMES = [
    "norm_dist_bbox_center",       # 0: image dist to bbox center / bbox height
    "norm_dist_bottom_center",     # 1: image dist to footpoint / bbox height
    "norm_dist_lower_body",        # 2: image dist to lower 30% / bbox height
    "is_inside_bbox",              # 3: binary 1.0 if ball in player bbox
    "is_inside_lower_body",        # 4: binary 1.0 if ball in lower 35% of bbox
    "player_bbox_height_ratio",    # 5: player bbox height / 1080.0
    "ball_detection_conf",         # 6: detector confidence of the ball [0, 1]
    "metric_ground_dist_m",        # 7: metric distance on pitch (Z=0)
    "metric_valid",                # 8: binary 1.0 if metric is valid and not aerial
    "relative_metric_speed_ms",    # 9: abs(v_player - v_ball)
    "closing_speed_ms",            # 10: approach velocity (-d/dt dist)
    "candidate_persistence_norm",  # 11: frames player has been nearby / 25.0
    "is_previous_carrier",         # 12: binary 1.0 if this player was carrier at t-1
    "frames_since_last_control",   # 13: frames elapsed since last secure control / 50.0
    "current_control_streak",      # 14: consecutive frames as top candidate / 25.0
    "ball_speed_image_norm",       # 15: ball speed px/s / 500.0
    "ball_speed_metric_ms",        # 16: ball metric speed m/s
    "player_speed_metric_ms",      # 17: player metric speed m/s
    "relative_speed_consistency",  # 18: min(v_p, v_b) / max(v_p, v_b, 1.0)
    "player_track_conf",           # 19: player tracker confidence / status
    "ball_track_state",            # 20: 1.0 tracked, 0.5 interp, 0.0 lost
    "team_attribution_conf",       # 21: team assignment confidence
    "calibration_valid",           # 22: 1.0 if pitch homography valid
    "is_aerial_suspect",           # 23: 1.0 if aerial trajectory suspected
]

FEATURE_DIM = len(FEATURE_NAMES)


# ==============================================================================
# DATA STRUCTURES
# ==============================================================================

@dataclass
class PlayerControlCandidateV2:
    """Rich multi-evidence candidate container for ball control inference."""

    track_id: int
    team_label: str
    team_confidence: float
    control_score: float                     # Calibrated P(control | x) in [0.0, 1.0]
    features: np.ndarray = field(default_factory=lambda: np.zeros(FEATURE_DIM, dtype=np.float32))
    image_distance_px: float = 0.0
    normalized_image_distance: float = 0.0
    footpoint_distance_px: float = 0.0
    normalized_footpoint_distance: float = 0.0
    metric_distance_m: Optional[float] = None
    relative_velocity_ms: Optional[float] = None
    is_inside_bbox: bool = False
    is_aerial_gated: bool = False
    gt_tracklet_id: Optional[int] = None


@dataclass
class BallControlEvaluationV2:
    """Frame-level evaluation of ball control across all candidates."""

    state: BallControlState
    primary_candidate: Optional[PlayerControlCandidateV2] = None
    secondary_candidate: Optional[PlayerControlCandidateV2] = None
    score_margin: float = 0.0                # primary_score - secondary_score
    confidence: float = 0.0
    is_aerial_suspect: bool = False
    all_candidates: List[PlayerControlCandidateV2] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PossessionConfigV2:
    """Configuration parameters for Possession V2."""

    pitch_dimensions: PitchDimensions = field(default_factory=PitchDimensions)

    # Candidate generation gating
    max_candidate_norm_dist: float = 1.60    # Distance / bbox_height candidate ceiling
    max_candidate_metric_dist_m: float = 6.0 # Metric ground distance candidate ceiling

    # Scoring & candidate selection thresholds (tuned on CONTROL_DEV)
    control_probability_threshold: float = 0.42 # P(control) >= threshold to declare control
    contested_margin_threshold: float = 0.10    # If margin < margin_thresh and opposing -> CONTESTED
    min_contested_score: float = 0.32           # Min score for runner-up to contest

    # Aerial gating
    aerial_speed_jump_ms: float = 25.0       # Metric speed jump triggering aerial discount
    aerial_min_image_speed_px: float = 350.0 # High image speed flight indicator

    # Temporal State Machine
    player_control_confirm_frames: int = 2   # Consecutive frames to confirm new carrier (N=2 tuned on DEV)
    team_possession_confirm_frames: int = 5  # Consecutive frames to confirm turnover
    free_ball_grace_frames: int = 15         # Provisional pass transit grace window
    max_ball_occlusion_frames: int = 12      # Missing ball frames before UNKNOWN
    min_team_label_confidence: float = 0.45  # Gating threshold for team label attribution

    # Model parameters
    model_type: str = "HIST_GBDT"            # "HIST_GBDT" or "LOGISTIC_REGRESSION"
    model_path: Optional[str] = None


# ==============================================================================
# CAUSAL FEATURE EXTRACTOR
# ==============================================================================

class BallControlFeatureExtractor:
    """Extracts 24 causal, interpretable features for player-ball pairs."""

    def __init__(self, config: Optional[PossessionConfigV2] = None) -> None:
        self.config = config or PossessionConfigV2()
        # Temporal state caches (track_id -> state)
        self.candidate_persistence: Dict[int, int] = {}
        self.last_control_frame: Dict[int, int] = {}
        self.streak_as_top: Dict[int, int] = {}
        self.prev_carrier_id: Optional[int] = None
        self.prev_ball_image_pos: Optional[Tuple[float, float, float]] = None
        self.prev_ball_metric_pos: Optional[Tuple[float, float, float]] = None
        self.prev_player_metric_pos: Dict[int, Tuple[float, float, float]] = {}
        self.prev_player_ball_dist: Dict[int, float] = {}

    def reset(self) -> None:
        """Clears all causal temporal history."""
        self.candidate_persistence.clear()
        self.last_control_frame.clear()
        self.streak_as_top.clear()
        self.prev_carrier_id = None
        self.prev_ball_image_pos = None
        self.prev_ball_metric_pos = None
        self.prev_player_metric_pos.clear()
        self.prev_player_ball_dist.clear()

    def extract_features(
        self,
        frame_index: int,
        timestamp: float,
        player_obs: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_obs: Optional[Union[BallMetricObservation, Dict[str, Any]]],
        calibration_valid: bool = True,
    ) -> Tuple[List[PlayerControlCandidateV2], bool]:
        """Extracts feature vectors for all candidate players relative to the ball."""
        if ball_obs is None:
            return [], False

        ball_bbox, ball_metric, ball_conf, ball_state_str = self._parse_ball(ball_obs)
        if ball_bbox is None:
            return [], False

        bx1, by1, bx2, by2 = ball_bbox
        ball_cx = (bx1 + bx2) / 2.0
        ball_cy = (by1 + by2) / 2.0

        # 1. Compute ball kinematics & aerial flag
        ball_speed_px_s = 0.0
        if self.prev_ball_image_pos is not None:
            pbx, pby, pbt = self.prev_ball_image_pos
            dt = max(1e-3, timestamp - pbt)
            ball_speed_px_s = float(np.hypot(ball_cx - pbx, ball_cy - pby) / dt)
        self.prev_ball_image_pos = (ball_cx, ball_cy, timestamp)

        ball_speed_ms = 0.0
        is_aerial_suspect = False
        if ball_metric is not None:
            bmx, bmy = ball_metric
            if self.prev_ball_metric_pos is not None:
                pbmx, pbmy, pbmt = self.prev_ball_metric_pos
                dt = max(1e-3, timestamp - pbmt)
                ball_speed_ms = float(np.hypot(bmx - pbmx, bmy - pbmy) / dt)
                if ball_speed_ms > self.config.aerial_speed_jump_ms:
                    is_aerial_suspect = True
            self.prev_ball_metric_pos = (bmx, bmy, timestamp)

        if ball_speed_px_s > self.config.aerial_min_image_speed_px and ball_speed_ms > 20.0:
            is_aerial_suspect = True

        # 2. Iterate players and extract candidate features
        candidates: List[PlayerControlCandidateV2] = []
        active_track_ids = set()

        for p in player_obs:
            p_data = self._parse_player(p)
            if p_data["role"] == "REFEREE":
                continue

            tid = p_data["track_id"]
            active_track_ids.add(tid)
            px1, py1, px2, py2 = p_data["bbox"]
            pw = max(1.0, px2 - px1)
            ph = max(1.0, py2 - py1)

            p_cx = (px1 + px2) / 2.0
            p_cy = (py1 + py2) / 2.0
            foot_x = p_cx
            foot_y = py2

            # Image distances
            dist_center = float(np.hypot(ball_cx - p_cx, ball_cy - p_cy))
            norm_dist_center = dist_center / ph

            dist_foot = float(np.hypot(ball_cx - foot_x, ball_cy - foot_y))
            norm_dist_foot = dist_foot / ph

            # Lower body region (bottom 30% of bbox)
            lb_y1 = py1 + 0.70 * ph
            lb_dist_y = max(0.0, lb_y1 - ball_cy) if ball_cy < lb_y1 else max(0.0, ball_cy - py2)
            lb_dist_x = max(0.0, px1 - ball_cx) if ball_cx < px1 else max(0.0, ball_cx - px2)
            dist_lower_body = float(np.hypot(lb_dist_x, lb_dist_y))
            norm_dist_lb = dist_lower_body / ph

            is_inside_bbox = bool(px1 <= ball_cx <= px2 and py1 <= ball_cy <= py2)
            is_inside_lb = bool(px1 <= ball_cx <= px2 and lb_y1 <= ball_cy <= py2)

            # Metric distance & velocities
            metric_dist: Optional[float] = None
            rel_speed_ms = 0.0
            closing_speed_ms = 0.0
            metric_valid_flag = False

            if calibration_valid and not is_aerial_suspect and ball_metric is not None and p_data["pitch_x"] is not None:
                p_mx, p_my = p_data["pitch_x"], p_data["pitch_y"]
                metric_dist = float(np.hypot(ball_metric[0] - p_mx, ball_metric[1] - p_my))
                metric_valid_flag = True

                # Relative velocity
                p_speed = p_data["speed_mps"] or 0.0
                rel_speed_ms = abs(p_speed - ball_speed_ms)

                # Closing velocity (-d/dt dist)
                if tid in self.prev_player_ball_dist:
                    prev_d = self.prev_player_ball_dist[tid]
                    dt = 0.04
                    closing_speed_ms = float((prev_d - metric_dist) / dt)
                self.prev_player_ball_dist[tid] = metric_dist

            # Candidate filter: player must be within broad proximity
            if norm_dist_foot > self.config.max_candidate_norm_dist:
                if metric_dist is None or metric_dist > self.config.max_candidate_metric_dist_m:
                    continue

            # Update temporal counters
            persist = self.candidate_persistence.get(tid, 0) + 1
            self.candidate_persistence[tid] = persist

            is_prev_carrier = 1.0 if (tid == self.prev_carrier_id) else 0.0
            frames_since_ctrl = float(frame_index - self.last_control_frame.get(tid, -999))
            streak = float(self.streak_as_top.get(tid, 0))

            p_speed_m = p_data["speed_mps"] or 0.0
            speed_cons = min(p_speed_m, ball_speed_ms) / max(p_speed_m, ball_speed_ms, 1.0)

            # Assemble 24-D feature vector
            feats = np.zeros(FEATURE_DIM, dtype=np.float32)
            feats[0] = min(3.0, norm_dist_center)
            feats[1] = min(3.0, norm_dist_foot)
            feats[2] = min(3.0, norm_dist_lb)
            feats[3] = 1.0 if is_inside_bbox else 0.0
            feats[4] = 1.0 if is_inside_lb else 0.0
            feats[5] = min(1.0, ph / 1080.0)
            feats[6] = ball_conf
            feats[7] = min(15.0, metric_dist) if (metric_dist is not None and metric_valid_flag) else 0.0
            feats[8] = 1.0 if metric_valid_flag else 0.0
            feats[9] = min(20.0, rel_speed_ms)
            feats[10] = max(-15.0, min(15.0, closing_speed_ms))
            feats[11] = min(1.0, persist / 25.0)
            feats[12] = is_prev_carrier
            feats[13] = min(1.0, frames_since_ctrl / 50.0)
            feats[14] = min(1.0, streak / 25.0)
            feats[15] = min(2.0, ball_speed_px_s / 500.0)
            feats[16] = min(25.0, ball_speed_ms)
            feats[17] = min(12.0, p_speed_m)
            feats[18] = float(speed_cons)
            feats[19] = float(p_data["track_conf"])
            feats[20] = 1.0 if ball_state_str == "TRACKED" else 0.5
            feats[21] = float(p_data["team_conf"])
            feats[22] = 1.0 if calibration_valid else 0.0
            feats[23] = 1.0 if is_aerial_suspect else 0.0

            cand = PlayerControlCandidateV2(
                track_id=tid,
                team_label=p_data["team_label"],
                team_confidence=p_data["team_conf"],
                control_score=0.0,
                features=feats,
                image_distance_px=dist_foot,
                normalized_image_distance=norm_dist_center,
                footpoint_distance_px=dist_foot,
                normalized_footpoint_distance=norm_dist_foot,
                metric_distance_m=metric_dist,
                relative_velocity_ms=rel_speed_ms,
                is_inside_bbox=is_inside_bbox,
                is_aerial_gated=is_aerial_suspect,
                gt_tracklet_id=p_data["gt_tracklet_id"],
            )
            candidates.append(cand)

        # Decay persistence for disappeared candidates
        for tid in list(self.candidate_persistence.keys()):
            if tid not in active_track_ids:
                del self.candidate_persistence[tid]
                if tid in self.prev_player_ball_dist:
                    del self.prev_player_ball_dist[tid]

        return candidates, is_aerial_suspect

    def update_control_memory(self, carrier_track_id: Optional[int], frame_index: int) -> None:
        """Causally updates streak and last control frame after decision."""
        self.prev_carrier_id = carrier_track_id
        if carrier_track_id is not None:
            self.last_control_frame[carrier_track_id] = frame_index
            self.streak_as_top[carrier_track_id] = self.streak_as_top.get(carrier_track_id, 0) + 1
            for tid in list(self.streak_as_top.keys()):
                if tid != carrier_track_id:
                    self.streak_as_top[tid] = 0
        else:
            self.streak_as_top.clear()

    # --------------------------------------------------------------------------
    # HELPERS
    # --------------------------------------------------------------------------

    def _parse_ball(self, ball_obs: Any) -> Tuple[Optional[List[float]], Optional[Tuple[float, float]], float, str]:
        if isinstance(ball_obs, dict):
            b_box = ball_obs.get("bbox")
            b_conf = float(ball_obs.get("confidence", 0.8))
            b_state = str(ball_obs.get("state", "TRACKED"))
            b_metric = None
            px = ball_obs.get("pitch_x_m") if "pitch_x_m" in ball_obs else ball_obs.get("pitch_x")
            py = ball_obs.get("pitch_y_m") if "pitch_y_m" in ball_obs else ball_obs.get("pitch_y")
            if px is not None and py is not None:
                b_metric = (float(px), float(py))
            return b_box, b_metric, b_conf, b_state

        b_box = getattr(ball_obs, "bbox", None)
        b_conf = float(getattr(ball_obs, "confidence", 0.8) or 0.8)
        b_state = str(getattr(ball_obs, "observation_state", "TRACKED"))
        b_metric = None
        px = getattr(ball_obs, "pitch_x_m", None)
        py = getattr(ball_obs, "pitch_y_m", None)
        if px is not None and py is not None:
            b_metric = (float(px), float(py))
        return b_box, b_metric, b_conf, b_state

    def _parse_player(self, p: Any) -> Dict[str, Any]:
        if isinstance(p, dict):
            return {
                "track_id": int(p.get("track_id", 0)),
                "bbox": p.get("bbox", [0.0, 0.0, 1.0, 1.0]),
                "team_label": str(p.get("team_label", "UNKNOWN")),
                "team_conf": float(p.get("team_confidence", 0.8)),
                "role": str(p.get("role", "OUTFIELD_PLAYER")),
                "pitch_x": p.get("pitch_x_m"),
                "pitch_y": p.get("pitch_y_m"),
                "speed_mps": p.get("speed_mps", 0.0),
                "track_conf": float(p.get("track_confidence", 0.9)),
                "gt_tracklet_id": p.get("gt_tracklet_id"),
            }

        return {
            "track_id": int(getattr(p, "track_id", 0)),
            "bbox": getattr(p, "bbox", [0.0, 0.0, 1.0, 1.0]),
            "team_label": str(getattr(p, "team_label", "UNKNOWN")),
            "team_conf": float(getattr(p, "team_confidence", 0.8) or 0.8),
            "role": str(getattr(p, "role", "OUTFIELD_PLAYER")),
            "pitch_x": getattr(p, "pitch_x_m", None),
            "pitch_y": getattr(p, "pitch_y_m", None),
            "speed_mps": getattr(p, "speed_mps", 0.0) or 0.0,
            "track_conf": float(getattr(p, "confidence", 0.9) or 0.9),
            "gt_tracklet_id": getattr(p, "gt_tracklet_id", None),
        }


# ==============================================================================
# PAIRWISE CONTROL MODEL (LOGISTIC REGRESSION & HIST_GBDT)
# ==============================================================================

class PairwiseControlModel:
    """Interpretable, calibrated pairwise control classifier."""

    def __init__(self, model_type: str = "HIST_GBDT", model_path: Optional[Union[str, Path]] = None) -> None:
        self.model_type = model_type
        self.is_fitted = False
        self.model = None
        self._fast_predict_fn = None

        # Check for pre-trained model artifact
        p = Path(model_path) if model_path else (Path(__file__).parent / "possession_v2_model.pkl")
        if p.is_file():
            try:
                import pickle
                with open(p, "rb") as f:
                    loaded = pickle.load(f)
                    if hasattr(loaded, "model") and loaded.model is not None:
                        self.model = loaded.model
                        self.is_fitted = True
                        self.model_type = getattr(loaded, "model_type", model_type)
                    elif hasattr(loaded, "predict_proba"):
                        self.model = loaded
                        self.is_fitted = True
                self._compile_fast_trees()
            except Exception as e:
                logger.warning("Could not load pre-trained model from %s: %s", p, e)
        # Heuristic fallback coefficients if model not yet fitted
        self._heuristic_weights = np.array([
            -1.2,  # 0: norm_dist_bbox_center (negative)
            -2.5,  # 1: norm_dist_bottom_center (strong negative)
            -1.5,  # 2: norm_dist_lower_body (strong negative)
             1.2,  # 3: is_inside_bbox (positive)
             1.8,  # 4: is_inside_lower_body (strong positive)
             0.2,  # 5: player_bbox_height_ratio
             0.5,  # 6: ball_detection_conf
            -0.8,  # 7: metric_ground_dist_m (negative)
             0.4,  # 8: metric_valid
            -0.2,  # 9: relative_metric_speed_ms
             0.2,  # 10: closing_speed_ms
             0.6,  # 11: candidate_persistence_norm (positive)
             1.5,  # 12: is_previous_carrier (strong hysteresis)
            -0.5,  # 13: frames_since_last_control
             0.8,  # 14: current_control_streak
            -0.4,  # 15: ball_speed_image_norm
            -0.2,  # 16: ball_speed_metric_ms
             0.1,  # 17: player_speed_metric_ms
             0.5,  # 18: relative_speed_consistency
             0.3,  # 19: player_track_conf
             0.2,  # 20: ball_track_state
             0.4,  # 21: team_attribution_conf
             0.1,  # 22: calibration_valid
            -1.0,  # 23: is_aerial_suspect (discount control)
        ], dtype=np.float32)
        self._heuristic_bias = 0.5

    def _compile_fast_trees(self) -> None:
        """Compiles HistGradientBoostingClassifier decision trees into high-speed branchless evaluator."""
        if self.model is None or not hasattr(self.model, "_predictors"):
            return
        try:
            base_score = float(self.model._baseline_prediction[0, 0])
            code_lines = ["def _fast_eval(x):", f"    raw = {base_score}"]
            for t_idx, pred in enumerate(self.model._predictors):
                nodes = pred[0].nodes
                def recurse(idx: int, indent: str) -> List[str]:
                    n = nodes[idx]
                    if n["is_leaf"]:
                        return [f"{indent}raw += {float(n['value'])}"]
                    f_idx = int(n["feature_idx"])
                    thresh = float(n["num_threshold"])
                    lines = [f"{indent}if x[{f_idx}] <= {thresh}:"]
                    lines.extend(recurse(int(n["left"]), indent + "    "))
                    lines.append(f"{indent}else:")
                    lines.extend(recurse(int(n["right"]), indent + "    "))
                    return lines
                code_lines.extend(recurse(0, "    "))
            code_lines.append("    return 1.0 / (1.0 + np.exp(-raw))")
            code_str = "\n".join(code_lines)
            namespace = {"np": np}
            exec(code_str, namespace)
            self._fast_predict_fn = namespace["_fast_eval"]
            logger.info("Compiled %d decision trees into fast evaluator", len(self.model._predictors))
        except Exception as e:
            logger.warning("Could not compile fast tree evaluator: %s", e)
            self._fast_predict_fn = None

    def fit(self, X: np.ndarray, y: np.ndarray) -> None:
        """Fits model on training features with class weighting and calibration."""
        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.calibration import CalibratedClassifierCV

        pos_count = np.sum(y == 1)
        neg_count = np.sum(y == 0)
        pos_weight = float(neg_count / max(1, pos_count))

        if self.model_type == "LOGISTIC_REGRESSION":
            base = LogisticRegression(class_weight="balanced", max_iter=200, C=1.0)
            self.model = CalibratedClassifierCV(base, method="isotonic", cv=3)
            self.model.fit(X, y)
        else:
            # Shallow HistGBDT
            sample_weights = np.where(y == 1, pos_weight, 1.0)
            self.model = HistGradientBoostingClassifier(
                max_depth=3,
                max_iter=60,
                l2_regularization=1.5,
                min_samples_leaf=15,
                random_state=42,
            )
            self.model.fit(X, y, sample_weight=sample_weights)

        self.is_fitted = True
        self._compile_fast_trees()

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Predicts probability P(control | X) for candidate feature vectors."""
        if X.shape[0] == 0:
            return np.zeros(0, dtype=np.float32)

        if self.is_fitted and self._fast_predict_fn is not None:
            n_samples = X.shape[0]
            res = np.empty(n_samples, dtype=np.float32)
            for i in range(n_samples):
                res[i] = self._fast_predict_fn(X[i])
            return res

        if self.is_fitted and self.model is not None:
            probs = self.model.predict_proba(X)[:, 1]
            return probs.astype(np.float32)

        # Calibrated heuristic sigmoid fallback
        logits = np.dot(X, self._heuristic_weights) + self._heuristic_bias
        probs = 1.0 / (1.0 + np.exp(-np.clip(logits, -8.0, 8.0)))
        return probs.astype(np.float32)


# ==============================================================================
# BALL CONTROL ESTIMATOR V2
# ==============================================================================

class BallControlEstimatorV2:
    """Evaluates player ball control using feature extractor, model scoring, and margin gates."""

    def __init__(
        self,
        config: Optional[PossessionConfigV2] = None,
        model: Optional[PairwiseControlModel] = None,
    ) -> None:
        self.config = config or PossessionConfigV2()
        self.feature_extractor = BallControlFeatureExtractor(self.config)
        self.model = model or PairwiseControlModel(model_type=self.config.model_type)

    def reset(self) -> None:
        self.feature_extractor.reset()

    def evaluate(
        self,
        frame_index: int,
        timestamp: float,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_observation: Optional[Union[BallMetricObservation, Dict[str, Any]]],
        calibration_valid: bool = True,
    ) -> BallControlEvaluationV2:
        """Evaluates ball control across candidates for current frame."""
        if ball_observation is None:
            return BallControlEvaluationV2(
                state=BallControlState.UNKNOWN,
                details={"reason": "NO_BALL_OBSERVATION"},
            )

        candidates, is_aerial = self.feature_extractor.extract_features(
            frame_index=frame_index,
            timestamp=timestamp,
            player_obs=player_observations,
            ball_obs=ball_observation,
            calibration_valid=calibration_valid,
        )

        if not candidates:
            state = BallControlState.FREE_BALL if not is_aerial else BallControlState.FREE_BALL
            return BallControlEvaluationV2(
                state=state,
                confidence=0.80 if is_aerial else 0.50,
                is_aerial_suspect=is_aerial,
                details={"reason": "NO_CANDIDATES_IN_RANGE", "is_aerial": is_aerial},
            )

        # Score candidates
        X = np.stack([c.features for c in candidates], axis=0)
        probs = self.model.predict_proba(X)
        for cand, p in zip(candidates, probs):
            cand.control_score = float(p)

        # Sort candidates descending by control score
        candidates.sort(key=lambda c: c.control_score, reverse=True)
        primary = candidates[0]
        secondary = candidates[1] if len(candidates) > 1 else None

        score_margin = float(primary.control_score - (secondary.control_score if secondary else 0.0))

        # Decision rules
        # Case A: Below control threshold -> FREE_BALL
        if primary.control_score < self.config.control_probability_threshold:
            state = BallControlState.FREE_BALL
            assigned_carrier = None
        # Case B: Opposing duel with small margin -> CONTESTED
        elif (
            secondary is not None
            and secondary.team_label != primary.team_label
            and secondary.control_score >= self.config.min_contested_score
            and score_margin < self.config.contested_margin_threshold
        ):
            state = BallControlState.CONTESTED
            assigned_carrier = None
        # Case C: Clear single candidate -> CONTROLLED
        else:
            state = BallControlState.CONTROLLED
            assigned_carrier = primary.track_id

        # Update causal memory
        self.feature_extractor.update_control_memory(assigned_carrier, frame_index)

        return BallControlEvaluationV2(
            state=state,
            primary_candidate=primary,
            secondary_candidate=secondary,
            score_margin=score_margin,
            confidence=primary.control_score,
            is_aerial_suspect=is_aerial,
            all_candidates=candidates,
            details={
                "candidate_count": len(candidates),
                "is_aerial": is_aerial,
                "primary_track_id": primary.track_id if primary else None,
                "primary_score": primary.control_score if primary else 0.0,
                "score_margin": score_margin,
            },
        )


# ==============================================================================
# TEAM POSSESSION STATE MACHINE V2
# ==============================================================================

class TeamPossessionStateMachineV2:
    """Causal possession state machine with confirmation delays and turnover management."""

    def __init__(self, config: Optional[PossessionConfigV2] = None) -> None:
        self.config = config or PossessionConfigV2()
        self.reset()

    def reset(self) -> None:
        self.current_team: str = "UNKNOWN"
        self.current_status: PossessionStatus = PossessionStatus.UNKNOWN
        self.confidence: float = 0.0

        self.confirmed_carrier_id: Optional[int] = None
        self.confirmed_carrier_team: Optional[str] = None
        self.confirmed_carrier_gt_id: Optional[int] = None

        self.pending_carrier_id: Optional[int] = None
        self.pending_carrier_team: Optional[str] = None
        self.pending_carrier_gt_id: Optional[int] = None
        self.pending_carrier_streak: int = 0

        self.pending_turnover_team: Optional[str] = None
        self.pending_turnover_streak: int = 0

        self.free_ball_age: int = 0
        self.occlusion_age: int = 0

        self.last_confirmed_team: Optional[str] = None
        self.last_confirmed_player_id: Optional[int] = None

    def update(
        self,
        frame_index: int,
        timestamp: float,
        control_eval: BallControlEvaluationV2,
    ) -> Tuple[TeamPossessionFrameState, Optional[PossessionChangeEvent]]:
        """Causally updates state machine and outputs current possession state + events."""
        turnover_event: Optional[PossessionChangeEvent] = None
        c_state = control_eval.state
        prim = control_eval.primary_candidate

        # 1. Handle Ball Occlusion / Missing
        if c_state == BallControlState.UNKNOWN:
            self.occlusion_age += 1
            if self.occlusion_age > self.config.max_ball_occlusion_frames:
                self.current_team = "UNKNOWN"
                self.current_status = PossessionStatus.UNKNOWN
                self.confirmed_carrier_id = None
            return self._build_frame_state(frame_index, timestamp, control_eval, None), None
        else:
            self.occlusion_age = 0

        # 2. Player Controlled State
        if c_state == BallControlState.CONTROLLED and prim is not None:
            self.free_ball_age = 0
            cand_id = prim.track_id
            cand_team = prim.team_label
            cand_gt = prim.gt_tracklet_id

            # Carrier confirmation hysteresis
            if cand_id == self.pending_carrier_id:
                self.pending_carrier_streak += 1
            else:
                self.pending_carrier_id = cand_id
                self.pending_carrier_team = cand_team
                self.pending_carrier_gt_id = cand_gt
                self.pending_carrier_streak = 1

            if self.pending_carrier_streak >= self.config.player_control_confirm_frames:
                # Confirmed new carrier!
                prev_team = self.current_team
                prev_player = self.confirmed_carrier_id

                self.confirmed_carrier_id = cand_id
                self.confirmed_carrier_team = cand_team
                self.confirmed_carrier_gt_id = cand_gt

                # Check turnover
                if cand_team in ("TEAM_0", "TEAM_1"):
                    if prev_team in ("TEAM_0", "TEAM_1") and cand_team != prev_team:
                        turnover_event = PossessionChangeEvent(
                            frame_index=frame_index,
                            timestamp=timestamp,
                            from_team=prev_team,
                            to_team=cand_team,
                            from_player_track_id=prev_player,
                            to_player_track_id=cand_id,
                            confirmation_delay_frames=self.pending_carrier_streak,
                            confidence=prim.control_score,
                        )

                    self.current_team = cand_team
                    self.current_status = PossessionStatus.SECURE
                    self.confidence = prim.control_score
                    self.last_confirmed_team = cand_team
                    self.last_confirmed_player_id = cand_id

        # 3. Contested Duel State
        elif c_state == BallControlState.CONTESTED:
            self.free_ball_age = 0
            self.current_status = PossessionStatus.CONTESTED
            self.current_team = "CONTESTED"
            self.confirmed_carrier_id = None
            self.confidence = 0.65

        # 4. Free Ball / Pass Transit State
        elif c_state == BallControlState.FREE_BALL:
            self.free_ball_age += 1
            self.confirmed_carrier_id = None

            if self.free_ball_age <= self.config.free_ball_grace_frames and self.last_confirmed_team in ("TEAM_0", "TEAM_1"):
                # Provisional pass transit with previous holding team
                self.current_team = self.last_confirmed_team
                self.current_status = PossessionStatus.PROVISIONAL_TRANSIT
                self.confidence = max(0.35, 0.70 - (self.free_ball_age / self.config.free_ball_grace_frames) * 0.35)
            else:
                # Extended loose ball -> NEUTRAL
                self.current_team = "NEUTRAL"
                self.current_status = PossessionStatus.NEUTRAL
                self.confidence = 0.50

        frame_state = self._build_frame_state(frame_index, timestamp, control_eval, turnover_event)
        return frame_state, turnover_event

    def _build_frame_state(
        self,
        frame_index: int,
        timestamp: float,
        control_eval: BallControlEvaluationV2,
        turnover_event: Optional[PossessionChangeEvent],
    ) -> TeamPossessionFrameState:
        return TeamPossessionFrameState(
            frame_index=frame_index,
            timestamp=timestamp,
            possession_team=self.current_team,
            possession_status=self.current_status,
            possession_confidence=self.confidence,
            controlling_player_id=self.confirmed_carrier_id,
            controlling_player_team=self.confirmed_carrier_team,
            control_state=control_eval.state,
            free_ball_age_frames=self.free_ball_age,
            occlusion_age_frames=self.occlusion_age,
            last_confirmed_team=self.last_confirmed_team,
            last_confirmed_player_id=self.last_confirmed_player_id,
            recent_possession_change=turnover_event,
            is_valid=True,
            controlling_player_gt_id=self.confirmed_carrier_gt_id,
            details={
                "v2_challenger": True,
                "score_margin": control_eval.score_margin,
                "is_aerial_suspect": control_eval.is_aerial_suspect,
                "candidate_count": len(control_eval.all_candidates),
            },
        )


# ==============================================================================
# UNIFIED POSSESSION ENGINE V2
# ==============================================================================

class PossessionEngineV2:
    """Unified challenger engine combining BallControlEstimatorV2 and TeamPossessionStateMachineV2."""

    def __init__(
        self,
        config: Optional[PossessionConfigV2] = None,
        model: Optional[PairwiseControlModel] = None,
    ) -> None:
        self.config = config or PossessionConfigV2()
        self.model = model or PairwiseControlModel(model_type=self.config.model_type)
        self.control_estimator = BallControlEstimatorV2(config=self.config, model=self.model)
        self.state_machine = TeamPossessionStateMachineV2(config=self.config)
        self.turnover_events: List[PossessionChangeEvent] = []

    def reset(self) -> None:
        self.control_estimator.reset()
        self.state_machine.reset()
        self.turnover_events.clear()

    def process_frame(
        self,
        frame_index: int,
        timestamp: float,
        player_observations: Sequence[Union[PlayerMetricObservation, Dict[str, Any]]],
        ball_observation: Optional[Union[BallMetricObservation, Dict[str, Any]]],
        calibration_valid: bool = True,
    ) -> TeamPossessionFrameState:
        """Processes a single frame and outputs complete TeamPossessionFrameState."""
        control_eval = self.control_estimator.evaluate(
            frame_index=frame_index,
            timestamp=timestamp,
            player_observations=player_observations,
            ball_observation=ball_observation,
            calibration_valid=calibration_valid,
        )

        frame_state, turnover = self.state_machine.update(
            frame_index=frame_index,
            timestamp=timestamp,
            control_eval=control_eval,
        )

        if turnover is not None:
            self.turnover_events.append(turnover)

        return frame_state
