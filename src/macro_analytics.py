from __future__ import annotations

from pathlib import Path
from typing import Any

import cv2
import numpy as np
from tqdm import tqdm

from src.video_ingest import VideoMeta


def _classify_formation(centers: np.ndarray) -> tuple[str, float]:
    """centers: (N,2) normalized 0-1. Returns (type, confidence)."""
    if centers.size == 0:
        return "scatter", 0.0
    n = centers.shape[0]
    if n == 1:
        return "scatter", 0.5
    c = centers.mean(axis=0)
    dists = np.linalg.norm(centers - c, axis=1)
    md = float(np.mean(dists)) + 1e-9
    cv = float(np.std(dists) / md)
    X = centers - c
    if X.shape[0] >= 2:
        _, s, _ = np.linalg.svd(X, full_matrices=False)
        s0, s1 = float(s[0]), float(s[1]) if len(s) > 1 else 0.0
        pca_ratio = (s0**2) / (s0**2 + s1**2 + 1e-9)
    else:
        pca_ratio = 1.0
    if cv < 0.42 and md > 0.04:
        return "circle", float(min(1.0, 1.2 - cv))
    if pca_ratio > 0.78 and n >= 3:
        return "line", float(min(1.0, pca_ratio))
    if n >= 4:
        dmat = np.linalg.norm(centers[:, None, :] - centers[None, :, :], axis=-1)
        i, j = divmod(int(np.argmax(dmat)), n)
        a, b = centers[i], centers[j]
        la = np.linalg.norm(centers - a, axis=1)
        lb = np.linalg.norm(centers - b, axis=1)
        lab = np.minimum(la, lb)
        sep = float(np.linalg.norm(a - b))
        compact = float(np.mean(lab) + 1e-9)
        if sep > 2.8 * compact:
            return "cluster", float(min(1.0, sep / (md + 1e-6)))
    return "scatter", 0.55


def _heatmap_grid(centers: np.ndarray) -> np.ndarray:
    grid = np.zeros((3, 3), dtype=np.float64)
    if centers.size == 0:
        return grid
    for x, y in centers:
        gx = min(2, int(float(x) * 3))
        gy = min(2, int(float(y) * 3))
        grid[gy, gx] += 1.0
    s = grid.sum()
    if s > 0:
        grid /= s
    return grid


