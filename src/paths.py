from __future__ import annotations

import os
import pathlib


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def _dir_from_env(env_name: str, default: pathlib.Path) -> pathlib.Path:
    raw = (os.environ.get(env_name) or "").strip()
    if not raw:
        p = default
    else:
        p = pathlib.Path(raw).expanduser()
        if not p.is_absolute():
            p = (repo_root() / p).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def memory_dir() -> pathlib.Path:
    return _dir_from_env("KINDER_MEMORY_DIR", repo_root() / "memory")


def reports_dir() -> pathlib.Path:
    """分析輸出（同日 Markdown、PDF、metrics、個人長期報告 students/）。"""
    return _dir_from_env("KINDER_REPORTS_DIR", repo_root() / "reports")


def metrics_dir() -> pathlib.Path:
    """個別孩童 metrics JSON：`YYYY-MM-DD_<student_id>_metrics.json`。"""
    p = reports_dir() / "metrics"
    p.mkdir(parents=True, exist_ok=True)
    return p


def tmp_dir() -> pathlib.Path:
    return _dir_from_env("KINDER_TMP_DIR", repo_root() / "tmp")


def identity_db_path() -> pathlib.Path:
    return memory_dir() / "identity_features.db.json"


def students_dir() -> pathlib.Path:
    """跨影片累積紀錄：`memory/students/<slug>/sessions.jsonl`。"""
    p = memory_dir() / "students"
    p.mkdir(parents=True, exist_ok=True)
    return p


def student_reports_dir() -> pathlib.Path:
    """個人長期報告輸出（Markdown／PDF）：`reports/students/<slug>/`。"""
    p = reports_dir() / "students"
    p.mkdir(parents=True, exist_ok=True)
    return p
