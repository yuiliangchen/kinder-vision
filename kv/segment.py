from __future__ import annotations

import subprocess
from pathlib import Path


def export_video_segment(src: Path, t0_sec: float, t1_sec: float, dst: Path) -> None:
    """以 ffmpeg 裁切影片（含音訊），供區間分析。需系統已安裝 ffmpeg。"""
    dst = Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    dur = max(0.25, float(t1_sec) - float(t0_sec))
    # 先精準裁切再編碼，避免 -c copy Keyframe 問題
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-ss",
        str(t0_sec),
        "-i",
        str(src),
        "-t",
        str(dur),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "23",
        "-movflags",
        "+faststart",
        str(dst),
    ]
    try:
        subprocess.run(cmd + ["-c:a", "aac", "-b:a", "128k"], check=True)
    except subprocess.CalledProcessError:
        subprocess.run(cmd + ["-an"], check=True)
