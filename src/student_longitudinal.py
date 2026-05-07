"""跨影片累積同一 student_id（或 anon）的微觀指標，供個人長期報告使用。"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from src.paths import students_dir


def student_slug(student_id: str) -> str:
    s = (student_id or "").strip()
    if not s:
        return "unknown"
    out = re.sub(r"[^a-zA-Z0-9._-]", "_", s)
    return (out[:160] or "unknown").strip("._") or "unknown"


def sessions_jsonl_path(student_id: str) -> Path:
    d = students_dir() / student_slug(student_id)
    d.mkdir(parents=True, exist_ok=True)
    return d / "sessions.jsonl"


def _child_for_archive(child: dict[str, Any]) -> dict[str, Any]:
    c = dict(child)
    ti = c.get("trajectory_image")
    if isinstance(ti, str) and ti and ("/" in ti or "\\" in ti):
        c["trajectory_image"] = Path(ti).name
    return c


def append_session(
    *,
    student_id: str,
    child: dict[str, Any],
    video_path: str,
    run_date: str,
    recorded_at_iso: str | None = None,
    extra_fields: dict[str, Any] | None = None,
) -> Path:
    """附加一筆分析紀錄（append-only JSONL）。"""
    path = sessions_jsonl_path(student_id)
    rec: dict[str, Any] = {
        "recorded_at": recorded_at_iso or datetime.now().isoformat(timespec="seconds"),
        "run_date": run_date,
        "video": video_path,
        "display_name": child.get("display_name"),
        "identity_source": child.get("identity_source"),
        "child": _child_for_archive(child),
    }
    if extra_fields:
        rec.update(extra_fields)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return path


def load_sessions(student_id: str) -> list[dict[str, Any]]:
    p = sessions_jsonl_path(student_id)
    if not p.is_file():
        return []
    rows: list[dict[str, Any]] = []
    # JSONL: split on '\n' only. str.splitlines() also splits on U+0085 etc., which can
    # appear inside JSON strings (e.g. unusual child_id glyphs) and corrupt parsing.
    for line in p.read_text(encoding="utf-8").split("\n"):
        line = line.strip("\r").strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def list_student_slugs() -> list[str]:
    root = students_dir()
    if not root.is_dir():
        return []
    return sorted(d.name for d in root.iterdir() if d.is_dir())
