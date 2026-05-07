"""將 MediaPipe 33 點姿勢（正規化於裁切區）轉為 COCO 17×2 全畫素座標。"""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np


def crop_padded_xyxy(
    frame_bgr: np.ndarray, xyxy: np.ndarray, pad: float = 0.12
) -> tuple[np.ndarray, int, int, int, int] | None:
    """依人框外擴裁切；回傳 (crop, xi1, yi1, cw, ch)。"""
    x1, y1, x2, y2 = [float(v) for v in xyxy]
    h, w = frame_bgr.shape[:2]
    bw = max(1.0, x2 - x1)
    bh = max(1.0, y2 - y1)
    xi1 = max(0, int(x1 - bw * pad))
    yi1 = max(0, int(y1 - bh * pad))
    xi2 = min(w, int(x2 + bw * pad))
    yi2 = min(h, int(y2 + bh * pad))
    if xi2 <= xi1 + 8 or yi2 <= yi1 + 8:
        return None
    crop = frame_bgr[yi1:yi2, xi1:xi2]
    ch, cw = crop.shape[:2]
    return crop, xi1, yi1, cw, ch
from mediapipe.tasks.python.vision import PoseLandmark


def normalized_pose_list_to_coco17(
    lms: Sequence[Any],
    xi1: int,
    yi1: int,
    cw: int,
    ch: int,
    vis_thr: float = 0.35,
) -> np.ndarray | None:
    if len(lms) < 33:
        return None

    def vis(i: int) -> float:
        lm = lms[i]
        v = getattr(lm, "visibility", None)
        return float(v) if v is not None else 1.0

    for idx in (int(PoseLandmark.LEFT_WRIST), int(PoseLandmark.RIGHT_WRIST), int(PoseLandmark.LEFT_HIP), int(PoseLandmark.RIGHT_HIP)):
        if vis(idx) < vis_thr:
            return None

    def pt(i: int) -> tuple[float, float]:
        lm = lms[i]
        x = float(getattr(lm, "x", 0.0) or 0.0) * cw + xi1
        y = float(getattr(lm, "y", 0.0) or 0.0) * ch + yi1
        return x, y

    out = np.zeros((17, 2), dtype=np.float64)
    mapping: list[tuple[int, int]] = [
        (int(PoseLandmark.NOSE), 0),
        (int(PoseLandmark.LEFT_EYE), 1),
        (int(PoseLandmark.RIGHT_EYE), 2),
        (int(PoseLandmark.LEFT_EAR), 3),
        (int(PoseLandmark.RIGHT_EAR), 4),
        (int(PoseLandmark.LEFT_SHOULDER), 5),
        (int(PoseLandmark.RIGHT_SHOULDER), 6),
        (int(PoseLandmark.LEFT_ELBOW), 7),
        (int(PoseLandmark.RIGHT_ELBOW), 8),
        (int(PoseLandmark.LEFT_WRIST), 9),
        (int(PoseLandmark.RIGHT_WRIST), 10),
        (int(PoseLandmark.LEFT_HIP), 11),
        (int(PoseLandmark.RIGHT_HIP), 12),
        (int(PoseLandmark.LEFT_KNEE), 13),
        (int(PoseLandmark.RIGHT_KNEE), 14),
        (int(PoseLandmark.LEFT_ANKLE), 15),
        (int(PoseLandmark.RIGHT_ANKLE), 16),
    ]
    for mpi, coco_i in mapping:
        x, y = pt(mpi)
        out[coco_i, 0] = x
        out[coco_i, 1] = y
    return out
