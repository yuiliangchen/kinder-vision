from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import librosa
import numpy as np
from scipy.signal import savgol_filter
from tqdm import tqdm

from kv import face_insight, identity
from kv.mediapipe_holistic import try_create_holistic_refiner
from kv.mediapipe_pose import try_create_refiner
from kv.video_ingest import VideoMeta


def _hip_center(kp: np.ndarray) -> np.ndarray:
    if kp.shape[0] < 13:
        return kp[0]
    return (kp[11] + kp[12]) * 0.5


def _wrist_signal(kp: np.ndarray) -> float:
    if kp.shape[0] < 11:
        return float(np.linalg.norm(kp[0]))
    return float(np.linalg.norm(kp[9]) + np.linalg.norm(kp[10]))


def _find_peaks(sig: np.ndarray, thr: float) -> list[int]:
    peaks = []
    for i in range(1, len(sig) - 1):
        if sig[i] > sig[i - 1] and sig[i] >= sig[i + 1] and sig[i] > thr:
            peaks.append(i)
    return peaks


def _refine_landmarks(refiner, frame_bgr: np.ndarray, box: np.ndarray | None, kp: np.ndarray) -> np.ndarray:
    if refiner is None or frame_bgr is None or box is None or box.size < 4:
        return kp
    refined = refiner.landmarks_coco17_fullframe(frame_bgr, box)
    return refined if refined is not None else kp


def _mean_unit_embeddings(vecs: list[np.ndarray]) -> np.ndarray | None:
    if not vecs:
        return None
    M = np.stack([np.asarray(v, dtype=np.float64).ravel() for v in vecs], axis=0)
    v = M.mean(axis=0)
    n = float(np.linalg.norm(v))
    return (v / n) if n > 1e-9 else None


