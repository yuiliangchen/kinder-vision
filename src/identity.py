from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

import numpy as np

from src.paths import identity_db_path, memory_dir

_STUDENT_SUFFIX_NUM = re.compile(r"^S_NEW_(\d+)$")


def _l2_normalize(v: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(v))
    if n < 1e-9:
        return v
    return v / n


def appearance_embedding_from_patch(bgr_patch: np.ndarray, dim: int = 128) -> np.ndarray:
    """HSV histogram embedding (no raw face pixels stored)."""
    if bgr_patch.size == 0 or bgr_patch.shape[0] < 2 or bgr_patch.shape[1] < 2:
        return _l2_normalize(np.zeros(dim, dtype=np.float64))
    hsv = bgr_patch  # keep BGR for speed; HSV optional via cv2
    import cv2

    hsv = cv2.cvtColor(bgr_patch, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1, 2], None, [4, 4, 4], [0, 180, 0, 256, 0, 256])
    hist = cv2.normalize(hist, None).flatten().astype(np.float64)
    if hist.size >= dim:
        vec = hist[:dim]
    else:
        vec = np.zeros(dim, dtype=np.float64)
        vec[: hist.size] = hist
    return _l2_normalize(vec)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    a = np.asarray(a, dtype=np.float64).ravel()
    b = np.asarray(b, dtype=np.float64).ravel()
    d = min(a.size, b.size)
    a, b = a[:d], b[:d]
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def ensure_identity_db() -> dict[str, Any]:
    memory_dir()
    path = identity_db_path()
    if not path.exists():
        path.write_text(json.dumps({"identities": []}, indent=2, ensure_ascii=False), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


def save_identity_db(db: dict[str, Any]) -> None:
    identity_db_path().write_text(json.dumps(db, indent=2, ensure_ascii=False), encoding="utf-8")


@dataclass
class IdentityAssignment:
    student_id: str
    display_name: str
    confidence: float
    status: str  # "returning" | "new"


def display_label_for_student_id(student_id: str) -> str | None:
    """若為 S_NEW_<數字>，回傳「孩子 <數字>」（去掉前導零的整數呈現）。"""
    m = _STUDENT_SUFFIX_NUM.match(str(student_id).strip())
    if not m:
        return None
    return f"孩子 {int(m.group(1))}"


def display_label_for_child(student_id: str | None, child_id: Any) -> str:
    """對外一致的孩子稱呼：優先用身分編號，否則用軌跡／槽位數字編號。"""
    if student_id:
        lab = display_label_for_student_id(str(student_id))
        if lab:
            return lab
    s = str(child_id).strip() if child_id is not None else ""
    if s.isdigit():
        return f"孩子 {int(s)}"
    if len(s) == 1:
        o = ord(s.upper())
        if ord("A") <= o <= ord("Z"):
            return f"孩子 {o - ord('A') + 1}"
    return f"孩子 {s}" if s else "孩子"


def assign_identity(embedding: np.ndarray, match_threshold: float = 0.85) -> IdentityAssignment:
    db = ensure_identity_db()
    best_sim = -1.0
    best: dict[str, Any] | None = None
    q = np.asarray(embedding, dtype=np.float64).ravel()
    for row in db.get("identities", []):
        feat = row.get("features", {}).get("face_embedding_sample")
        if feat is None:
            continue
        ref = np.asarray(feat, dtype=np.float64).ravel()
        if ref.size != q.size:
            continue
        sim = cosine_similarity(q, ref)
        if sim > best_sim:
            best_sim = sim
            best = row
    if best is not None and best_sim >= match_threshold:
        sid = str(best["student_id"])
        lab = display_label_for_student_id(sid)
        return IdentityAssignment(
            student_id=sid,
            display_name=lab or str(best.get("display_name", "孩子")),
            confidence=float(best_sim),
            status="returning",
        )
    n = len(db.get("identities", [])) + 1
    sid = f"S_NEW_{n:04d}"
    name = display_label_for_student_id(sid) or f"孩子 {n}"
    return IdentityAssignment(student_id=sid, display_name=name, confidence=float(max(best_sim, 0.0)), status="new")


def register_new_identity(student_id: str, display_name: str, embedding: list[float]) -> None:
    db = ensure_identity_db()
    db.setdefault("identities", []).append(
        {
            "student_id": student_id,
            "display_name": display_name,
            "features": {"face_embedding_sample": embedding},
        }
    )
    save_identity_db(db)
