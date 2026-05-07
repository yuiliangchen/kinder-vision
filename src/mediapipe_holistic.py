"""MediaPipe Tasks Holistic Landmarker：裁切內同時有臉／手／姿勢，此處僅取姿勢 33 點轉 COCO17。"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import cv2
import numpy as np

from mediapipe.tasks.python.core import base_options as base_options_lib
from mediapipe.tasks.python.vision import HolisticLandmarker, HolisticLandmarkerOptions
from mediapipe.tasks.python.vision.core import image as mp_image

from src.mediapipe_kp_common import crop_padded_xyxy, normalized_pose_list_to_coco17

_HOLISTIC_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/holistic_landmarker/"
    "holistic_landmarker/float16/latest/holistic_landmarker.task"
)


def _ensure_holistic_model_file() -> Path:
    cache = Path.home() / ".cache" / "kinder-vision"
    cache.mkdir(parents=True, exist_ok=True)
    dst = cache / "holistic_landmarker.task"
    if dst.is_file() and dst.stat().st_size > 100_000:
        return dst
    req = urllib.request.Request(_HOLISTIC_MODEL_URL, headers={"User-Agent": "KinderVision/1.0"})
    with urllib.request.urlopen(req, timeout=180) as resp, open(dst, "wb") as f:
        f.write(resp.read())
    return dst


class MediaPipeHolisticRefiner:
    """HolisticLandmarker（單人裁切）：輸出 COCO 17×2 全畫素座標。"""

    def __init__(self) -> None:
        path = str(_ensure_holistic_model_file())
        opts = HolisticLandmarkerOptions(
            base_options=base_options_lib.BaseOptions(model_asset_path=path),
            min_pose_detection_confidence=0.35,
            min_pose_landmarks_confidence=0.35,
            min_face_detection_confidence=0.35,
        )
        self._lm = HolisticLandmarker.create_from_options(opts)

    def close(self) -> None:
        self._lm.close()

    def landmarks_coco17_fullframe(self, frame_bgr: np.ndarray, xyxy: np.ndarray, vis_thr: float = 0.35) -> np.ndarray | None:
        boxed = crop_padded_xyxy(frame_bgr, xyxy)
        if boxed is None:
            return None
        crop, xi1, yi1, cw, ch = boxed
        rgb = np.ascontiguousarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        image = mp_image.Image(image_format=mp_image.ImageFormat.SRGB, data=rgb)
        result = self._lm.detect(image)
        if not result.pose_landmarks or len(result.pose_landmarks) < 33:
            return None
        return normalized_pose_list_to_coco17(result.pose_landmarks, xi1, yi1, cw, ch, vis_thr=vis_thr)


def try_create_holistic_refiner() -> MediaPipeHolisticRefiner | None:
    try:
        return MediaPipeHolisticRefiner()
    except Exception:
        return None


def refine_holistic_if_possible(
    refiner: MediaPipeHolisticRefiner | None,
    frame_bgr: np.ndarray,
    xyxy: np.ndarray | None,
    yolo_kp: np.ndarray,
) -> np.ndarray:
    if refiner is None or xyxy is None or xyxy.size < 4:
        return yolo_kp
    refined = refiner.landmarks_coco17_fullframe(frame_bgr, xyxy)
    return refined if refined is not None else yolo_kp
