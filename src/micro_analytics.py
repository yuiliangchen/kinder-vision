from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
import librosa
import numpy as np
from scipy.signal import savgol_filter
from tqdm import tqdm

from src import face_insight, identity
from src.mediapipe_holistic import try_create_holistic_refiner
from src.mediapipe_pose import try_create_refiner
from src.video_ingest import VideoMeta


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


class _UnionFind:
    def __init__(self, items: list[int]) -> None:
        self.parent = {i: i for i in items}

    def find(self, x: int) -> int:
        while self.parent[x] != x:
            self.parent[x] = self.parent[self.parent[x]]
            x = self.parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb

    def groups(self) -> dict[int, list[int]]:
        out: dict[int, list[int]] = defaultdict(list)
        for x in self.parent:
            out[self.find(x)].append(x)
        return dict(out)


def _cluster_tracks_by_face(
    tids: list[int],
    track_face_vecs: dict[int, list[np.ndarray]],
    track_app_vecs: dict[int, list[np.ndarray]],
    track_series: dict[int, list[dict[str, Any]]] | None = None,
    *,
    face_threshold: float = 0.50,
    app_threshold: float = 0.88,
    overlap_tolerance: float = 0.25,
    target_clusters: int | None = None,
) -> dict[int, int]:
    """Merge ByteTrack ids that very likely belong to the same person.

    Returns a mapping ``track_id -> cluster_root_id``. Roots are themselves
    valid track ids (chosen as the smallest member of each group).

    Strategy:
        1. Average each track's ArcFace embeddings (if any) into a unit vector.
        2. **Hard exclusion**: if two tracks overlap on the timeline by more
           than ``overlap_tolerance`` seconds, they cannot be the same person
           regardless of similarity — ByteTrack already separated them within
           that window. This is the most reliable signal we have.
        3. Among non-overlapping pairs, union those whose face cosine
           similarity >= ``face_threshold``. The default 0.62 is calibrated
           for buffalo_l on classroom footage where small / low-resolution
           faces produce inflated baseline similarities (~0.4–0.5 between
           different children).
        4. As a softer fallback, also union pairs whose appearance histogram
           cosine >= ``app_threshold`` AND whose face evidence (if any) does
           not reject the merge.
    """
    if not tids:
        return {}

    # Pre-compute time intervals for each track so we can reject overlapping
    # pairs in O(1) during the pairwise loop.
    intervals: dict[int, tuple[float, float]] = {}
    if track_series:
        for tid in tids:
            rows = track_series.get(tid) or []
            ts = [float(r.get("t", 0.0)) for r in rows if r.get("t") is not None]
            if ts:
                intervals[tid] = (min(ts), max(ts))

    def _overlaps(a: int, b: int) -> bool:
        ia, ib = intervals.get(a), intervals.get(b)
        if ia is None or ib is None:
            return False
        a0, a1 = ia
        b0, b1 = ib
        overlap = min(a1, b1) - max(a0, b0)
        return overlap > overlap_tolerance

    # Pre-compute candidate edges sorted by descending similarity. We then
    # accept them greedily, only unifying two clusters when **no** member of
    # the resulting group would overlap with another member — this prevents
    # transitive merges from collapsing simultaneously-visible tracks.
    face_means: dict[int, np.ndarray] = {}
    for tid in tids:
        m = _mean_unit_embeddings(track_face_vecs.get(tid, []))
        if m is not None:
            face_means[tid] = m
    app_means: dict[int, np.ndarray] = {}
    for tid in tids:
        m = _mean_unit_embeddings(track_app_vecs.get(tid, []))
        if m is not None:
            app_means[tid] = m

    sorted_face_tids = sorted(face_means.keys())
    face_evidence: dict[tuple[int, int], float] = {}
    edges: list[tuple[float, int, int, str]] = []  # (sim, ti, tj, source)
    for i, ti in enumerate(sorted_face_tids):
        for tj in sorted_face_tids[i + 1 :]:
            if _overlaps(ti, tj):
                continue
            sim = float(np.dot(face_means[ti], face_means[tj]))
            face_evidence[(ti, tj)] = sim
            if sim >= face_threshold:
                edges.append((sim, ti, tj, "face"))
    sorted_app_tids = sorted(app_means.keys())
    for i, ti in enumerate(sorted_app_tids):
        for tj in sorted_app_tids[i + 1 :]:
            if _overlaps(ti, tj):
                continue
            key = (min(ti, tj), max(ti, tj))
            face_sim = face_evidence.get(key)
            if face_sim is not None and face_sim < face_threshold * 0.55:
                continue
            sim = float(np.dot(app_means[ti], app_means[tj]))
            if sim >= app_threshold:
                # Bias appearance edges below face edges with the same number.
                edges.append((sim - 0.05, ti, tj, "app"))

    # Build *all* candidate edges between non-overlapping pairs (even those
    # below the static threshold) so that target-driven clustering can keep
    # merging until it hits ``target_clusters``. Pairs above the static
    # threshold are always considered; lower-similarity pairs are only used
    # when target_clusters demands further consolidation.
    all_edges: list[tuple[float, int, int]] = []
    if target_clusters is not None:
        for i, ti in enumerate(sorted_face_tids):
            for tj in sorted_face_tids[i + 1 :]:
                if _overlaps(ti, tj):
                    continue
                key = (min(ti, tj), max(ti, tj))
                sim = face_evidence.get(key)
                if sim is None:
                    sim = float(np.dot(face_means[ti], face_means[tj]))
                all_edges.append((sim, ti, tj))
        all_edges.sort(key=lambda e: e[0], reverse=True)

    edges.sort(key=lambda e: e[0], reverse=True)

    uf = _UnionFind(list(tids))
    cluster_members: dict[int, set[int]] = {tid: {tid} for tid in tids}

    def _can_merge(ra: int, rb: int, *, allow_brief_overlap: bool = False) -> bool:
        # Reject if a cross-cluster pair overlaps too much. ByteTrack
        # occasionally double-registers a person for ~1–2 frames around a
        # crossing, so when ``allow_brief_overlap`` is enabled (target-driven
        # phase) we tolerate up to ``overlap_tolerance`` seconds of overlap
        # between any individual pair as long as **no** pair exceeds an
        # "obviously two people" budget.
        ma, mb = cluster_members[ra], cluster_members[rb]
        hard_budget = max(overlap_tolerance, 1.0)
        for x in ma:
            ix = intervals.get(x)
            if ix is None:
                continue
            for y in mb:
                iy = intervals.get(y)
                if iy is None:
                    continue
                ov = min(ix[1], iy[1]) - max(ix[0], iy[0])
                if allow_brief_overlap:
                    if ov > hard_budget:
                        return False
                else:
                    if ov > overlap_tolerance:
                        return False
        return True

    def _do_merge(ti: int, tj: int, *, allow_brief_overlap: bool = False) -> bool:
        ra, rb = uf.find(ti), uf.find(tj)
        if ra == rb:
            return False
        if not _can_merge(ra, rb, allow_brief_overlap=allow_brief_overlap):
            return False
        uf.union(ti, tj)
        new_root = uf.find(ti)
        other_root = ra if new_root == rb else rb
        cluster_members[new_root] = cluster_members[ra] | cluster_members[rb]
        if other_root in cluster_members and other_root != new_root:
            del cluster_members[other_root]
        return True

    for sim, ti, tj, _src in edges:
        _do_merge(ti, tj)

    # Target-driven extra merging: greedily consume the next-highest
    # similarity edge as long as we are above ``target_clusters`` and the
    # merge respects the temporal-overlap constraint. Edges below an
    # absolute floor (0.30) are still rejected to avoid merging clearly
    # different people just to hit a number.
    if target_clusters is not None:
        # Allow the floor to dip well below the static threshold when the
        # caller insists on a specific identity count. 0.18 still discards
        # near-orthogonal embeddings (clearly different people).
        min_floor = 0.18
        idx = 0
        while len(cluster_members) > target_clusters and idx < len(all_edges):
            sim, ti, tj = all_edges[idx]
            idx += 1
            if sim < min_floor:
                break
            _do_merge(ti, tj, allow_brief_overlap=True)

    groups = uf.groups()
    mapping: dict[int, int] = {}
    for members in groups.values():
        root = min(members)
        for m in members:
            mapping[m] = root
    return mapping


