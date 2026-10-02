"""
Chapter 6A: Team & Role Attribution Module (EXP-12).
Provides unsupervised track-level team classification, player role separation
(outfield player, goalkeeper, referee), and quality-filtered crop aggregation.

Strict Isolation Guarantees:
  - Zero ground-truth team or role metadata enters inference.
  - Zero modification to tracker identity (tracker IDs are strictly immutable).
  - Unsupervised neutral cluster labels (TEAM_0, TEAM_1).
  - Operates primarily at TRACK level over accumulated evidence.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Sequence

import cv2
import numpy as np
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture

from app.video_analysis.reid_encoder import (
    EMBEDDING_DIM,
    PlayerAppearanceEncoder,
    extract_player_crop,
)


class RoleType(str, Enum):
    OUTFIELD_PLAYER = "OUTFIELD_PLAYER"
    GOALKEEPER = "GOALKEEPER"
    REFEREE = "REFEREE"
    UNKNOWN = "UNKNOWN"


class TeamLabel(str, Enum):
    TEAM_0 = "TEAM_0"
    TEAM_1 = "TEAM_1"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class CropQualityFilterConfig:
    """Thresholds for filtering noisy or corrupt player crops."""
    min_bbox_height: float = 40.0
    min_bbox_width: float = 15.0
    min_aspect_ratio: float = 1.2
    max_aspect_ratio: float = 4.5
    min_sharpness: float = 25.0  # Laplacian variance threshold
    max_overlap_iou: float = 0.20  # IoU with other detected players
    boundary_margin_px: float = 2.0


@dataclass(frozen=True)
class TeamClassifierConfig:
    """Configuration for track-level team and role attribution."""
    method: str = "kmeans"  # "kmeans" or "gmm"
    feature_type: str = "hsv_hist"  # "hsv_hist", "lab_hist", "reid", "fused"
    min_evidence_crops: int = 3
    max_crops_per_track: int = 25
    hsv_h_bins: int = 16
    hsv_s_bins: int = 8
    hsv_v_bins: int = 8
    exclude_pitch_green: bool = True
    role_outlier_quantile: float = 0.88  # Outlier threshold for GK/Referee candidates
    gk_lateral_margin_ratio: float = 0.20  # Fraction of frame edge considered goal area
    seed: int = 42


@dataclass
class TrackIdentityAttributes:
    """Immutable identity attributes associated with a single track ID."""
    track_id: int
    team_label: str  # "TEAM_0", "TEAM_1", "UNKNOWN"
    team_confidence: float  # [0.0, 1.0]
    role: str  # "OUTFIELD_PLAYER", "GOALKEEPER", "REFEREE", "UNKNOWN"
    role_confidence: float  # [0.0, 1.0]
    evidence_count: int  # Number of valid crops aggregated
    features: dict[str, Any] = field(default_factory=dict)


def compute_laplacian_sharpness(img: np.ndarray) -> float:
    """Computes Laplacian variance as an indicator of crop focus and sharpness."""
    if img.size == 0 or img.shape[0] < 3 or img.shape[1] < 3:
        return 0.0
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def is_crop_quality_valid(
    bbox_xyxy: tuple[float, float, float, float] | list[float],
    frame_shape: tuple[int, int, ...],
    crop_bgr: np.ndarray | None,
    other_bboxes_xyxy: Sequence[tuple[float, float, float, float] | list[float]] = (),
    config: CropQualityFilterConfig = CropQualityFilterConfig(),
) -> bool:
    """
    Evaluates whether a player detection bounding box and its image crop meet
    the strict quality requirements for color and appearance attribution.
    """
    x1, y1, x2, y2 = bbox_xyxy
    w = max(0.0, x2 - x1)
    h = max(0.0, y2 - y1)

    if h < config.min_bbox_height or w < config.min_bbox_width:
        return False

    aspect_ratio = h / max(1.0, w)
    if aspect_ratio < config.min_aspect_ratio or aspect_ratio > config.max_aspect_ratio:
        return False

    h_img, w_img = frame_shape[:2]
    m = config.boundary_margin_px
    if x1 < m or y1 < m or x2 > (w_img - m) or y2 > (h_img - m):
        return False

    # Check mutual occlusion with any other candidate player
    for other in other_bboxes_xyxy:
        ox1, oy1, ox2, oy2 = other
        if ox1 == x1 and oy1 == y1 and ox2 == x2 and oy2 == y2:
            continue
        ix1 = max(x1, ox1)
        iy1 = max(y1, oy1)
        ix2 = min(x2, ox2)
        iy2 = min(y2, oy2)
        iw = max(0.0, ix2 - ix1)
        ih = max(0.0, iy2 - iy1)
        intersection = iw * ih
        if intersection > 0.0:
            union = (w * h) + ((ox2 - ox1) * (oy2 - oy1)) - intersection
            iou = intersection / max(1e-6, union)
            if iou >= config.max_overlap_iou:
                return False

    if crop_bgr is not None:
        sharpness = compute_laplacian_sharpness(crop_bgr)
        if sharpness < config.min_sharpness:
            return False

    return True


def extract_torso_crop(
    frame: np.ndarray,
    bbox_xyxy: tuple[float, float, float, float] | list[float],
    y_min_ratio: float = 0.15,
    y_max_ratio: float = 0.55,
    x_margin_ratio: float = 0.15,
) -> np.ndarray:
    """
    Extracts the upper body / jersey torso region from a full player bounding box.
    Cuts off head/hair above and shorts/legs below, and removes lateral field bleed.
    """
    h_img, w_img = frame.shape[:2]
    x1, y1, x2, y2 = bbox_xyxy
    w = max(1.0, x2 - x1)
    h = max(1.0, y2 - y1)

    tx1 = int(round(max(0.0, min(float(w_img - 1), x1 + x_margin_ratio * w))))
    tx2 = int(round(max(0.0, min(float(w_img), x2 - x_margin_ratio * w))))
    ty1 = int(round(max(0.0, min(float(h_img - 1), y1 + y_min_ratio * h))))
    ty2 = int(round(max(0.0, min(float(h_img), y1 + y_max_ratio * h))))

    if tx2 <= tx1 or ty2 <= ty1:
        tx1 = int(round(max(0.0, min(float(w_img - 1), x1))))
        tx2 = int(round(max(float(tx1 + 1), min(float(w_img), x2))))
        ty1 = int(round(max(0.0, min(float(h_img - 1), y1))))
        ty2 = int(round(max(float(ty1 + 1), min(float(h_img), y2))))

    torso = frame[ty1:ty2, tx1:tx2].copy()
    if torso.size == 0:
        torso = np.zeros((32, 16, 3), dtype=np.uint8)
    return torso


class ColorFeatureExtractor:
    """
    Extracts robust color representations (HSV / Lab histograms, dominant colors)
    from player torso crops while masking out pitch grass.
    """

    def __init__(
        self,
        hsv_h_bins: int = 16,
        hsv_s_bins: int = 8,
        hsv_v_bins: int = 8,
        exclude_pitch_green: bool = True,
    ) -> None:
        self.h_bins = hsv_h_bins
        self.s_bins = hsv_s_bins
        self.v_bins = hsv_v_bins
        self.exclude_green = exclude_pitch_green

    def get_pitch_green_mask(self, hsv_crop: np.ndarray) -> np.ndarray:
        """
        Detects standard football pitch grass in HSV space:
        Hue in [35, 85] (green band), Saturation >= 40, Value >= 30.
        Returns a boolean mask where True = grass pixel.
        """
        h = hsv_crop[:, :, 0]
        s = hsv_crop[:, :, 1]
        v = hsv_crop[:, :, 2]
        green_mask = (h >= 35) & (h <= 85) & (s >= 40) & (v >= 30)
        return green_mask

    def extract_hsv_histogram(self, torso_bgr: np.ndarray) -> np.ndarray:
        """
        Computes a normalized HSV color histogram excluding green field background.
        Returns an L2-normalized float32 vector of length (H_bins * S_bins + V_bins).
        """
        if torso_bgr.size == 0:
            return np.zeros(self.h_bins * self.s_bins + self.v_bins, dtype=np.float32)

        hsv = cv2.cvtColor(torso_bgr, cv2.COLOR_BGR2HSV)
        mask = None
        if self.exclude_green:
            green = self.get_pitch_green_mask(hsv)
            non_green = ~green
            # Only use mask if at least 15% of torso pixels are non-green
            if np.mean(non_green) >= 0.15:
                mask = (non_green.astype(np.uint8) * 255)

        # 2D HS histogram captures chromatic identity invariant to shading
        hist_hs = cv2.calcHist(
            [hsv], [0, 1], mask, [self.h_bins, self.s_bins], [0, 180, 0, 256]
        ).flatten()

        # 1D V histogram captures luminance (white vs dark jerseys)
        hist_v = cv2.calcHist(
            [hsv], [2], mask, [self.v_bins], [0, 256]
        ).flatten()

        hist = np.concatenate([hist_hs, hist_v], axis=0).astype(np.float32)
        norm = np.linalg.norm(hist)
        if norm > 1e-6:
            hist /= norm
        return hist

    def extract_lab_histogram(self, torso_bgr: np.ndarray, bins: int = 16) -> np.ndarray:
        """Computes a normalized Lab color histogram."""
        if torso_bgr.size == 0:
            return np.zeros(bins * 3, dtype=np.float32)

        lab = cv2.cvtColor(torso_bgr, cv2.COLOR_BGR2Lab)
        h_l = cv2.calcHist([lab], [0], None, [bins], [0, 256]).flatten()
        h_a = cv2.calcHist([lab], [1], None, [bins], [0, 256]).flatten()
        h_b = cv2.calcHist([lab], [2], None, [bins], [0, 256]).flatten()

        hist = np.concatenate([h_l, h_a, h_b], axis=0).astype(np.float32)
        norm = np.linalg.norm(hist)
        if norm > 1e-6:
            hist /= norm
        return hist


@dataclass
class TrackObservationBuffer:
    """Accumulates quality crops and features for one track ID over time."""
    track_id: int
    crops_torso: list[np.ndarray] = field(default_factory=list)
    bboxes_xyxy: list[tuple[float, float, float, float]] = field(default_factory=list)
    frame_indices: list[int] = field(default_factory=list)
    color_features: list[np.ndarray] = field(default_factory=list)
    reid_features: list[np.ndarray] = field(default_factory=list)

    def add_observation(
        self,
        frame_idx: int,
        bbox_xyxy: tuple[float, float, float, float],
        torso_crop: np.ndarray,
        color_feat: np.ndarray,
        reid_feat: np.ndarray | None = None,
        max_crops: int = 25,
    ) -> None:
        if len(self.crops_torso) < max_crops:
            self.frame_indices.append(frame_idx)
            self.bboxes_xyxy.append(bbox_xyxy)
            self.crops_torso.append(torso_crop)
            self.color_features.append(color_feat)
            if reid_feat is not None:
                self.reid_features.append(reid_feat)
        else:
            # Subsample uniformly across lifespan
            replace_idx = np.random.randint(0, len(self.crops_torso))
            self.frame_indices[replace_idx] = frame_idx
            self.bboxes_xyxy[replace_idx] = bbox_xyxy
            self.crops_torso[replace_idx] = torso_crop
            self.color_features[replace_idx] = color_feat
            if reid_feat is not None and len(self.reid_features) > replace_idx:
                self.reid_features[replace_idx] = reid_feat


class TrackAppearanceAggregator:
    """
    Aggregates temporal observations of a track into a single robust feature vector
    using coordinate-wise median or quality-weighted mean.
    """

    @staticmethod
    def aggregate_features(features_list: list[np.ndarray], strategy: str = "median") -> np.ndarray:
        """
        Aggregates a sequence of feature vectors for a track:
          - 'median': coordinate-wise median, then L2-normalized.
          - 'mean': coordinate-wise mean, then L2-normalized.
        """
        if not features_list:
            return np.empty(0, dtype=np.float32)

        arr = np.stack(features_list, axis=0)
        if strategy == "median":
            aggregated = np.median(arr, axis=0)
        else:
            aggregated = np.mean(arr, axis=0)

        norm = np.linalg.norm(aggregated)
        if norm > 1e-6:
            aggregated /= norm
        return aggregated.astype(np.float32)


class TeamClassifier:
    """
    Unsupervised track-level team attribution and player role classifier.
    Decoupled from tracker association: never alters tracker IDs.
    """

    def __init__(
        self,
        config: TeamClassifierConfig = TeamClassifierConfig(),
        quality_config: CropQualityFilterConfig = CropQualityFilterConfig(),
        reid_encoder: PlayerAppearanceEncoder | None = None,
    ) -> None:
        self.config = config
        self.quality_config = quality_config
        self.reid_encoder = reid_encoder
        self.color_extractor = ColorFeatureExtractor(
            hsv_h_bins=config.hsv_h_bins,
            hsv_s_bins=config.hsv_s_bins,
            hsv_v_bins=config.hsv_v_bins,
            exclude_pitch_green=config.exclude_pitch_green,
        )
        self._buffers: dict[int, TrackObservationBuffer] = {}
        self._assigned_attributes: dict[int, TrackIdentityAttributes] = {}

    def reset(self) -> None:
        """Resets all track buffers and assigned attributes between sequences."""
        self._buffers.clear()
        self._assigned_attributes.clear()

    def process_frame_detections(
        self,
        frame: np.ndarray,
        frame_idx: int,
        tracked_players: list[dict[str, Any]],
        precomputed_reid_features: dict[int, np.ndarray] | None = None,
    ) -> None:
        """
        Processes a single frame: filters quality crops, extracts appearance
        features, and updates per-track observation buffers.
        tracked_players: list of dicts with 'track_id' and 'bbox' [x1, y1, x2, y2].
        """
        all_bboxes = [p["bbox"] for p in tracked_players]

        for p_idx, player in enumerate(tracked_players):
            tid = int(player["track_id"])
            bbox = player["bbox"]

            torso = extract_torso_crop(frame, bbox)
            if not is_crop_quality_valid(
                bbox_xyxy=bbox,
                frame_shape=frame.shape,
                crop_bgr=torso,
                other_bboxes_xyxy=all_bboxes,
                config=self.quality_config,
            ):
                continue

            if self.config.feature_type == "lab_hist":
                color_feat = self.color_extractor.extract_lab_histogram(torso)
            else:
                color_feat = self.color_extractor.extract_hsv_histogram(torso)

            reid_feat = None
            if self.config.feature_type in ("reid", "fused"):
                if precomputed_reid_features and p_idx in precomputed_reid_features:
                    reid_feat = precomputed_reid_features[p_idx]
                elif self.reid_encoder is not None:
                    full_crop = extract_player_crop(frame, bbox)
                    reid_feat = self.reid_encoder.encode_crops([full_crop])[0]

            if tid not in self._buffers:
                self._buffers[tid] = TrackObservationBuffer(track_id=tid)

            self._buffers[tid].add_observation(
                frame_idx=frame_idx,
                bbox_xyxy=tuple(bbox),
                torso_crop=torso,
                color_feat=color_feat,
                reid_feat=reid_feat,
                max_crops=self.config.max_crops_per_track,
            )

    def process_extracted_observations(
        self,
        observations_by_track: dict[int, list[dict[str, Any]]],
    ) -> None:
        """
        Populates track buffers directly from pre-extracted quality observations.
        observations_by_track: dict mapping track_id -> list of dicts with:
          'frame_idx', 'bbox', 'torso_crop', 'full_crop'
        """
        for tid, obs_list in observations_by_track.items():
            if tid not in self._buffers:
                self._buffers[tid] = TrackObservationBuffer(track_id=tid)
            buf = self._buffers[tid]

            torso_crops = [o["torso_crop"] for o in obs_list]
            if self.config.feature_type == "lab_hist":
                color_feats = [self.color_extractor.extract_lab_histogram(c) for c in torso_crops]
            else:
                color_feats = [self.color_extractor.extract_hsv_histogram(c) for c in torso_crops]

            reid_feats = None
            if self.config.feature_type in ("reid", "fused") and self.reid_encoder is not None:
                full_crops = [o["full_crop"] for o in obs_list]
                reid_feats = self.reid_encoder.encode_crops(full_crops)

            for i, o in enumerate(obs_list):
                rf = reid_feats[i] if reid_feats is not None else None
                buf.add_observation(
                    frame_idx=o["frame_idx"],
                    bbox_xyxy=tuple(o["bbox"]),
                    torso_crop=o["torso_crop"],
                    color_feat=color_feats[i],
                    reid_feat=rf,
                    max_crops=self.config.max_crops_per_track,
                )

    def fit_and_assign(self, frame_width: int = 1920) -> dict[int, TrackIdentityAttributes]:
        """
        Executes track-level clustering to assign TEAM_0 / TEAM_1 and role classification
        (OUTFIELD_PLAYER, GOALKEEPER, REFEREE, UNKNOWN).
        Returns a dict mapping track_id -> TrackIdentityAttributes.
        """
        if not self._buffers:
            return {}

        track_ids = sorted(self._buffers.keys())
        track_vectors: list[np.ndarray] = []
        valid_track_ids: list[int] = []

        for tid in track_ids:
            buf = self._buffers[tid]
            if len(buf.color_features) < self.config.min_evidence_crops:
                continue

            if self.config.feature_type == "reid":
                if not buf.reid_features:
                    continue
                v = TrackAppearanceAggregator.aggregate_features(buf.reid_features, strategy="mean")
            elif self.config.feature_type == "fused":
                if not buf.reid_features:
                    continue
                c_v = TrackAppearanceAggregator.aggregate_features(buf.color_features, strategy="median")
                r_v = TrackAppearanceAggregator.aggregate_features(buf.reid_features, strategy="mean")
                v = np.concatenate([c_v, r_v], axis=0)
                norm = np.linalg.norm(v)
                if norm > 1e-6:
                    v /= norm
            else:
                v = TrackAppearanceAggregator.aggregate_features(buf.color_features, strategy="median")

            track_vectors.append(v)
            valid_track_ids.append(tid)

        results: dict[int, TrackIdentityAttributes] = {}

        # Fallback if too few tracks have sufficient evidence
        if len(valid_track_ids) < 4:
            for tid in track_ids:
                results[tid] = TrackIdentityAttributes(
                    track_id=tid,
                    team_label=TeamLabel.UNKNOWN.value,
                    team_confidence=0.0,
                    role=RoleType.UNKNOWN.value,
                    role_confidence=0.0,
                    evidence_count=len(self._buffers[tid].color_features) if tid in self._buffers else 0,
                )
            self._assigned_attributes = results
            return results

        X = np.stack(track_vectors, axis=0)

        # 1. Unsupervised 2-team clustering
        if self.config.method == "gmm":
            gmm = GaussianMixture(n_components=2, random_state=self.config.seed)
            gmm.fit(X)
            probs = gmm.predict_proba(X)
            cluster_labels = np.argmax(probs, axis=1)
            centers = gmm.means_
            # Normalise GMM center distances
            confidences = [float(abs(p[0] - p[1])) for p in probs]
        else:
            kmeans = KMeans(n_clusters=2, random_state=self.config.seed, n_init=10)
            kmeans.fit(X)
            cluster_labels = kmeans.labels_
            centers = kmeans.cluster_centers_

            dists = np.linalg.norm(X[:, None, :] - centers[None, :, :], axis=2)
            d0, d1 = dists[:, 0], dists[:, 1]
            confidences = [
                float(abs(d0[i] - d1[i]) / max(1e-6, d0[i] + d1[i]))
                for i in range(len(valid_track_ids))
            ]

        # 2. Outlier distance computation for role classification
        dists_to_centers = np.linalg.norm(X[:, None, :] - centers[None, :, :], axis=2)
        min_dists = np.min(dists_to_centers, axis=1)
        outlier_thresh = np.quantile(min_dists, self.config.role_outlier_quantile)

        # 3. Assign attributes with role heuristics
        for idx, tid in enumerate(valid_track_ids):
            c_label = cluster_labels[idx]
            conf = confidences[idx]
            min_d = min_dists[idx]
            buf = self._buffers[tid]

            # Spatial behavior: average lateral position across track
            xs = [(b[0] + b[2]) / 2.0 for b in buf.bboxes_xyxy]
            mean_x = float(np.mean(xs)) if xs else (frame_width / 2.0)
            lateral_dist = abs(mean_x - (frame_width / 2.0)) / (frame_width / 2.0)

            # Heuristics for role separation
            is_outlier = (min_d >= outlier_thresh and conf < 0.35)
            is_gk_candidate = lateral_dist >= (1.0 - self.config.gk_lateral_margin_ratio)

            if is_outlier and is_gk_candidate:
                role = RoleType.GOALKEEPER.value
                role_conf = round(float(lateral_dist), 4)
                team = TeamLabel.TEAM_0.value if c_label == 0 else TeamLabel.TEAM_1.value
            elif is_outlier:
                role = RoleType.REFEREE.value
                role_conf = round(float(min_d / max(1e-6, outlier_thresh)), 4)
                team = TeamLabel.UNKNOWN.value  # Referees do not belong to a team
            else:
                role = RoleType.OUTFIELD_PLAYER.value
                role_conf = round(conf, 4)
                team = TeamLabel.TEAM_0.value if c_label == 0 else TeamLabel.TEAM_1.value

            results[tid] = TrackIdentityAttributes(
                track_id=tid,
                team_label=team,
                team_confidence=round(conf, 4),
                role=role,
                role_confidence=role_conf,
                evidence_count=len(buf.color_features),
            )

        # Add remaining low-evidence tracks as UNKNOWN
        for tid in track_ids:
            if tid not in results:
                results[tid] = TrackIdentityAttributes(
                    track_id=tid,
                    team_label=TeamLabel.UNKNOWN.value,
                    team_confidence=0.0,
                    role=RoleType.UNKNOWN.value,
                    role_confidence=0.0,
                    evidence_count=len(self._buffers[tid].color_features) if tid in self._buffers else 0,
                )

        self._assigned_attributes = results
        return results

    def get_track_attributes(self, track_id: int) -> TrackIdentityAttributes | None:
        """Retrieves assigned attributes for a track ID."""
        return self._assigned_attributes.get(track_id)
