from __future__ import annotations

import numpy as np


def _get_app():
    """Lazy-load shared InsightFace pipeline (buffalo_l)."""
    app = getattr(_get_app, "_app", None)
    if app is not None:
        return app
    try:
        from insightface.app import FaceAnalysis  # type: ignore[import-not-found]
    except ImportError:
        return None
    providers = ["CPUExecutionProvider"]
    try:
        import onnxruntime as ort  # noqa: F401

        if "CoreMLExecutionProvider" in ort.get_available_providers():
            providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
    except Exception:
        pass
    app = FaceAnalysis(name="buffalo_l", providers=providers)
    app.prepare(ctx_id=0, det_size=(640, 640))
    setattr(_get_app, "_app", app)
    return app


def embed_face_optional(bgr_face: np.ndarray) -> np.ndarray | None:
    """若已安裝 insightface，回傳 L2 正規化之 ArcFace 向量；否則 None。

    安裝（可選）: pip install insightface onnxruntime
    首次執行會下載模型至本機快取。
    """
    res = embed_face_with_age_optional(bgr_face)
    return None if res is None else res[0]


def embed_face_with_age_optional(
    bgr_face: np.ndarray,
) -> tuple[np.ndarray, float | None] | None:
    """Like ``embed_face_optional`` but also returns the estimated age.

    Returns ``(embedding, age)`` where ``age`` may be ``None`` if the buffalo_l
    pipeline did not populate it.
    """
    if bgr_face.size == 0 or bgr_face.shape[0] < 16 or bgr_face.shape[1] < 16:
        return None
    app = _get_app()
    if app is None:
        return None
    try:
        faces = app.get(bgr_face)
    except Exception:
        return None
    if not faces:
        return None
    f = max(faces, key=lambda x: float(getattr(x, "det_score", 0.0) or 0.0))
    emb = np.asarray(f.normed_embedding, dtype=np.float64).ravel()
    n = float(np.linalg.norm(emb))
    if n < 1e-9:
        return None
    age_val = getattr(f, "age", None)
    age: float | None
    try:
        age = float(age_val) if age_val is not None else None
    except (TypeError, ValueError):
        age = None
    return emb / n, age