def _classify_adult_tracks(
    track_face_ages: dict[int, list[float]],
    cluster_map: dict[int, int],
    *,
    adult_age_threshold: float = 18.0,
    min_samples: int = 2,
) -> set[int]:
    """Return the set of cluster roots that look like adults (age-based).

    Aggregates all face-age samples that fall under the same cluster root and
    flags clusters whose median estimated age exceeds ``adult_age_threshold``.
    Clusters with too few age samples remain unflagged ("unknown" → keep).

    Note: buffalo_l face age is unreliable on classroom footage (low
    resolution / small faces collapse onto the 25–35 range). Prefer
    :func:`_classify_adult_tracks_by_height` whenever bbox heights are
    available.
    """
    by_root: dict[int, list[float]] = defaultdict(list)
    for tid, ages in track_face_ages.items():
        root = cluster_map.get(tid, tid)
        by_root[root].extend(float(a) for a in ages if a is not None)
    adults: set[int] = set()
    for root, ages in by_root.items():
        if len(ages) < min_samples:
            continue
        if float(np.median(ages)) >= adult_age_threshold:
            adults.add(root)
    return adults


def _classify_adult_tracks_by_height(
    merged_series: dict[int, list[dict[str, Any]]],
    *,
    adult_ratio: float = 1.35,
    min_samples: int = 4,
) -> tuple[set[int], dict[int, float]]:
    """Identify cluster roots that look like adults from bbox height alone.

    For each cluster, compute the median ``box_h`` across all of its frames.
    Then take the **per-cluster median** of those values as the population
    baseline (this is robust to a few unusually tall children) and flag any
    cluster whose median height exceeds ``adult_ratio`` × baseline.

    Returns ``(adult_roots, height_by_root)`` so callers can surface the
    underlying numbers in warnings / reports.
    """
    height_by_root: dict[int, float] = {}
    for root, rows in merged_series.items():
        heights = [float(r.get("box_h", 0.0)) for r in rows if r.get("box_h")]
        if len(heights) < min_samples:
            continue
        height_by_root[root] = float(np.median(heights))
    if not height_by_root:
        return set(), {}
    baseline = float(np.median(list(height_by_root.values())))
    if baseline <= 0:
        return set(), height_by_root
    adults = {
        root for root, h in height_by_root.items() if h >= adult_ratio * baseline
    }
    return adults, height_by_root


