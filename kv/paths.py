from __future__ import annotations

import pathlib


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def memory_dir() -> pathlib.Path:
    p = repo_root() / "memory"
    p.mkdir(parents=True, exist_ok=True)
    return p


def metrics_dir() -> pathlib.Path:
    """個別孩童 metrics JSON：`YYYY-MM-DD_<student_id>_metrics.json`。"""
    p = memory_dir() / "metrics"
    p.mkdir(parents=True, exist_ok=True)
    return p


def tmp_dir() -> pathlib.Path:
    p = repo_root() / "tmp"
    p.mkdir(parents=True, exist_ok=True)
    return p


def identity_db_path() -> pathlib.Path:
    return memory_dir() / "identity_features.db.json"


def students_dir() -> pathlib.Path:
    p = memory_dir() / "students"
    p.mkdir(parents=True, exist_ok=True)
    return p
