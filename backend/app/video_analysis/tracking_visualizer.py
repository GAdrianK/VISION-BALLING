from __future__ import annotations

from typing import Sequence

import cv2
import numpy as np

from app.video_analysis.tracking_schemas import (
    BallObservationState,
    BallTrackObservation,
    PlayerTrackObservation,
)


def draw_player_tracks(
    frame: np.ndarray,
    players: Sequence[PlayerTrackObservation],
    color: tuple[int, int, int] = (255, 120, 0),  # Blue-ish / Orange in BGR
) -> np.ndarray:
    """
    Renders player bounding boxes and persistent track IDs.
    Returns modified copy of the frame.
    """
    out = frame.copy()
    for p in players:
        x1, y1, x2, y2 = (int(v) for v in p.bbox)
        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"ID: {p.track_id} ({p.confidence:.2f})"
        font_scale = 0.5
        thickness = 1
        (label_w, label_h), baseline = cv2.getTextSize(
            label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
        )
        tag_y1 = max(0, y1 - label_h - baseline - 4)
        cv2.rectangle(
            out,
            (x1, tag_y1),
            (x1 + label_w + 4, tag_y1 + label_h + baseline + 4),
            color,
            -1,
        )
        cv2.putText(
            out,
            label,
            (x1 + 2, tag_y1 + label_h + 2),
            cv2.FONT_HERSHEY_SIMPLEX,
            font_scale,
            (255, 255, 255),
            thickness,
            cv2.LINE_AA,
        )
    return out


def draw_ball_track(
    frame: np.ndarray,
    ball: BallTrackObservation | None,
    trail: Sequence[BallTrackObservation] = (),
) -> np.ndarray:
    """
    Renders ball observation with visually distinct states:
      - DETECTED: Green solid circle + confidence
      - INTERPOLATED: Orange circle + 'INTERP' tag
      - PREDICTED: Cyan circle + 'PRED' tag
      - LOST: No marker drawn
    """
    if ball is None or ball.observation_state == BallObservationState.LOST:
        return frame

    out = frame.copy()

    # Draw recent motion trail
    if trail:
        points = [
            (int(obs.position[0]), int(obs.position[1]))
            for obs in trail
            if obs.observation_state != BallObservationState.LOST
        ]
        for i in range(1, len(points)):
            cv2.line(out, points[i - 1], points[i], (0, 255, 255), 1, cv2.LINE_AA)

    cx, cy = int(ball.position[0]), int(ball.position[1])

    if ball.observation_state == BallObservationState.DETECTED:
        color = (0, 255, 0)  # Bright Green
        label = f"BALL {ball.confidence:.2f}" if ball.confidence else "BALL"
        cv2.circle(out, (cx, cy), 8, color, -1)
        cv2.circle(out, (cx, cy), 12, (255, 255, 255), 1, cv2.LINE_AA)
    elif ball.observation_state == BallObservationState.INTERPOLATED:
        color = (0, 165, 255)  # Orange in BGR
        label = "BALL (INTERP)"
        cv2.circle(out, (cx, cy), 7, color, 2, cv2.LINE_AA)
        cv2.circle(out, (cx, cy), 3, color, -1)
    elif ball.observation_state == BallObservationState.PREDICTED:
        color = (255, 255, 0)  # Cyan in BGR
        label = f"BALL (PRED +{ball.gap_length})"
        cv2.circle(out, (cx, cy), 6, color, 1, cv2.LINE_AA)
    else:
        return out

    # Draw label above ball
    font_scale = 0.45
    cv2.putText(
        out,
        label,
        (cx + 10, cy - 8),
        cv2.FONT_HERSHEY_SIMPLEX,
        font_scale,
        color,
        1,
        cv2.LINE_AA,
    )
    return out


def visualize_frame_tracks(
    frame: np.ndarray,
    players: Sequence[PlayerTrackObservation],
    ball: BallTrackObservation | None,
    ball_trail: Sequence[BallTrackObservation] = (),
) -> np.ndarray:
    """Combines player and ball visualization into a single annotated frame."""
    frame_annotated = draw_player_tracks(frame, players)
    return draw_ball_track(frame_annotated, ball, trail=ball_trail)
