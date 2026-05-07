from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from ultralytics import YOLO

from src import edu_advisor, face_insight, identity, llm_edu, macro_analytics, metrics_checker, micro_analytics
from src import student_longitudinal
from src.report_pdf import export_combined_report_pdf
from src.paths import memory_dir, metrics_dir, reports_dir, tmp_dir
from src.timecode import format_mmss, parse_timecode
from src.video_ingest import load_audio_mono, read_video_meta


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def _identity_pass(video_path: Path, model: YOLO, learn_identities: bool) -> list[dict[str, Any]]:
    meta = read_video_meta(video_path)
    mid = max(0, int(meta.frame_count * 0.5))
    cap = cv2.VideoCapture(str(video_path))
    cap.set(cv2.CAP_PROP_POS_FRAMES, mid)
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        return []
    res = model(frame, verbose=False)[0]
    xyxy = res.boxes.xyxy.cpu().numpy() if res.boxes is not None and len(res.boxes) else np.zeros((0, 4))
    h, w = frame.shape[:2]
    dets: list[tuple[float, np.ndarray]] = []
    for i in range(xyxy.shape[0]):
        x1, y1, x2, y2 = [int(max(0, t)) for t in xyxy[i]]
        x2, y2 = min(w, x2), min(h, y2)
        patch = frame[y1:y2, x1:x2]
        h_box = max(1, y2 - y1)
        y2f = min(h, int(y1 + 0.42 * h_box))
        face_patch = frame[y1:y2f, x1:x2]
        cx = float((x1 + x2) * 0.5)
        dets.append((cx, patch, face_patch))
    dets.sort(key=lambda t: t[0])
    items: list[dict[str, Any]] = []
    for slot, (_cx, patch, face_patch) in enumerate(dets):
        arc = face_insight.embed_face_optional(face_patch)
        emb = arc if arc is not None else identity.appearance_embedding_from_patch(patch, dim=128)
        ass = identity.assign_identity(emb, match_threshold=0.85)
        if learn_identities and ass.status == "new":
            identity.register_new_identity(ass.student_id, ass.display_name, emb.astype(float).tolist())
        items.append(
            {
                "slot": slot,
                "student_id": ass.student_id,
                "display_name": ass.display_name,
                "confidence": ass.confidence,
                "status": ass.status,
            }
        )
    return items


def _slot_index_from_child_id(child_id: Any) -> int:
    """槽位對齊（child_id 為數字字串或舊版單字母）。"""
    s = str(child_id).strip()
    if s.isdigit():
        return max(0, int(s) - 1)
    if len(s) == 1:
        o = ord(s.upper())
        if ord("A") <= o <= ord("Z"):
            return o - ord("A")
    return 0


def _merge_child_identities(micro: dict[str, Any], id_map: list[dict[str, Any]]) -> None:
    """整片軌跡 ReID 優先，否則回退至片中點＋槽位對齊。"""
    reid = micro.get("reid_by_track") or {}
    for c in micro.get("children", []) or []:
        tid = c.get("track_id")
        row = reid.get(str(tid)) if tid is not None else None
        if row and row.get("student_id"):
            c["student_id"] = row["student_id"]
            if row.get("display_name"):
                c["display_name"] = row["display_name"]
            c["identity_source"] = row.get("source", "reid")
            continue
        idx = _slot_index_from_child_id(c.get("child_id"))
        if idx < len(id_map):
            im = id_map[idx]
            if im.get("student_id"):
                c["student_id"] = im["student_id"]
            if im.get("display_name"):
                c["display_name"] = im["display_name"]
            c["identity_source"] = "midframe_slot"


def _normalize_micro_display_names(micro: dict[str, Any]) -> None:
    """對外一律使用數字編號稱呼（與 student_id / 軌跡槽位一致）。"""
    for row in (micro.get("reid_by_track") or {}).values():
        if isinstance(row, dict) and row.get("student_id"):
            lab = identity.display_label_for_student_id(str(row["student_id"]))
            if lab:
                row["display_name"] = lab
    for c in micro.get("children", []) or []:
        c["display_name"] = identity.display_label_for_child(c.get("student_id"), c.get("child_id"))


def _pose_backend_label_zh(pose_backend: str | None) -> str:
    pb = pose_backend or "yolo_only"
    return {
        "yolo+mediapipe_pose": "YOLO + MediaPipe Pose",
        "yolo+mediapipe_holistic": "YOLO + MediaPipe Holistic",
        "yolo+mediapipe": "YOLO + MediaPipe",
        "yolo_only": "僅 YOLO",
    }.get(pb, "僅 YOLO")


