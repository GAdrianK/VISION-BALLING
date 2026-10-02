"""Temporal Pitch Calibration and Homography Propagation Engine (EXP-14).

Propagates trusted keyframe football pitch calibrations through video frames
using sparse optical flow feature correspondences, dynamic confidence gating,
and explicit recalibration triggers while maintaining strict GPL isolation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import cv2
import numpy as np

try:
    from app.video_analysis.pitch_calibration import (
        PitchCalibrationResult,
        PitchDimensions,
        invert_homography,
    )
    from app.video_analysis.calibration_adapters import BaseCalibrationAdapter
except ImportError:
    from backend.app.video_analysis.pitch_calibration import (
        PitchCalibrationResult,
        PitchDimensions,
        invert_homography,
    )
    from backend.app.video_analysis.calibration_adapters import BaseCalibrationAdapter

logger = logging.getLogger(__name__)


class TemporalCalibrationState(str, Enum):
    """Lifecycle state of the current frame calibration."""

    CALIBRATED = "CALIBRATED"      # Fresh keyframe calibration (e.g. PnLCalib)
    PROPAGATED = "PROPAGATED"      # Temporal optical flow propagation from trusted state
    STALE = "STALE"                # Propagation age exceeded threshold; awaiting keyframe
    INVALID = "INVALID"            # Unreliable, uncalibrated, or degenerate geometry


class RecalibrationReason(str, Enum):
    """Reason triggering a new keyframe calibration."""

    NONE = "NONE"
    NO_INITIAL_CALIBRATION = "NO_INITIAL_CALIBRATION"
    MAX_AGE_EXCEEDED = "MAX_AGE_EXCEEDED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    INSUFFICIENT_FEATURES = "INSUFFICIENT_FEATURES"
    SCENE_CUT = "SCENE_CUT"
    IMPLAUSIBLE_GEOMETRY = "IMPLAUSIBLE_GEOMETRY"
    FORCED = "FORCED"


@dataclass
class TemporalCalibrationConfig:
    """Configuration parameters for temporal pitch calibration."""

    max_keyframe_interval: int = 10         # Maximum age before forcing recalibration (K cadence)
    min_features: int = 15                  # Minimum matched features for valid propagation
    min_inlier_ratio: float = 0.60          # Minimum RANSAC inlier ratio
    max_scene_displacement_px: float = 120.0 # Maximum frame-to-frame translation (scene cut check)
    max_scale_step: float = 0.15            # Maximum inter-frame zoom factor variation
    ransac_threshold_px: float = 3.0        # RANSAC reprojection error threshold
    feature_resolution: Tuple[int, int] = (960, 540) # Working resolution for optical flow
    max_corners: int = 150                  # Max features to track
    quality_level: float = 0.02             # Shi-Tomasi corner detection quality
    min_distance: float = 15.0              # Minimum pixel distance between tracked corners
    pitch_margin_m: float = 15.0            # Pitch boundary margin for coordinate validation
    mask_top_fraction: float = 0.08         # Exclude top broadcast scoreboard area
    mask_player_dilation_px: int = 10       # Exclusion dilation around player bboxes


@dataclass
class PlayerGroundProjection:
    """Structured downstream player / ball pitch projection record."""

    track_id: int
    frame_index: int
    timestamp: Optional[float]
    image_x: float
    image_y: float
    pitch_x_m: Optional[float]
    pitch_y_m: Optional[float]
    calibration_state: str
    calibration_age: int
    calibration_confidence: float
    is_valid_ground_point: bool
    is_inside_pitch: bool


@dataclass
class TemporalCalibrationResult(PitchCalibrationResult):
    """Result of temporal calibration for a specific frame."""

    state: TemporalCalibrationState = TemporalCalibrationState.INVALID
    calibration_age: int = 0
    last_calibration_frame: Optional[int] = None
    propagation_confidence: float = 0.0
    recalibration_reason: RecalibrationReason = RecalibrationReason.NONE
    inliers_count: int = 0
    matched_features_count: int = 0
    displacement_px: float = 0.0
    scale_step: float = 1.0


class TemporalPitchCalibrator:
    """Temporal pitch calibrator managing keyframe calibration and optical flow propagation."""

    def __init__(
        self,
        adapter: BaseCalibrationAdapter,
        config: Optional[TemporalCalibrationConfig] = None,
        pitch_dimensions: Optional[PitchDimensions] = None,
    ) -> None:
        self.adapter = adapter
        self.config = config or TemporalCalibrationConfig()
        self.pitch_dimensions = pitch_dimensions or PitchDimensions()

        # State memory
        self._last_trusted_result: Optional[TemporalCalibrationResult] = None
        self._current_homography_p2i: Optional[np.ndarray] = None
        self._current_homography_i2p: Optional[np.ndarray] = None
        self._prev_gray: Optional[np.ndarray] = None
        self._calibration_age: int = 0
        self._last_calibrated_frame: Optional[int] = None
        self._state: TemporalCalibrationState = TemporalCalibrationState.INVALID

    def reset(self) -> None:
        """Reset internal temporal tracker state."""
        self._last_trusted_result = None
        self._current_homography_p2i = None
        self._current_homography_i2p = None
        self._prev_gray = None
        self._calibration_age = 0
        self._last_calibrated_frame = None
        self._state = TemporalCalibrationState.INVALID

    @property
    def calibration_age(self) -> int:
        return self._calibration_age

    @property
    def state(self) -> TemporalCalibrationState:
        return self._state

    def update(
        self,
        frame_bgr_or_gray: np.ndarray,
        frame_index: int,
        timestamp: Optional[float] = None,
        player_bboxes: Optional[List[Union[List[float], Tuple[float, float, float, float]]]] = None,
        image_path: Optional[Union[str, Path]] = None,
    ) -> TemporalCalibrationResult:
        """Process current video frame and return calibrated or propagated pitch homography."""
        # Convert to grayscale at working resolution
        h_orig, w_orig = frame_bgr_or_gray.shape[:2]
        target_w, target_h = self.config.feature_resolution

        if len(frame_bgr_or_gray.shape) == 3:
            curr_gray_full = cv2.cvtColor(frame_bgr_or_gray, cv2.COLOR_BGR2GRAY)
        else:
            curr_gray_full = frame_bgr_or_gray

        if (w_orig, h_orig) != (target_w, target_h):
            curr_gray = cv2.resize(curr_gray_full, (target_w, target_h), interpolation=cv2.INTER_LINEAR)
        else:
            curr_gray = curr_gray_full

        # Determine recalibration necessity
        should_recalib, reason = self._check_recalibration_trigger(frame_index)

        # 1. Execute Keyframe Calibration if triggered
        if should_recalib:
            keyframe_result = self._execute_keyframe(
                frame_bgr_or_gray,
                frame_index,
                timestamp=timestamp,
                image_path=image_path,
            )
            if keyframe_result.valid and keyframe_result.homography_pitch_to_image is not None:
                # Successfully calibrated keyframe
                self._current_homography_p2i = keyframe_result.homography_pitch_to_image.copy()
                self._current_homography_i2p = keyframe_result.homography_image_to_pitch.copy()
                self._calibration_age = 0
                self._last_calibrated_frame = frame_index
                self._state = TemporalCalibrationState.CALIBRATED
                self._prev_gray = curr_gray.copy()

                res = TemporalCalibrationResult(
                    frame_index=frame_index,
                    timestamp=timestamp,
                    valid=True,
                    homography_image_to_pitch=self._current_homography_i2p,
                    homography_pitch_to_image=self._current_homography_p2i,
                    camera_parameters=keyframe_result.camera_parameters,
                    reprojection_error_px=keyframe_result.reprojection_error_px,
                    source_calibrator=self.adapter.__class__.__name__,
                    pitch_dimensions=self.pitch_dimensions,
                    state=TemporalCalibrationState.CALIBRATED,
                    calibration_age=0,
                    last_calibration_frame=frame_index,
                    propagation_confidence=1.0,
                    recalibration_reason=reason,
                )
                self._last_trusted_result = res
                return res

            logger.info("Keyframe calibration failed at frame %d (%s). Falling back to propagation.", frame_index, reason)

        # 2. Attempt Optical Flow Propagation from previous frame
        if self._prev_gray is not None and self._current_homography_p2i is not None:
            # Build exclusion mask (ignoring players and top scoreboards)
            scale_x = target_w / float(w_orig)
            scale_y = target_h / float(h_orig)
            feature_mask = self._build_feature_mask(target_w, target_h, player_bboxes, scale_x, scale_y)

            T_warp, prop_diag = self._estimate_interframe_motion(self._prev_gray, curr_gray, feature_mask)

            if T_warp is not None and prop_diag["is_confident"]:
                # Homography composition: H_p2i(t) = T_(t-1 -> t) @ H_p2i(t-1)
                new_H_p2i = T_warp @ self._current_homography_p2i
                new_H_i2p = invert_homography(new_H_p2i)

                # Plausibility check: center circle spot (0,0) must project within plausible image limits
                if new_H_i2p is not None and self._verify_projected_plausibility(new_H_p2i, w_orig, h_orig):
                    self._current_homography_p2i = new_H_p2i
                    self._current_homography_i2p = new_H_i2p
                    self._calibration_age += 1
                    self._state = (
                        TemporalCalibrationState.PROPAGATED
                        if self._calibration_age <= self.config.max_keyframe_interval
                        else TemporalCalibrationState.STALE
                    )
                    self._prev_gray = curr_gray.copy()

                    res = TemporalCalibrationResult(
                        frame_index=frame_index,
                        timestamp=timestamp,
                        valid=True,
                        homography_image_to_pitch=self._current_homography_i2p,
                        homography_pitch_to_image=self._current_homography_p2i,
                        camera_parameters=self._last_trusted_result.camera_parameters if self._last_trusted_result else None,
                        reprojection_error_px=self._last_trusted_result.reprojection_error_px if self._last_trusted_result else None,
                        source_calibrator="OpticalFlowPropagation",
                        pitch_dimensions=self.pitch_dimensions,
                        state=self._state,
                        calibration_age=self._calibration_age,
                        last_calibration_frame=self._last_calibrated_frame,
                        propagation_confidence=float(prop_diag["confidence"]),
                        recalibration_reason=reason if should_recalib else RecalibrationReason.NONE,
                        inliers_count=int(prop_diag.get("inliers_count", 0)),
                        matched_features_count=int(prop_diag.get("matched_count", 0)),
                        displacement_px=float(prop_diag.get("displacement_px", 0.0)),
                        scale_step=float(prop_diag.get("scale", 1.0)),
                    )
                    return res

        # 3. Propagation Failed -> Trigger Immediate Keyframe Recalibration Recovery
        recov_reason = (
            prop_diag.get("recalibration_reason", RecalibrationReason.SCENE_CUT)
            if (self._prev_gray is not None and self._current_homography_p2i is not None)
            else RecalibrationReason.INSUFFICIENT_FEATURES
        )
        recov_result = self._execute_keyframe(
            frame_bgr_or_gray,
            frame_index,
            timestamp=timestamp,
            image_path=image_path,
        )
        if recov_result.valid and recov_result.homography_pitch_to_image is not None:
            self._current_homography_p2i = recov_result.homography_pitch_to_image.copy()
            self._current_homography_i2p = recov_result.homography_image_to_pitch.copy()
            self._calibration_age = 0
            self._last_calibrated_frame = frame_index
            self._state = TemporalCalibrationState.CALIBRATED
            self._prev_gray = curr_gray.copy()
            res = TemporalCalibrationResult(
                frame_index=frame_index,
                timestamp=timestamp,
                valid=True,
                homography_image_to_pitch=self._current_homography_i2p,
                homography_pitch_to_image=self._current_homography_p2i,
                camera_parameters=recov_result.camera_parameters,
                reprojection_error_px=recov_result.reprojection_error_px,
                source_calibrator=self.adapter.__class__.__name__,
                pitch_dimensions=self.pitch_dimensions,
                state=TemporalCalibrationState.CALIBRATED,
                calibration_age=0,
                last_calibration_frame=frame_index,
                propagation_confidence=1.0,
                recalibration_reason=recov_reason,
            )
            self._last_trusted_result = res
            return res

        # 4. Total Failure: Neither Propagation nor Keyframe Recalibration Succeeded
        self._state = TemporalCalibrationState.INVALID
        self._prev_gray = curr_gray.copy()
        return TemporalCalibrationResult(
            frame_index=frame_index,
            timestamp=timestamp,
            valid=False,
            homography_image_to_pitch=None,
            homography_pitch_to_image=None,
            source_calibrator="Failed",
            pitch_dimensions=self.pitch_dimensions,
            state=TemporalCalibrationState.INVALID,
            calibration_age=self._calibration_age,
            last_calibration_frame=self._last_calibrated_frame,
            propagation_confidence=0.0,
            recalibration_reason=recov_reason,
        )

    def _check_recalibration_trigger(self, frame_index: int) -> Tuple[bool, RecalibrationReason]:
        """Evaluate explicit recalibration rules."""
        if self._last_calibrated_frame is None or self._current_homography_p2i is None:
            return True, RecalibrationReason.NO_INITIAL_CALIBRATION

        if self._calibration_age >= self.config.max_keyframe_interval:
            return True, RecalibrationReason.MAX_AGE_EXCEEDED

        if self._state == TemporalCalibrationState.INVALID:
            return True, RecalibrationReason.LOW_CONFIDENCE

        return False, RecalibrationReason.NONE

    def _execute_keyframe(
        self,
        frame: np.ndarray,
        frame_index: int,
        timestamp: Optional[float] = None,
        image_path: Optional[Union[str, Path]] = None,
    ) -> PitchCalibrationResult:
        """Call external calibration adapter on keyframe."""
        if image_path is not None and Path(image_path).exists():
            return self.adapter.calibrate_image(image_path, frame_index=frame_index, timestamp=timestamp)

        # Temporary file write if array given
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
            temp_path = tf.name
        try:
            cv2.imwrite(temp_path, frame)
            res = self.adapter.calibrate_image(temp_path, frame_index=frame_index, timestamp=timestamp)
            return res
        finally:
            if Path(temp_path).exists():
                Path(temp_path).unlink()

    def _build_feature_mask(
        self,
        w: int,
        h: int,
        player_bboxes: Optional[List[Any]],
        scale_x: float,
        scale_y: float,
    ) -> np.ndarray:
        """Construct tracking mask excluding banners, scoreboards, and moving players."""
        mask = np.zeros((h, w), dtype=np.uint8)
        # Include central field region, masking out top score banners and bottom tickers
        top_cut = int(h * self.config.mask_top_fraction)
        bottom_cut = int(h * 0.98)
        mask[top_cut:bottom_cut, :] = 255

        # Mask player bounding boxes
        if player_bboxes:
            pad = self.config.mask_player_dilation_px
            for bbox in player_bboxes:
                if len(bbox) >= 4:
                    bx1 = max(0, int(bbox[0] * scale_x) - pad)
                    by1 = max(0, int(bbox[1] * scale_y) - pad)
                    bx2 = min(w, int(bbox[2] * scale_x) + pad)
                    by2 = min(h, int(bbox[3] * scale_y) + pad)
                    mask[by1:by2, bx1:bx2] = 0

        return mask

    def _estimate_interframe_motion(
        self,
        prev_gray: np.ndarray,
        curr_gray: np.ndarray,
        mask: np.ndarray,
    ) -> Tuple[Optional[np.ndarray], Dict[str, Any]]:
        """Track features and compute RANSAC 3x3 planar transformation between frames."""
        corners = cv2.goodFeaturesToTrack(
            prev_gray,
            maxCorners=self.config.max_corners,
            qualityLevel=self.config.quality_level,
            minDistance=self.config.min_distance,
            mask=mask,
        )

        diag: Dict[str, Any] = {
            "matched_count": 0,
            "inliers_count": 0,
            "inlier_ratio": 0.0,
            "displacement_px": 0.0,
            "scale": 1.0,
            "confidence": 0.0,
            "is_confident": False,
        }

        if corners is None or len(corners) < self.config.min_features:
            return None, diag

        # Forward optical flow
        curr_pts, status, _ = cv2.calcOpticalFlowPyrLK(
            prev_gray, curr_gray, corners, None, winSize=(21, 21), maxLevel=3
        )
        if curr_pts is None or status is None:
            return None, diag

        valid = status.ravel() == 1
        p0 = corners[valid]
        p1 = curr_pts[valid]

        diag["matched_count"] = len(p0)
        if len(p0) < self.config.min_features:
            return None, diag

        # Robust RANSAC affine motion estimation
        affine_2x3, inliers = cv2.estimateAffinePartial2D(
            p0,
            p1,
            method=cv2.RANSAC,
            ransacReprojThreshold=self.config.ransac_threshold_px,
            maxIters=2000,
        )

        if affine_2x3 is None or inliers is None:
            return None, diag

        inliers_cnt = int(np.sum(inliers))
        inlier_ratio = inliers_cnt / float(len(p0))
        diag["inliers_count"] = inliers_cnt
        diag["inlier_ratio"] = inlier_ratio

        # Displacement and scale
        dx = float(affine_2x3[0, 2])
        dy = float(affine_2x3[1, 2])
        displacement = float(np.hypot(dx, dy))
        scale = float(np.sqrt(affine_2x3[0, 0] ** 2 + affine_2x3[0, 1] ** 2))

        diag["displacement_px"] = displacement
        diag["scale"] = scale

        # Scene cut / sudden camera jerk detection
        if displacement > self.config.max_scene_displacement_px:
            diag["recalibration_reason"] = RecalibrationReason.SCENE_CUT
            return None, diag

        if abs(scale - 1.0) > self.config.max_scale_step:
            diag["recalibration_reason"] = RecalibrationReason.LOW_CONFIDENCE
            return None, diag

        # Confidence metric
        confidence = float(np.clip(inlier_ratio * (min(inliers_cnt, 60) / 60.0), 0.0, 1.0))
        diag["confidence"] = confidence

        if inlier_ratio < self.config.min_inlier_ratio or inliers_cnt < self.config.min_features:
            return None, diag

        diag["is_confident"] = True

        # Convert 2x3 affine to 3x3 projective matrix
        T_3x3 = np.eye(3, dtype=np.float64)
        T_3x3[:2, :] = affine_2x3

        return T_3x3, diag

    def _verify_projected_plausibility(self, H_p2i: np.ndarray, w: int, h: int) -> bool:
        """Verify that canonical field center projects within plausible broadcast bounds."""
        center_mark_pitch = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        p = H_p2i @ center_mark_pitch
        if abs(p[2]) < 1e-6:
            return False
        u = p[0] / p[2]
        v = p[1] / p[2]
        # Center mark shouldn't fly infinitely far outside the broadcast frame
        return (-1000.0 <= u <= w + 1000.0) and (-1000.0 <= v <= h + 1000.0)

    def project_tracked_players(
        self,
        tracks_or_detections: List[Dict[str, Any]],
        calib_result: TemporalCalibrationResult,
    ) -> List[PlayerGroundProjection]:
        """Project player bounding boxes (bottom-center anchor) onto canonical pitch ground plane."""
        projections: List[PlayerGroundProjection] = []
        for item in tracks_or_detections:
            track_id = int(item.get("track_id", -1))
            bbox = item.get("bbox") or item.get("box")
            if not bbox or len(bbox) < 4:
                continue

            x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
            u_anchor = (x1 + x2) / 2.0
            v_anchor = y2

            pitch_pt = calib_result.image_to_pitch(u_anchor, v_anchor, check_bounds=False)
            if pitch_pt is not None:
                is_valid = True
                px, py = pitch_pt
                is_inside = self.pitch_dimensions.is_inside(px, py, margin_m=self.config.pitch_margin_m)
            else:
                is_valid = False
                px, py = None, None
                is_inside = False

            projections.append(
                PlayerGroundProjection(
                    track_id=track_id,
                    frame_index=calib_result.frame_index or 0,
                    timestamp=calib_result.timestamp,
                    image_x=u_anchor,
                    image_y=v_anchor,
                    pitch_x_m=px,
                    pitch_y_m=py,
                    calibration_state=calib_result.state.value,
                    calibration_age=calib_result.calibration_age,
                    calibration_confidence=calib_result.propagation_confidence,
                    is_valid_ground_point=is_valid,
                    is_inside_pitch=is_inside,
                )
            )
        return projections

    def project_tracked_ball(
        self,
        ball_bbox: Optional[Union[List[float], Tuple[float, float, float, float]]],
        calib_result: TemporalCalibrationResult,
        track_id: int = 0,
    ) -> Optional[PlayerGroundProjection]:
        """Project ball center anchor onto canonical pitch ground plane."""
        if ball_bbox is None or len(ball_bbox) < 4:
            return None

        x1, y1, x2, y2 = float(ball_bbox[0]), float(ball_bbox[1]), float(ball_bbox[2]), float(ball_bbox[3])
        u_center = (x1 + x2) / 2.0
        v_center = (y1 + y2) / 2.0

        pitch_pt = calib_result.image_to_pitch(u_center, v_center, check_bounds=False)
        if pitch_pt is not None:
            is_valid = True
            px, py = pitch_pt
            is_inside = self.pitch_dimensions.is_inside(px, py, margin_m=self.config.pitch_margin_m)
        else:
            is_valid = False
            px, py = None, None
            is_inside = False

        return PlayerGroundProjection(
            track_id=track_id,
            frame_index=calib_result.frame_index or 0,
            timestamp=calib_result.timestamp,
            image_x=u_center,
            image_y=v_center,
            pitch_x_m=px,
            pitch_y_m=py,
            calibration_state=calib_result.state.value,
            calibration_age=calib_result.calibration_age,
            calibration_confidence=calib_result.propagation_confidence,
            is_valid_ground_point=is_valid,
            is_inside_pitch=is_inside,
        )
