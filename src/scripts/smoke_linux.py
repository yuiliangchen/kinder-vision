#!/usr/bin/env python3
from __future__ import annotations

import importlib
import platform
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _check_import(module_name: str) -> tuple[bool, str]:
    try:
        m = importlib.import_module(module_name)
        ver = getattr(m, "__version__", "unknown")
        return True, f"{module_name}=={ver}"
    except Exception as e:  # noqa: BLE001
        return False, f"{module_name} import failed: {e}"


def main() -> int:
    print(f"python={sys.version.split()[0]} platform={platform.platform()}")

    required = [
        "numpy",
        "scipy",
        "pandas",
        "cv2",
        "librosa",
        "soundfile",
        "matplotlib",
        "tqdm",
        "lap",
        "torch",
        "mediapipe",
        "ultralytics",
    ]

    failed = 0
    for name in required:
        ok, msg = _check_import(name)
        print(("OK   " if ok else "FAIL ") + msg)
        if not ok:
            failed += 1

    # Optional YOLO constructor smoke test.
    try:
        from ultralytics import YOLO

        model_name = "yolov8n-pose.pt"
        YOLO(model_name)
        print(f"OK   ultralytics.YOLO('{model_name}')")
    except Exception as e:  # noqa: BLE001
        print(f"FAIL ultralytics.YOLO init failed: {e}")
        failed += 1

    # Optional local model existence hint.
    local_model = _REPO_ROOT / "yolov8n-pose.pt"
    if not local_model.exists():
        print("INFO yolov8n-pose.pt not found locally; Ultralytics may auto-download on first use.")

    if failed:
        print(f"RESULT: FAILED ({failed} checks)")
        return 1
    print("RESULT: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
