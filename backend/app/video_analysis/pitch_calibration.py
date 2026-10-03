"""Pitch Calibration Core Abstractions and Coordinate Conventions.

Provides canonical pitch geometry, calibration results, deterministic
coordinate transformations, and downstream player/ball ground projection.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np


@dataclass(frozen=True)
class PitchDimensions:
    """Canonical soccer pitch dimensions in meters.

    Default values follow FIFA standard recommendations: 105.0m x 68.0m.
    Coordinates origin is centered at the center mark (0, 0).
    X-axis: Longitudinal axis [-length/2, +length/2] (touchlines).
    Y-axis: Lateral axis [-width/2, +width/2] (goal lines).
    Z-axis: Vertical axis (0 at ground plane).
    """

    length_m: float = 105.0
    width_m: float = 68.0

    # FIFA standard sub-elements
    center_circle_radius_m: float = 9.15
    penalty_area_length_m: float = 16.50
    penalty_area_width_m: float = 40.32
    goal_area_length_m: float = 5.50
    goal_area_width_m: float = 18.32
    penalty_spot_distance_m: float = 11.00

    @property
    def x_min(self) -> float:
        return -self.length_m / 2.0

    @property
    def x_max(self) -> float:
        return self.length_m / 2.0

    @property
    def y_min(self) -> float:
        return -self.width_m / 2.0

    @property
    def y_max(self) -> float:
        return self.width_m / 2.0

    def is_inside(self, x: float, y: float, margin_m: float = 0.0) -> bool:
        """Check whether a point (x, y) in meters lies within pitch boundaries."""
        return (
            (self.x_min - margin_m) <= x <= (self.x_max + margin_m)
            and (self.y_min - margin_m) <= y <= (self.y_max + margin_m)
        )

    def get_canonical_pitch_lines(self) -> Dict[str, List[Tuple[float, float]]]:
        """Return canonical line segments in pitch coordinates (meters) for drawing."""
        half_l = self.length_m / 2.0
        half_w = self.width_m / 2.0
        pa_l = self.penalty_area_length_m
        pa_w = self.penalty_area_width_m / 2.0
        ga_l = self.goal_area_length_m
        ga_w = self.goal_area_width_m / 2.0

        return {
            # Perimeter
            "touchline_top": [(-half_l, -half_w), (half_l, -half_w)],
            "touchline_bottom": [(-half_l, half_w), (half_l, half_w)],
            "goalline_left": [(-half_l, -half_w), (-half_l, half_w)],
            "goalline_right": [(half_l, -half_w), (half_l, half_w)],
            "halfway_line": [(0.0, -half_w), (0.0, half_w)],
            # Left penalty area
            "penalty_left_top": [(-half_l, -pa_w), (-half_l + pa_l, -pa_w)],
            "penalty_left_front": [(-half_l + pa_l, -pa_w), (-half_l + pa_l, pa_w)],
            "penalty_left_bottom": [(-half_l + pa_l, pa_w), (-half_l, pa_w)],
            # Right penalty area
            "penalty_right_top": [(half_l, -pa_w), (half_l - pa_l, -pa_w)],
            "penalty_right_front": [(half_l - pa_l, -pa_w), (half_l - pa_l, pa_w)],
            "penalty_right_bottom": [(half_l - pa_l, pa_w), (half_l, pa_w)],
            # Left goal area
            "goal_area_left_top": [(-half_l, -ga_w), (-half_l + ga_l, -ga_w)],
            "goal_area_left_front": [(-half_l + ga_l, -ga_w), (-half_l + ga_l, ga_w)],
            "goal_area_left_bottom": [(-half_l + ga_l, ga_w), (-half_l, ga_w)],
            # Right goal area
            "goal_area_right_top": [(half_l, -ga_w), (half_l - ga_l, -ga_w)],
            "goal_area_right_front": [(half_l - ga_l, -ga_w), (half_l - ga_l, ga_w)],
            "goal_area_right_bottom": [(half_l - ga_l, ga_w), (half_l, ga_w)],
        }


def invert_homography(h_matrix: np.ndarray, rcond: float = 1e-12) -> Optional[np.ndarray]:
    """Invert a 3x3 homography matrix safely, checking determinant and condition number."""
    if h_matrix is None or h_matrix.shape != (3, 3):
        return None
    det = np.linalg.det(h_matrix)
    if not np.isfinite(det) or abs(det) < 1e-15:
        return None
    try:
        inv_h = np.linalg.inv(h_matrix)
        if not np.all(np.isfinite(inv_h)):
            return None
        # Normalize scale so that H[2, 2] == 1 if nonzero
        if abs(inv_h[2, 2]) > 1e-12:
            inv_h = inv_h / inv_h[2, 2]
        return inv_h
    except np.linalg.LinAlgError:
        return None


@dataclass
class PitchCalibrationResult:
    """Represents a unified camera calibration and pitch mapping result for a single frame.

    Standard convention:
    - homography_image_to_pitch: maps image pixel coordinates [u, v, 1]^T
      to 2D pitch coordinates [X, Y, 1]^T in meters (origin at center mark).
    - homography_pitch_to_image: inverse mapping from [X, Y, 1]^T to [u, v, 1]^T.
    """

    frame_index: Optional[int] = None
    timestamp: Optional[float] = None
    valid: bool = False
    homography_image_to_pitch: Optional[np.ndarray] = None
    homography_pitch_to_image: Optional[np.ndarray] = None
    camera_parameters: Optional[Dict[str, Any]] = None
    visible_pitch_elements: Optional[List[str]] = None
    confidence: Optional[float] = None
    reprojection_error_px: Optional[float] = None
    source_calibrator: str = ""
    pitch_dimensions: PitchDimensions = field(default_factory=PitchDimensions)

    def __post_init__(self) -> None:
        # Guarantee mutual consistency between H_img2pitch and H_pitch2img
        if self.valid:
            if self.homography_image_to_pitch is not None and self.homography_pitch_to_image is None:
                self.homography_pitch_to_image = invert_homography(self.homography_image_to_pitch)
            elif self.homography_pitch_to_image is not None and self.homography_image_to_pitch is None:
                self.homography_image_to_pitch = invert_homography(self.homography_pitch_to_image)

            if self.homography_image_to_pitch is None or self.homography_pitch_to_image is None:
                self.valid = False

    def image_to_pitch(
        self,
        u: float,
        v: float,
        check_bounds: bool = False,
        margin_m: float = 15.0,
    ) -> Optional[Tuple[float, float]]:
        """Transform image coordinates (u, v) in pixels to pitch coordinates (X, Y) in meters.

        Returns None if calibration is invalid, unprojectable, or outside bounds (if requested).
        """
        if not self.valid or self.homography_image_to_pitch is None:
            return None

        pt = np.array([float(u), float(v), 1.0], dtype=np.float64)
        p_proj = self.homography_image_to_pitch @ pt
        w = p_proj[2]

        if not np.isfinite(w) or abs(w) < 1e-9:
            return None

        x_m = float(p_proj[0] / w)
        y_m = float(p_proj[1] / w)

        if not (np.isfinite(x_m) and np.isfinite(y_m)):
            return None

        if check_bounds and not self.pitch_dimensions.is_inside(x_m, y_m, margin_m=margin_m):
            return None

        return (x_m, y_m)

    def pitch_to_image(
        self,
        x_m: float,
        y_m: float,
    ) -> Optional[Tuple[float, float]]:
        """Transform pitch coordinates (X, Y) in meters to image coordinates (u, v) in pixels.

        Returns None if calibration is invalid or point lies behind camera/at infinity.
        """
        if not self.valid or self.homography_pitch_to_image is None:
            return None

        pt = np.array([float(x_m), float(y_m), 1.0], dtype=np.float64)
        p_proj = self.homography_pitch_to_image @ pt
        w = p_proj[2]

        if not np.isfinite(w) or abs(w) < 1e-9:
            return None

        u = float(p_proj[0] / w)
        v = float(p_proj[1] / w)

        if not (np.isfinite(u) and np.isfinite(v)):
            return None

        return (u, v)

    def project_player_bbox(
        self,
        bbox: Union[List[float], Tuple[float, float, float, float]],
        check_bounds: bool = True,
        margin_m: float = 15.0,
    ) -> Optional[Tuple[float, float]]:
        """Project player bounding box to pitch ground plane (meters).

        Downstream projection anchor: bottom-center ((x1 + x2)/2, y2).
        Approximation: player ground contact is modeled by the bottom-center of the bbox.
        """
        if not self.valid:
            return None
        if len(bbox) < 4:
            return None
        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        if x2 <= x1 or y2 <= y1:
            return None

        u_anchor = (x1 + x2) / 2.0
        v_anchor = y2  # ground contact point

        return self.image_to_pitch(u_anchor, v_anchor, check_bounds=check_bounds, margin_m=margin_m)

    def project_ball_bbox(
        self,
        bbox: Union[List[float], Tuple[float, float, float, float]],
        check_bounds: bool = True,
        margin_m: float = 15.0,
    ) -> Optional[Tuple[float, float]]:
        """Project ball bounding box to pitch ground plane (meters).

        Downstream projection anchor: bbox center ((x1 + x2)/2, (y1 + y2)/2).
        Note: Ball may be airborne (Z > 0); this projects the ground plane intersection (Z = 0).
        """
        if not self.valid:
            return None
        if len(bbox) < 4:
            return None
        x1, y1, x2, y2 = float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])
        if x2 <= x1 or y2 <= y1:
            return None

        u_center = (x1 + x2) / 2.0
        v_center = (y1 + y2) / 2.0

        return self.image_to_pitch(u_center, v_center, check_bounds=check_bounds, margin_m=margin_m)