def _merge_track_series(
    tracks: dict[int, list[dict[str, Any]]],
    cluster_map: dict[int, int],
) -> dict[int, list[dict[str, Any]]]:
    """Concatenate per-frame samples for tracks that share a cluster root."""
    if not cluster_map:
        return tracks
    merged: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for tid, series in tracks.items():
        root = cluster_map.get(tid, tid)
        merged[root].extend(series)
    for root in merged:
        merged[root].sort(key=lambda s: float(s.get("t", 0.0)))
    return dict(merged)


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
            from src.viz import save_trajectory_png

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
    expected_children: int | None = None,
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
            (
                series_by_tid,
                wmsg,
                reid_by_track,
                track_face_vecs,
                track_app_vecs,
                track_face_ages,
            ) = _collect_micro_tracking(
                model,
                video_path,
                meta,
                sample_stride,
                refiner=refiner,
                use_video_reid=use_video_reid,
                learn_identities=learn_identities,
            )

            # Drop tracks too short to yield reliable per-child metrics before
            # clustering — ByteTrack often emits 1–2 frame ghosts during
            # crossings that would otherwise inflate the identity count.
            min_frames_for_cluster = 8
            cluster_input = {
                tid: rows
                for tid, rows in series_by_tid.items()
                if len(rows) >= min_frames_for_cluster
            }
            face_input = {tid: v for tid, v in track_face_vecs.items() if tid in cluster_input}
            app_input = {tid: v for tid, v in track_app_vecs.items() if tid in cluster_input}
            # If the caller provided ``expected_children`` we still need room
            # for the adults that will be filtered out later, so target a
            # slightly larger cluster count than the requested child count.
            cluster_target: int | None = None
            if expected_children is not None and expected_children > 0:
                cluster_target = expected_children + 4  # rough headroom for adults
            cluster_map = _cluster_tracks_by_face(
                list(cluster_input.keys()),
                face_input,
                app_input,
                track_series=cluster_input,
                target_clusters=cluster_target,
            )
            # Tracks that were excluded from clustering keep their own identity
            # so we do not silently drop their motion data; they will appear
            # as singletons in the merged dictionary.
            for tid in series_by_tid:
                cluster_map.setdefault(tid, tid)
            merged_series = _merge_track_series(series_by_tid, cluster_map)
            # NOTE: buffalo_l face-age is unreliable on classroom footage
            # (every face collapses onto the 25–35 range), so we use bbox
            # height instead — adults are noticeably taller than children
            # under the same camera framing. The age-based path is kept as
            # a fallback for cases where heights are missing.
            adult_roots, _height_by_root = _classify_adult_tracks_by_height(merged_series)
            adult_filter_method = "bbox_height" if adult_roots else "face_age"
            if not adult_roots:
                adult_roots = _classify_adult_tracks(track_face_ages, cluster_map)
            adults_filtered_count = sum(
                1 for root in merged_series.keys() if root in adult_roots
            )
            child_series = {
                root: ser for root, ser in merged_series.items() if root not in adult_roots
            }

            cluster_warnings: list[str] = []
            n_raw = len(series_by_tid)
            n_clusters = len(merged_series)
            n_children = len(child_series)
            if n_raw and n_clusters < n_raw:
                cluster_warnings.append(
                    f"軌跡合併：{n_raw} 條 ByteTrack 軌跡 → {n_clusters} 個身分（face/appearance ReID）"
                )
            if adults_filtered_count:
                method_zh = (
                    "bbox 高度中位數 ≥ 1.35× 班級中位"
                    if adult_filter_method == "bbox_height"
                    else "buffalo_l face age 中位數 ≥ 18"
                )
                cluster_warnings.append(
                    f"估計為成人並排除：{adults_filtered_count} 個身分（{method_zh}）"
                )

            children, w2 = _series_to_children(
                child_series, meta, beat_times, stop_times, bpm_hint, meter_per_px, trajectory_dir
            )
            # Only retain reid_by_track entries for surviving cluster roots so
            # downstream consumers see one row per identity, not per raw track.
            reid_by_root: dict[str, dict[str, Any]] = {}
            for tid, info in reid_by_track.items():
                try:
                    tid_int = int(tid)
                except (TypeError, ValueError):
                    reid_by_root[str(tid)] = info
                    continue
                root = cluster_map.get(tid_int, tid_int)
                if root in adult_roots:
                    continue
                reid_by_root.setdefault(str(root), info)

            warnings = mp_warn + list(wmsg) + list(w2) + cluster_warnings
            out = {
                "children": children,
                "bpm_hint": bpm_hint,
                "warnings": warnings,
                "tracking": "bytetrack",
                "vid_stride": sample_stride,
                "pose_backend": pose_backend,
                "reid_by_track": reid_by_root,
                "cluster_summary": {
                    "raw_tracks": n_raw,
                    "merged_identities": n_clusters,
                    "adults_excluded": adults_filtered_count,
                    "children_kept": n_children,
                },
            }
            if not children and not series_by_tid:
                # Only fall back to slot-aligned mode when ByteTrack itself
                # produced nothing; otherwise we trust the cluster output
                # rather than silently bypass identity merging.
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
                    expected_children=expected_children,
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
) -> tuple[
    dict[int, list[dict[str, Any]]],
    list[str],
    dict[str, dict[str, Any]],
    dict[int, list[np.ndarray]],
    dict[int, list[np.ndarray]],
    dict[int, list[float]],
]:
    warnings: list[str] = []
    tracks: dict[int, list[dict[str, Any]]] = defaultdict(list)
    track_face_vecs: dict[int, list[np.ndarray]] = defaultdict(list)
    track_app_vecs: dict[int, list[np.ndarray]] = defaultdict(list)
    track_face_ages: dict[int, list[float]] = defaultdict(list)
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
                        fea = face_insight.embed_face_with_age_optional(fp)
                        if fea is not None:
                            fe, age_val = fea
                            track_face_vecs[tid].append(fe)
                            if age_val is not None:
                                track_face_ages[tid].append(float(age_val))
                        ub = _upper_body_patch_from_det(frame_bgr, x1, y1, x2, y2)
                        if ub.size > 80:
                            ae = identity.appearance_embedding_from_patch(ub, dim=128)
                            if float(np.linalg.norm(ae)) > 1e-5:
                                track_app_vecs[tid].append(ae)
            box_h = 0.0
            if box is not None and len(box) >= 4:
                box_h = float(max(0.0, float(box[3]) - float(box[1])))
            tracks[tid].append(
                {
                    "t": t,
                    "w": _wrist_signal(kp),
                    "hip": _hip_center(kp),
                    "cx": float(kp[:, 0].mean()),
                    "h": h,
                    "w_img": w_img,
                    "box_h": box_h,
                }
            )
    pbar.close()
    if skipped_id:
        warnings.append("部分影格缺少追蹤 ID，已略過該幀（ByteTrack / Ultralytics）")
    if frame_iter and not tracks:
        warnings.append("ByteTrack 未產生穩定軌跡；已嘗試改走非追蹤模式（若仍無輸出請調整取樣或影片）")

    reid_by_track: dict[str, dict[str, Any]] = {}
    # Fallback labelling: give every track a distinct display name when identity
    # match fails (otherwise everyone collapses onto "孩子 1" because the in-memory
    # DB starts empty and `assign_identity` re-uses the next free index).
    # Sort track ids deterministically so output ordering is stable across runs.
    def _track_sort_key(t: Any) -> tuple[int, Any]:
        s = str(t)
        return (0, int(s)) if s.isdigit() else (1, s)

    sorted_tids = sorted(tracks.keys(), key=_track_sort_key)
    seen_student_ids: dict[str, str] = {}
    fallback_counter = 0
    for tid in sorted_tids:
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
        if ass is None:
            # No embedding at all — synthesize a per-track fallback identity
            fallback_counter += 1
            sid = f"T_{tid}"
            reid_by_track[str(tid)] = {
                "student_id": sid,
                "display_name": f"孩子 {fallback_counter}",
                "confidence": 0.0,
                "status": "new",
                "source": "track_fallback",
            }
            continue

        sid = ass.student_id
        display_name = ass.display_name
        if ass.status == "new":
            # Each new track must get its own label even when the identity DB
            # has not been persisted yet. Tag the synthetic id with the track
            # id so two new tracks never collide on `S_NEW_0001`.
            sid = f"{ass.student_id}_T{tid}"
            fallback_counter += 1
            display_name = f"孩子 {fallback_counter}"
        elif sid in seen_student_ids:
            # Two tracks matched the same returning identity — keep distinct
            # display labels so per-child reports do not get merged downstream.
            display_name = f"{seen_student_ids[sid]}（軌跡 {tid}）"
        else:
            seen_student_ids[sid] = display_name

        reid_by_track[str(tid)] = {
            "student_id": sid,
            "display_name": display_name,
            "confidence": round(float(ass.confidence), 4),
            "status": ass.status,
            "source": src,
        }
        if learn_identities and ass.status == "new" and vec_for_reg is not None:
            identity.register_new_identity(sid, display_name, vec_for_reg.astype(float).tolist())

    return tracks, warnings, reid_by_track, dict(track_face_vecs), dict(track_app_vecs), dict(track_face_ages)


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