def run_full_pipeline(
    video_path: str | Path,
    model_path: str = "yolov8n-pose.pt",
    sample_stride: int = 3,
    learn_identities: bool = False,
    use_tracking: bool = True,
    t0: str | None = None,
    t1: str | None = None,
    use_mediapipe: bool | None = True,
    pose_mode: str = "pose",
    use_llm: bool = True,
    use_video_reid: bool = True,
    emit_pdf: bool = False,
    accumulate_sessions: bool = True,
) -> dict[str, Path]:
    orig_video_path = Path(video_path).expanduser().resolve()
    if not orig_video_path.is_file():
        raise FileNotFoundError(orig_video_path)

    memory_dir()
    rd = reports_dir()
    td = tmp_dir()
    run_started = datetime.now()
    date_s = run_started.strftime("%Y-%m-%d")
    pdf_stamp = run_started.strftime("%Y-%m-%d_%H-%M-%S")

    full_meta = read_video_meta(orig_video_path)
    segment_path: Path | None = None
    work_path = orig_video_path
    win_t0_sec: float | None = None
    win_t1_sec: float | None = None

    if t0 is not None or t1 is not None:
        from src.segment import export_video_segment

        win_t0_sec = parse_timecode(t0) if t0 is not None else 0.0
        win_t1_sec = parse_timecode(t1) if t1 is not None else float(full_meta.duration_sec)
        win_t0_sec = max(0.0, min(win_t0_sec, float(full_meta.duration_sec)))
        win_t1_sec = max(0.0, min(win_t1_sec, float(full_meta.duration_sec)))
        if win_t1_sec <= win_t0_sec + 0.25:
            raise ValueError("分析區間無效：請確認 t0 < t1，且區間至少約 0.25 秒")
        segment_path = td / "kinder-segment.mp4"
        export_video_segment(orig_video_path, win_t0_sec, win_t1_sec, segment_path)
        work_path = segment_path

    model = YOLO(model_path)
    meta = read_video_meta(work_path)
    id_map = _identity_pass(work_path, model, learn_identities=learn_identities)
    _write_json(td / "kinder-identity-map.json", {"items": id_map})

    heatmap_path = td / "kinder-heatmap.png"
    macro = macro_analytics.run_macro(
        work_path, meta, model, sample_stride=sample_stride, heatmap_png=heatmap_path
    )
    if win_t0_sec is not None and win_t1_sec is not None:
        macro["analysis_window_original"] = f"{format_mmss(win_t0_sec)} — {format_mmss(win_t1_sec)}"
        macro["analysis_window_original_sec"] = [win_t0_sec, win_t1_sec]
    _write_json(td / "kinder-macro-result.json", macro)
    (rd / f"{date_s}-kinder-macro.md").write_text(
        "# 巨觀層分析（機讀摘要）\n\n```json\n"
        + json.dumps(macro, ensure_ascii=False, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )

    audio_y, sr = load_audio_mono(work_path)
    micro = micro_analytics.run_micro(
        work_path,
        meta,
        model,
        audio_y,
        sr,
        sample_stride=max(2, sample_stride - 1),
        use_tracking=use_tracking,
        trajectory_dir=td,
        use_mediapipe=use_mediapipe,
        pose_mode=pose_mode,
        use_video_reid=use_video_reid,
        learn_identities=learn_identities,
    )
    if win_t0_sec is not None and win_t1_sec is not None:
        micro["analysis_window_original"] = f"{format_mmss(win_t0_sec)} — {format_mmss(win_t1_sec)}"
        micro["analysis_window_original_sec"] = [win_t0_sec, win_t1_sec]

    _merge_child_identities(micro, id_map)
    _normalize_micro_display_names(micro)

    metrics = metrics_checker.run_metrics(macro, micro)

    edu_md = edu_advisor.render_edu_markdown(str(orig_video_path), meta.duration_sec, macro, micro, metrics)
    if use_llm:
        edu_md, llm_warn, llm_used = llm_edu.augment_edu_report(
            edu_md,
            video_path=str(orig_video_path),
            duration_sec=float(meta.duration_sec),
            macro=macro,
            micro=micro,
            metrics=metrics,
        )
        micro["llm_warnings"] = llm_warn
        micro["llm_section_appended"] = llm_used
    else:
        micro["llm_warnings"] = []
        micro["llm_section_appended"] = False

    _write_json(td / "kinder-micro-result.json", micro)
    (rd / f"{date_s}-kinder-micro.md").write_text(
        "# 微觀層分析（機讀摘要）\n\n```json\n"
        + json.dumps(micro, ensure_ascii=False, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )

    _write_json(td / "kinder-metrics-check.json", metrics)
    (rd / f"{date_s}-kinder-metrics.md").write_text(
        "# 指標核查（機讀摘要）\n\n```json\n"
        + json.dumps(metrics, ensure_ascii=False, indent=2)
        + "\n```\n",
        encoding="utf-8",
    )

    (td / "kinder-edu-report.md").write_text(edu_md, encoding="utf-8")
    (rd / f"{date_s}-kinder-edu-report.md").write_text(edu_md, encoding="utf-8")

    recorded_at = datetime.now().isoformat(timespec="seconds")
    for c in micro.get("children", []) or []:
        sid = c.get("student_id")
        fname_sid = sid or f"anon_{c.get('child_id', 'X')}"
        out = metrics_dir() / f"{date_s}_{fname_sid}_metrics.json"
        _write_json(out, c)
        if accumulate_sessions:
            student_longitudinal.append_session(
                student_id=fname_sid,
                child=c,
                video_path=str(orig_video_path),
                run_date=date_s,
                recorded_at_iso=recorded_at,
            )

    track_zh = "ByteTrack" if micro.get("tracking") == "bytetrack" else "槽位對齊（無追蹤）"
    pose_zh = _pose_backend_label_zh(str(micro.get("pose_backend", "")))
    win_line = ""
    if micro.get("analysis_window_original"):
        win_line = f"\n- 原片區間：{micro['analysis_window_original']}"
    consolidated = [
        "# 📊 幼兒行為分析報告（自動彙總）",
        "",
        f"- 分析片長：{int(meta.duration_sec // 60)} 分 {int(meta.duration_sec % 60)} 秒（送入模型之片段）",
        f"- 追蹤模式：{track_zh}（vid_stride={micro.get('vid_stride', '—')}）；姿勢：{pose_zh}{win_line}",
        f"- 分析時間：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- 整體狀態：{metrics.get('overall_status', '')}",
        "",
        "## 指標摘要",
        "",
        f"- 節奏同步：{metrics['micro_metrics']['sync_score']['status']}（{metrics['micro_metrics']['sync_score']['value_ms']} ms）",
        f"- 身體穩定：{metrics['micro_metrics']['stability_score']['status']}（{metrics['micro_metrics']['stability_score']['value_cm']} cm）",
        f"- 動作流暢：{metrics['micro_metrics']['fluency_score']['status']}（jerk 代理 {metrics['micro_metrics']['fluency_score']['value_jerk']}）",
        "",
        "*詳見 tmp/kinder-*、reports/ 同日彙總，以及 reports/metrics/ 個別孩童 metrics。*",
    ]
    analysis_path = rd / f"{date_s}-kinder-analysis.md"
    analysis_path.write_text("\n".join(consolidated), encoding="utf-8")

    pdf_tmp_out: Path | None = None
    pdf_reports_out: Path | None = None
    if emit_pdf:
        pdf_tmp = td / "kinder-report.pdf"
        pdf_saved = rd / f"{pdf_stamp}-kinder-report.pdf"
        export_combined_report_pdf(analysis_path, td / "kinder-edu-report.md", pdf_tmp)
        pdf_saved.write_bytes(pdf_tmp.read_bytes())
        pdf_tmp_out = pdf_tmp
        pdf_reports_out = pdf_saved

    out: dict[str, Path] = {
        "macro_json": td / "kinder-macro-result.json",
        "micro_json": td / "kinder-micro-result.json",
        "metrics_json": td / "kinder-metrics-check.json",
        "edu_md": td / "kinder-edu-report.md",
        "reports_edu": rd / f"{date_s}-kinder-edu-report.md",
        "reports_analysis": analysis_path,
        "heatmap_png": Path(macro.get("heatmap_png", heatmap_path)),
    }
    if segment_path is not None:
        out["segment_video"] = segment_path
    if pdf_tmp_out is not None and pdf_reports_out is not None:
        out["report_pdf"] = pdf_tmp_out
        out["reports_pdf"] = pdf_reports_out
    return out
