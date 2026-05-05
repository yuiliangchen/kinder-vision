from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import librosa
import numpy as np


@dataclass
class VideoMeta:
    path: str
    width: int
    height: int
    fps: float
    frame_count: int
    duration_sec: float


def read_video_meta(video_path: str | Path) -> VideoMeta:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(f"Cannot open video: {video_path}")
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0) or 25.0
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    duration = n / fps if fps > 0 else 0.0
    cap.release()
    return VideoMeta(str(video_path), width, height, fps, n, duration)


def load_audio_mono(video_path: str | Path, sr: int = 22050) -> tuple[np.ndarray, int]:
    y, sr = librosa.load(str(video_path), sr=sr, mono=True)
    return y, int(sr)
