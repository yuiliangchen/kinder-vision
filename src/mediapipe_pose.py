from __future__ import annotations

import urllib.request
from pathlib import Path

import cv2
import numpy as np

import mediapipe as mp
from mediapipe.tasks.python.core import base_options as base_options_lib
from mediapipe.tasks.python.vision import PoseLandmarker, PoseLandmarkerOptions
from mediapipe.python._framework_bindings import image as mp_image

from src.mediapipe_kp_common import crop_padded_xyxy, normalized_pose_list_to_coco17

_POSE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/1/pose_landmarker_lite.task"
)


def _ensure_pose_model_file() -> Path:
    cache = Path.home() / ".cache" / "kinder-vision"
    cache.mkdir(parents=True, exist_ok=True)
    dst = cache / "pose_landmarker_lite.task"
    if dst.is_file() and dst.stat().st_size > 100_000:
        return dst
    req = urllib.request.Request(_POSE_MODEL_URL, headers={"User-Agent": "KinderVision/1.0"})
    with urllib.request.urlopen(req, timeout=120) as resp, open(dst, "wb") as f:
        f.write(resp.read())
    return dst


class MediaPipePoseRefiner:
    """MediaPipe Pose Landmarker：於 YOLO 人框裁切上精化。"""

    def __init__(self) -> None:
        model_path = str(_ensure_pose_model_file())
        opts = PoseLandmarkerOptions(
            base_options=base_options_lib.BaseOptions(model_asset_path=model_path),
            num_poses=1,
            min_pose_detection_confidence=0.35,
            min_pose_presence_confidence=0.35,
            min_tracking_confidence=0.35,
        )
        self._landmarker = PoseLandmarker.create_from_options(opts)

    def close(self) -> None:
        self._landmarker.close()

    def landmarks_coco17_fullframe(self, frame_bgr: np.ndarray, xyxy: np.ndarray, vis_thr: float = 0.35) -> np.ndarray | None:
        boxed = crop_padded_xyxy(frame_bgr, xyxy)
        if boxed is None:
            return None
        crop, xi1, yi1, cw, ch = boxed
        rgb = np.ascontiguousarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB))
        image = mp_image.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect(image)
        if not result.pose_landmarks:
            return None
        lms = result.pose_landmarks[0]
        return normalized_pose_list_to_coco17(lms, xi1, yi1, cw, ch, vis_thr=vis_thr)


def try_create_refiner() -> MediaPipePoseRefiner | None:
    try:
        return MediaPipePoseRefiner()
    except Exception:
        return None


def refine_keypoints_if_possible(
    refiner: MediaPipePoseRefiner | None,
    frame_bgr: np.ndarray,
    xyxy: np.ndarray | None,
    yolo_kp: np.ndarray,
) -> np.ndarray:
    if refiner is None or xyxy is None or xyxy.size < 4:
        return yolo_kp
    refined = refiner.landmarks_coco17_fullframe(frame_bgr, xyxy)
    return refined if refined is not None else yolo_kp