def _face_patch_from_det(frame_bgr: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    h = frame_bgr.shape[0]
    h_box = max(1, y2 - y1)
    y2f = min(h, int(y1 + 0.42 * h_box))
    return frame_bgr[y1:y2f, x1:x2]


def _upper_body_patch_from_det(frame_bgr: np.ndarray, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    h = frame_bgr.shape[0]
    h_box = max(1, y2 - y1)
    y2u = min(h, int(y1 + 0.65 * h_box))
    return frame_bgr[y1:y2u, x1:x2]


def _detect_stop_times(y: np.ndarray, sr: int) -> list[float]:
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    times = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)
    med = float(np.median(rms) + 1e-9)
    drops = np.where(rms[:-1] - rms[1:] > 0.35 * med)[0]
    return [float(times[i]) for i in drops[:12]]


def _series_to_children(
    series_by_tid: dict[int, list[dict[str, Any]]],
    meta: VideoMeta,
    beat_times: list[float],
    stop_times: list[float],
    tempo: float,
    meter_per_px: float,
    trajectory_dir: Path | None,
) -> tuple[list[dict[str, Any]], list[str]]:
    warnings: list[str] = []
    per: list[dict[str, Any]] = []
    if not series_by_tid:
        return [], ["未偵測到可追蹤的人物關鍵點"]

    mean_cx: list[tuple[int, float]] = []
    for tid, rows in series_by_tid.items():
        cxs = [float(r["cx"]) for r in rows if r.get("cx") is not None]
        mean_cx.append((tid, float(np.mean(cxs)) if cxs else 0.0))
    mean_cx.sort(key=lambda x: x[1])
    tid_order = [t for t, _ in mean_cx]

    for slot, tid in enumerate(tid_order):
        rows = series_by_tid[tid]
        if len(rows) < 8:
            continue
        ts = np.asarray([r["t"] for r in rows], dtype=np.float64)
        wrist_v = np.asarray([r["w"] for r in rows], dtype=np.float64)
        hip_xy = np.asarray([r["hip"] for r in rows], dtype=np.float64)
        h = int(rows[0].get("h", 480))
        wf = int(rows[0].get("w_img", 640))
        hip_norm = np.stack([hip_xy[:, 0] / max(wf, 1), hip_xy[:, 1] / max(h, 1)], axis=1)

        wl = min(9, (len(wrist_v) // 2) * 2 - 1)
        if wl >= 5 and wl % 2 == 1:
            sm = savgol_filter(wrist_v, window_length=wl, polyorder=2, mode="interp")
        else:
            sm = wrist_v
        thr = float(np.percentile(sm, 70))
        peak_idx = _find_peaks(sm, thr)
        errs = []
        for pi in peak_idx:
            pt = ts[pi]
            if not beat_times:
                break
            j = int(np.argmin(np.abs(np.asarray(beat_times) - pt)))
            errs.append(float(abs(beat_times[j] - pt) * 1000.0))
        avg_err = float(np.mean(errs)) if errs else 180.0

        disp_list = []
        for st in stop_times:
            mask = (ts >= st) & (ts <= st + 1.0)
            if mask.sum() < 2:
                continue
            hip_s = hip_xy[mask]
            disp = float(np.linalg.norm(hip_s[-1] - hip_s[0]) * meter_per_px * 100.0)
            disp_list.append({"signal_time": f"{st:.1f}", "displacement_cm": round(disp, 2)})
        avg_disp = float(np.mean([d["displacement_cm"] for d in disp_list])) if disp_list else 12.0

        if len(hip_xy) >= 7:
            pos_m = hip_xy * meter_per_px
            dt = np.diff(ts)
            dt[dt <= 0] = 1.0 / max(meta.fps, 1e-6)
            vel = np.diff(pos_m, axis=0) / dt[:, None]
            acc = np.diff(vel, axis=0) / (dt[:-1, None] + dt[1:, None])
            jerk = np.linalg.norm(np.diff(acc, axis=0), axis=1)
            avg_jerk = float(np.mean(jerk)) if len(jerk) else 5.0
        else:
            avg_jerk = 5.0

        child_id = str(slot + 1)
        traj_rel: str | None = None
        if trajectory_dir is not None:
            from kv.viz import save_trajectory_png

            p = Path(trajectory_dir) / f"kinder-child-{child_id}-trajectory.png"
            save_trajectory_png(hip_norm, p, title=f"孩子 {child_id} 髖部軌跡 (track {tid})")
            traj_rel = str(p.resolve())

        per.append(
            {
                "child_id": child_id,
                "track_id": int(tid),
                "bpm": float(round(float(tempo), 2)),
                "avg_error_ms": round(avg_err, 2),
                "sync_rating": "優秀" if avg_err < 50 else "良好" if avg_err < 150 else "需加強",
                "stop_signals_detected": disp_list[:6],
                "avg_displacement_cm": round(avg_disp, 2),
                "stability_rating": "優秀" if avg_disp < 5 else "良好" if avg_disp < 15 else "需加強",
                "concern_flag": avg_disp > 15,
                "avg_jerk": round(avg_jerk, 3),
                "fluency_rating": "流暢" if avg_jerk < 2 else "普通" if avg_jerk < 5 else "僵硬",
                "trajectory_image": traj_rel,
            }
        )
    return per, warnings


def run_micro(
    video_path: str | Path,
    meta: VideoMeta,
    model,
    audio_y: np.ndarray,
    audio_sr: int,
    sample_stride: int = 2,
    meter_per_px: float = 0.003,
    use_tracking: bool = True,
    trajectory_dir: Path | None = None,
    use_mediapipe: bool | None = None,
    pose_mode: str = "pose",
    use_video_reid: bool = True,
    learn_identities: bool = False,
) -> dict[str, Any]:
    tempo, beats = librosa.beat.beat_track(y=audio_y, sr=audio_sr, units="time")
    _tb = np.asarray(tempo, dtype=np.float64).ravel()
    bpm_hint = float(_tb[0]) if _tb.size and np.isfinite(_tb[0]) else 120.0
    beat_times = list(np.asarray(beats, dtype=np.float64))
    stop_times = _detect_stop_times(audio_y, audio_sr)

    mode = (pose_mode or "pose").strip().lower()
    if mode not in ("off", "pose", "holistic"):
        mode = "pose"
    if use_mediapipe is False:
        mode = "off"

    refiner = None
    if mode == "holistic":
        refiner = try_create_holistic_refiner()
        pose_backend = "yolo+mediapipe_holistic" if refiner is not None else "yolo_only"
    elif mode == "pose":
        refiner = try_create_refiner()
        pose_backend = "yolo+mediapipe_pose" if refiner is not None else "yolo_only"
    else:
        pose_backend = "yolo_only"

    mp_warn: list[str] = []
    if mode != "off" and refiner is None:
        mp_warn.append(f"已選 pose_mode={mode} 但無法建立 MediaPipe 模型，改以僅 YOLO 關節運算。")

    try:
        if use_tracking:
            series_by_tid, wmsg, reid_by_track = _collect_micro_tracking(
                model,
                video_path,
                meta,
                sample_stride,
                refiner=refiner,
                use_video_reid=use_video_reid,
                learn_identities=learn_identities,
            )
            children, w2 = _series_to_children(
                series_by_tid, meta, beat_times, stop_times, bpm_hint, meter_per_px, trajectory_dir
            )
            warnings = mp_warn + list(wmsg) + list(w2)
            out = {
                "children": children,
                "bpm_hint": bpm_hint,
                "warnings": warnings,
                "tracking": "bytetrack",
                "vid_stride": sample_stride,
                "pose_backend": pose_backend,
                "reid_by_track": reid_by_track,
            }
            if not children:
                return run_micro(
                    video_path,
                    meta,
                    model,
                    audio_y,
                    audio_sr,
                    sample_stride=sample_stride,
                    meter_per_px=meter_per_px,
                    use_tracking=False,
                    trajectory_dir=trajectory_dir,
                    use_mediapipe=use_mediapipe,
                    pose_mode=pose_mode,
                    use_video_reid=use_video_reid,
                    learn_identities=learn_identities,
                )
            return out

        children, warnings = _run_micro_sorted_slots(
            video_path,
            meta,
            model,
            sample_stride,
            beat_times,
            stop_times,
            bpm_hint,
            meter_per_px,
            trajectory_dir,
            refiner=refiner,
        )
        return {
            "children": children,
            "bpm_hint": bpm_hint,
            "warnings": mp_warn + list(warnings),
            "tracking": "none",
            "vid_stride": sample_stride,
            "pose_backend": pose_backend,
            "reid_by_track": {},
        }
    finally:
        if refiner is not None:
            refiner.close()


def _collect_micro_tracking(
    model,
    video_path: str | Path,
    meta: VideoMeta,
    sample_stride: int,
    refiner,
    use_video_reid: bool,
    learn_identities: bool,
) -> tuple[dict[int, list[dict[str, Any]]], list[str], dict[str, dict[str, Any]]]:
    warnings: list[str] = []
    tracks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    track_face_vecs: dict[int, list[np.ndarray]] = defaultdict(list)
    track_app_vecs: dict[int, list[np.ndarray]] = defaultdict(list)
    frame_iter = 0
    skipped_id = False
    stride = max(1, int(sample_stride))
    est = max(1, meta.frame_count // stride)
    pbar = tqdm(total=est, desc="micro/track", unit="f")
    for r in model.track(
        source=str(video_path),
        stream=True,
        persist=True,
        vid_stride=stride,
        verbose=False,
        conf=0.25,
    ):
        h, w_img = r.orig_shape
        frame_idx = frame_iter * stride
        t = frame_idx / max(meta.fps, 1e-6)
        frame_iter += 1
        pbar.update(1)
        kps = r.keypoints.xy.cpu().numpy() if r.keypoints is not None and len(r.keypoints) else np.zeros((0, 17, 2))
        if kps.shape[0] == 0:
            continue
        frame_bgr = r.orig_img
        if not isinstance(frame_bgr, np.ndarray):
            frame_bgr = None
        xyxy_all = r.boxes.xyxy.cpu().numpy() if r.boxes is not None and len(r.boxes) else None
        ids = None
        if r.boxes is not None and r.boxes.id is not None and len(r.boxes.id):
            ids = r.boxes.id.int().cpu().numpy()
        if ids is None or len(ids) < kps.shape[0]:
            skipped_id = True
            continue
        for j in range(kps.shape[0]):
            tid = int(ids[j])
            kp = kps[j].copy()
            box = xyxy_all[j] if xyxy_all is not None and j < xyxy_all.shape[0] else None
            if frame_bgr is not None:
                kp = _refine_landmarks(refiner, frame_bgr, box, kp)
                if use_video_reid and box is not None:
                    x1, y1, x2, y2 = [int(max(0, v)) for v in box[:4]]
                    x2, y2 = min(w_img, x2), min(h, y2)
                    if x2 > x1 + 4 and y2 > y1 + 4:
                        fp = _face_patch_from_det(frame_bgr, x1, y1, x2, y2)
                        fe = face_insight.embed_face_optional(fp)
                        if fe is not None:
                            track_face_vecs[tid].append(fe)
                        ub = _upper_body_patch_from_det(frame_bgr, x1, y1, x2, y2)
                        if ub.size > 80:
                            ae = identity.appearance_embedding_from_patch(ub, dim=128)
                            if float(np.linalg.norm(ae)) > 1e-5:
                                track_app_vecs[tid].append(ae)
            tracks[tid].append(
                {
                    "t": t,
                    "w": _wrist_signal(kp),
                    "hip": _hip_center(kp),
                    "cx": float(kp[:, 0].mean()),
                    "h": h,
                    "w_img": w_img,
                }
            )
    pbar.close()
    if skipped_id:
        warnings.append("部分影格缺少追蹤 ID，已略過該幀（ByteTrack / Ultralytics）")
    if frame_iter and not tracks:
        warnings.append("ByteTrack 未產生穩定軌跡；已嘗試改走非追蹤模式（若仍無輸出請調整取樣或影片）")

    reid_by_track: dict[str, dict[str, Any]] = {}
    for tid in tracks:
        fe = _mean_unit_embeddings(track_face_vecs.get(tid, []))
        ae = _mean_unit_embeddings(track_app_vecs.get(tid, []))
        ass = None
        src = ""
        vec_for_reg: np.ndarray | None = None
        if fe is not None:
            ass = identity.assign_identity(fe, match_threshold=0.85)
            src = "arcface_track_mean"
            vec_for_reg = fe
        elif ae is not None:
            ass = identity.assign_identity(ae, match_threshold=0.72)
            src = "appearance_track_mean"
            vec_for_reg = ae
        if ass is not None:
            reid_by_track[str(tid)] = {
                "student_id": ass.student_id,
                "display_name": ass.display_name,
                "confidence": round(float(ass.confidence), 4),
                "status": ass.status,
                "source": src,
            }
            if learn_identities and ass.status == "new" and vec_for_reg is not None:
                identity.register_new_identity(ass.student_id, ass.display_name, vec_for_reg.astype(float).tolist())

    return tracks, warnings, reid_by_track


def _run_micro_sorted_slots(
    video_path: str | Path,
    meta: VideoMeta,
    model,
    sample_stride: int,
    beat_times: list[float],
    stop_times: list[float],
    tempo: float,
    meter_per_px: float,
    trajectory_dir: Path | None,
    refiner,
) -> tuple[list[dict[str, Any]], list[str]]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        raise FileNotFoundError(video_path)

    series: list[list[dict[str, Any]]] = []
    frame_idx = 0
    pbar = tqdm(total=meta.frame_count, desc="micro/yolo", unit="f")
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_idx % sample_stride != 0:
            frame_idx += 1
            pbar.update(1)
            continue
        t = frame_idx / max(meta.fps, 1e-6)
        h, w_img = frame.shape[:2]
        res = model(frame, verbose=False)[0]
        kps = res.keypoints.xy.cpu().numpy() if res.keypoints is not None and len(res.keypoints) else np.zeros((0, 17, 2))
        xyxy_all = res.boxes.xyxy.cpu().numpy() if res.boxes is not None and len(res.boxes) else None
        rows: list[dict[str, Any]] = []
        for i in range(kps.shape[0]):
            kp = kps[i].copy()
            box = xyxy_all[i] if xyxy_all is not None and i < xyxy_all.shape[0] else None
            kp = _refine_landmarks(refiner, frame, box, kp)
            rows.append(
                {
                    "t": t,
                    "w": _wrist_signal(kp),
                    "hip": _hip_center(kp),
                    "cx": float(kp[:, 0].mean()),
                    "h": h,
                    "w_img": w_img,
                }
            )
        rows.sort(key=lambda r: r["cx"])
        series.append(rows)
        frame_idx += 1
        pbar.update(1)
    pbar.close()
    cap.release()

    max_people = max((len(rows) for rows in series), default=0)
    if max_people == 0:
        return [], ["未偵測到可分析的人物關鍵點"]

    by_tid: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for slot in range(max_people):
        tid = slot + 1
        for frame_rows in series:
            if slot >= len(frame_rows):
                continue
            by_tid[tid].append(frame_rows[slot])
    return _series_to_children(by_tid, meta, beat_times, stop_times, tempo, meter_per_px, trajectory_dir)