def run_macro(
    video_path: str | Path,
    meta: VideoMeta,
    model,
    sample_stride: int = 3,
    heatmap_png: Path | None = None,
) -> dict[str, Any]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(video_path)

    window_sec = 30.0

    sampled_centers: list[np.ndarray] = []
    sampled_ts: list[float] = []
    dist_series: list[float] = []
    motion_active: list[float] = []

    prev_centers: np.ndarray | None = None
    cm_per_px = 0.35
    frame_idx = 0
    pbar = tqdm(total=meta.frame_count, desc="macro/yolo", unit="f")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % sample_stride != 0:
            frame_idx += 1
            pbar.update(1)
            continue

        h, w = frame.shape[:2]
        res = model(frame, verbose=False)[0]
        xyxy = res.boxes.xyxy.cpu().numpy() if res.boxes is not None and len(res.boxes) else np.zeros((0, 4))

        centers = []
        for i in range(xyxy.shape[0]):
            x1, y1, x2, y2 = xyxy[i]
            cx = ((x1 + x2) * 0.5) / max(w, 1)
            cy = ((y1 + y2) * 0.5) / max(h, 1)
            centers.append((cx, cy))
        C = np.asarray(centers, dtype=np.float64) if centers else np.zeros((0, 2))

        if C.shape[0] >= 2:
            pd = np.linalg.norm(C[:, None, :] - C[None, :, :], axis=-1)
            triu = np.triu_indices(C.shape[0], k=1)
            dist_series.append(float(pd[triu].mean() * max(h, w) * cm_per_px))

        active_frac = 0.0
        if prev_centers is not None and C.shape[0] and prev_centers.shape[0]:
            m = min(C.shape[0], prev_centers.shape[0])
            dxy = np.linalg.norm(C[:m] - prev_centers[:m], axis=1)
            speed = dxy * (meta.fps / max(sample_stride, 1)) * max(h, w) * cm_per_px
            active_frac = float(np.mean(speed > 0.5))
        motion_active.append(active_frac)
        prev_centers = C.copy() if C.shape[0] else prev_centers

        sampled_centers.append(C)
        sampled_ts.append(frame_idx / max(meta.fps, 1e-6))
        frame_idx += 1
        pbar.update(1)
    pbar.close()
    cap.release()

    if not sampled_centers:
        return {
            "formation_timeline": [],
            "heatmap_grid": [[0.0] * 3 for _ in range(3)],
            "hotspot_zones": [],
            "underused_zones": [],
            "avg_distance_timeline": [],
            "overall_avg_cm": 0.0,
            "engagement_score": 0.0,
            "engagement_timeline": [],
            "low_engagement_periods": [],
            "warnings": ["無法讀取影片幀"],
        }

    timeline: list[dict[str, Any]] = []
    duration = meta.duration_sec or 1.0
    nwin = max(1, int(np.ceil(duration / window_sec)))
    for wi in range(nwin):
        t0 = wi * window_sec
        t1 = min(duration, (wi + 1) * window_sec)
        idxs = [i for i, t in enumerate(sampled_ts) if t0 <= t < t1]
        if not idxs:
            continue
        rows = [sampled_centers[i] for i in idxs if sampled_centers[i].shape[0] > 0]
        if not rows:
            continue
        W = np.vstack(rows)
        if W.shape[0] == 0:
            continue
        ftype, ratio = _classify_formation(W)
        timeline.append(
            {
                "start": f"{int(t0 // 60):02d}:{int(t0 % 60):02d}",
                "end": f"{int(t1 // 60):02d}:{int(t1 % 60):02d}",
                "type": ftype,
                "ratio": float(round(ratio, 3)),
            }
        )

    H = np.zeros((3, 3))
    for C in sampled_centers:
        H += _heatmap_grid(C)
    H = H / (H.sum() + 1e-9)
    flat = H.flatten()
    meanv = float(flat.mean()) + 1e-9
    hotspot, under = [], []
    for gy in range(3):
        for gx in range(3):
            val = H[gy, gx]
            label = ["上", "中", "下"][gy] + ["左", "中", "右"][gx]
            if val >= meanv + 0.35 * (float(flat.max()) - meanv):
                hotspot.append(label)
            if val <= meanv * 0.65:
                under.append(label)

    avg_timeline = []
    step = max(1, len(dist_series) // 30)
    for j, i in enumerate(range(0, len(dist_series), step)):
        avg_timeline.append({"time": f"00:{j * 5:02d}", "avg_cm": float(round(dist_series[i], 1))})
    overall_avg = float(np.mean(dist_series)) if dist_series else 0.0

    eng = float(np.mean(motion_active)) if motion_active else 0.0
    eng_timeline = [{"time": "00:00-全片", "rate": round(eng, 3)}]

    out: dict[str, Any] = {
        "formation_timeline": timeline,
        "heatmap_grid": H.tolist(),
        "hotspot_zones": hotspot[:5],
        "underused_zones": under[:5],
        "avg_distance_timeline": avg_timeline[:40],
        "overall_avg_cm": overall_avg,
        "min_cm": float(np.min(dist_series)) if dist_series else 0.0,
        "max_cm": float(np.max(dist_series)) if dist_series else 0.0,
        "engagement_score": eng,
        "engagement_timeline": eng_timeline,
        "low_engagement_periods": [],
        "warnings": [],
    }
    small = sum(1 for C in sampled_centers if C.shape[0] < 3) / max(len(sampled_centers), 1)
    if small > 0.6:
        out["warnings"].append("多數幀偵測到幼兒 < 3 人，隊形分析僅供參考（macro_analytics）")

    if heatmap_png is not None:
        from src.viz import save_heatmap_png

        save_heatmap_png(H.tolist(), Path(heatmap_png))
        out["heatmap_png"] = str(Path(heatmap_png).resolve())
    return out
