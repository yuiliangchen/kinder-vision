"""將既有的 memory/metrics/*_metrics.json 批次匯入 memory/students/<id>/sessions.jsonl。"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path

from kv.paths import metrics_dir, repo_root
from kv.student_longitudinal import append_session, load_sessions, sessions_jsonl_path

_METRICS_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})_(.+)_metrics\.json$")


def _metrics_key(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(repo_root()))
    except ValueError:
        return path.name


def _already_imported(student_id: str, import_metrics: str) -> bool:
    for row in load_sessions(student_id):
        if row.get("import_metrics") == import_metrics:
            return True
    return False


def import_metrics_file(
    path: Path,
    *,
    dry_run: bool = False,
    skip_existing: bool = True,
) -> tuple[str, str]:
    """匯入單一 metrics 檔。回傳 (狀態, 說明)。"""
    m = _METRICS_NAME.match(path.name)
    if not m:
        return ("skip", f"檔名不符合 YYYY-MM-DD_<id>_metrics.json：{path.name}")
    run_date, student_id = m.group(1), m.group(2)
    try:
        child = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        return ("error", f"{path}: {e}")

    imp_key = _metrics_key(path)
    if skip_existing and _already_imported(student_id, imp_key):
        return ("dup", f"已存在 import_metrics={imp_key}")

    recorded = datetime_from_mtime(path)
    video = f"import:{imp_key}"
    if dry_run:
        return ("dry", f"將寫入 {sessions_jsonl_path(student_id)} ← {imp_key}")

    append_session(
        student_id=student_id,
        child=child,
        video_path=video,
        run_date=run_date,
        recorded_at_iso=recorded,
        extra_fields={"import_metrics": imp_key},
    )
    return ("ok", imp_key)


def datetime_from_mtime(path: Path) -> str:
    try:
        ts = path.stat().st_mtime
    except OSError:
        return datetime.now().isoformat(timespec="seconds")
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="批次匯入 memory/metrics/*_metrics.json 至跨影片累積檔 sessions.jsonl（依 import_metrics 去重）"
    )
    ap.add_argument(
        "--memory",
        type=Path,
        default=None,
        help="掃描目錄（預設專案 memory/metrics/）",
    )
    ap.add_argument("--dry-run", action="store_true", help="只列出將匯入的項目，不寫檔")
    ap.add_argument(
        "--force",
        action="store_true",
        help="即使已從同一 metrics 檔匯入過仍再追加一筆（預設會跳過重複）",
    )
    args = ap.parse_args()
    root = (args.memory or metrics_dir()).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"不是目錄：{root}")

    paths = sorted(root.glob("*_metrics.json"))
    if not paths:
        print(f"未找到 *_metrics.json：{root}")
        return

    skip_existing = not args.force
    n_ok = n_dup = n_skip = n_err = n_dry = 0
    for p in paths:
        status, msg = import_metrics_file(p, dry_run=args.dry_run, skip_existing=skip_existing)
        if status == "ok":
            n_ok += 1
            print(f"[ok] {p.name} → {msg}")
        elif status == "dry":
            n_dry += 1
            print(f"[dry-run] {msg}")
        elif status == "dup":
            n_dup += 1
            print(f"[skip] {p.name} {msg}")
        elif status == "skip":
            n_skip += 1
            print(f"[skip] {p.name} {msg}")
        else:
            n_err += 1
            print(f"[error] {p.name} {msg}")

    tail = "（dry-run，未寫入）" if args.dry_run else ""
    print(f"完成：ok={n_ok} dry={n_dry} dup={n_dup} skip={n_skip} error={n_err} {tail}".rstrip())


if __name__ == "__main__":
    main()
