from __future__ import annotations

import numpy as np


def embed_face_optional(bgr_face: np.ndarray) -> np.ndarray | None:
    """若已安裝 insightface，回傳 L2 正規化之 ArcFace 向量；否則 None。

    安裝（可選）: pip install insightface onnxruntime
    首次執行會下載模型至本機快取。
    """
    if bgr_face.size == 0 or bgr_face.shape[0] < 16 or bgr_face.shape[1] < 16:
        return None
    try:
        from insightface.app import FaceAnalysis  # type: ignore[import-not-found]
    except ImportError:
        return None

    app = getattr(embed_face_optional, "_app", None)
    if app is None:
        providers = ["CPUExecutionProvider"]
        try:
            import onnxruntime as ort  # noqa: F401

            if "CoreMLExecutionProvider" in ort.get_available_providers():
                providers = ["CoreMLExecutionProvider", "CPUExecutionProvider"]
        except Exception:
            pass
        app = FaceAnalysis(name="buffalo_l", providers=providers)
        app.prepare(ctx_id=0, det_size=(640, 640))
        setattr(embed_face_optional, "_app", app)

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
    return emb / n
