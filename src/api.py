from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, Field

from src.pipeline import run_full_pipeline
from src.paths import tmp_dir


class AnalyzeRequest(BaseModel):
    video_path: str = Field(..., description="Path to input video file")
    model: str = Field("yolov8n-pose.pt", description="YOLO model path or model name")
    stride: int = Field(4, ge=1, description="Frame sampling stride")
    learn_identities: bool = False
    no_track: bool = False
    t0: str | None = None
    t1: str | None = None
    pose: str = Field("pose", pattern="^(off|pose|holistic)$")
    no_mediapipe: bool = False
    no_video_reid: bool = False
    no_ai: bool = False
    pdf: bool = False
    no_accumulate_sessions: bool = False


class AnalyzeResponse(BaseModel):
    ok: bool = True
    task_id: str
    status: str


app = FastAPI(title="Kinder Vision API", version="0.1.0")
_TASKS_LOCK = threading.Lock()
_TASKS: dict[str, dict[str, Any]] = {}
_TASK_TTL_SEC = max(60, int((os.environ.get("KINDER_TASK_TTL_SEC") or "86400").strip() or "86400"))
_API_KEY = (os.environ.get("KINDER_API_KEY") or "").strip()
_TASKS_DB_PATH = tmp_dir() / "kinder-api-tasks.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _require_api_key(x_api_key: str | None) -> None:
    if not _API_KEY:
        return
    if not x_api_key or x_api_key.strip() != _API_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")


def _cleanup_tasks_locked() -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=_TASK_TTL_SEC)
    stale: list[str] = []
    for task_id, row in _TASKS.items():
        if row.get("status") not in {"succeeded", "failed"}:
            continue
        done_at = _parse_iso(row.get("finished_at"))
        if done_at and done_at < cutoff:
            stale.append(task_id)
    for task_id in stale:
        _TASKS.pop(task_id, None)


def _persist_tasks_locked() -> None:
    serializable = {"tasks": list(_TASKS.values())}
    _TASKS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    _TASKS_DB_PATH.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_tasks() -> None:
    if not _TASKS_DB_PATH.is_file():
        return
    try:
        raw = json.loads(_TASKS_DB_PATH.read_text(encoding="utf-8"))
        rows = raw.get("tasks", []) if isinstance(raw, dict) else []
        if not isinstance(rows, list):
            return
        with _TASKS_LOCK:
            for row in rows:
                if not isinstance(row, dict):
                    continue
                tid = str(row.get("task_id", "")).strip()
                if not tid:
                    continue
                # Restart after crash/reboot: incomplete tasks are marked cancelled.
                status = str(row.get("status", "failed"))
                if status in {"queued", "running"}:
                    row["status"] = "cancelled"
                    row["finished_at"] = _now_iso()
                    row["error"] = {"code": 499, "message": "Task interrupted by service restart"}
                _TASKS[tid] = row
            _cleanup_tasks_locked()
            _persist_tasks_locked()
    except Exception:
        return


def _run_task(task_id: str, req: AnalyzeRequest) -> None:
    with _TASKS_LOCK:
        row = _TASKS.get(task_id)
        if row is None:
            return
        if row.get("status") == "cancelled":
            return
        row["status"] = "running"
        row["started_at"] = _now_iso()
        _persist_tasks_locked()
    try:
        outputs = run_full_pipeline(
            Path(req.video_path),
            model_path=req.model,
            sample_stride=req.stride,
            learn_identities=req.learn_identities,
            use_tracking=not req.no_track,
            t0=req.t0,
            t1=req.t1,
            use_mediapipe=False if req.no_mediapipe else True,
            pose_mode=req.pose,
            use_llm=not req.no_ai,
            use_video_reid=not req.no_video_reid,
            emit_pdf=req.pdf,
            accumulate_sessions=not req.no_accumulate_sessions,
        )
        with _TASKS_LOCK:
            row = _TASKS.get(task_id)
            if row is None:
                return
            if row.get("status") == "cancelled":
                _persist_tasks_locked()
                return
            row["status"] = "succeeded"
            row["finished_at"] = _now_iso()
            row["outputs"] = {k: str(v) for k, v in outputs.items()}
            _persist_tasks_locked()
    except FileNotFoundError as e:
        with _TASKS_LOCK:
            row = _TASKS.get(task_id)
            if row is None:
                return
            row["status"] = "failed"
            row["finished_at"] = _now_iso()
            row["error"] = {"code": 404, "message": f"File not found: {e}"}
            _persist_tasks_locked()
    except ValueError as e:
        with _TASKS_LOCK:
            row = _TASKS.get(task_id)
            if row is None:
                return
            row["status"] = "failed"
            row["finished_at"] = _now_iso()
            row["error"] = {"code": 400, "message": str(e)}
            _persist_tasks_locked()
    except Exception as e:  # noqa: BLE001
        with _TASKS_LOCK:
            row = _TASKS.get(task_id)
            if row is None:
                return
            row["status"] = "failed"
            row["finished_at"] = _now_iso()
            row["error"] = {"code": 500, "message": f"Analyze failed: {e}"}
            _persist_tasks_locked()


@app.get("/health")
def health() -> dict[str, Any]:
    return {"ok": True, "service": "kinder-vision-api", "task_ttl_sec": _TASK_TTL_SEC}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(req: AnalyzeRequest, x_api_key: str | None = Header(default=None)) -> AnalyzeResponse:
    _require_api_key(x_api_key)
    task_id = uuid.uuid4().hex
    with _TASKS_LOCK:
        _cleanup_tasks_locked()
        _TASKS[task_id] = {
            "task_id": task_id,
            "status": "queued",
            "created_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "request": req.model_dump(),
            "outputs": None,
            "error": None,
        }
        _persist_tasks_locked()
    t = threading.Thread(target=_run_task, args=(task_id, req), daemon=True)
    t.start()
    return AnalyzeResponse(task_id=task_id, status="queued")


@app.get("/tasks/{task_id}")
def get_task(task_id: str, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    _require_api_key(x_api_key)
    with _TASKS_LOCK:
        _cleanup_tasks_locked()
        row = _TASKS.get(task_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        return dict(row)


@app.get("/tasks")
def list_tasks(
    x_api_key: str | None = Header(default=None),
    limit: int = Query(default=20, ge=1, le=200),
) -> dict[str, Any]:
    _require_api_key(x_api_key)
    with _TASKS_LOCK:
        _cleanup_tasks_locked()
        _persist_tasks_locked()
        rows = list(_TASKS.values())
    rows.sort(key=lambda r: str(r.get("created_at", "")), reverse=True)
    return {"count": min(limit, len(rows)), "items": [dict(r) for r in rows[:limit]]}


@app.post("/tasks/{task_id}/cancel")
def cancel_task(task_id: str, x_api_key: str | None = Header(default=None)) -> dict[str, Any]:
    _require_api_key(x_api_key)
    with _TASKS_LOCK:
        _cleanup_tasks_locked()
        row = _TASKS.get(task_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        status = str(row.get("status", ""))
        if status in {"succeeded", "failed", "cancelled"}:
            return {"ok": True, "task_id": task_id, "status": status, "message": "Task already terminal"}
        row["status"] = "cancelled"
        row["finished_at"] = _now_iso()
        row["error"] = {"code": 499, "message": "Task cancelled by user"}
        _persist_tasks_locked()
        return {"ok": True, "task_id": task_id, "status": "cancelled"}


_load_tasks()
