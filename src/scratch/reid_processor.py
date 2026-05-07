import json
import math
import sys
from pathlib import Path

# 允許從 repo 根目錄執行：python src/scratch/reid_processor.py
_REPO = Path(__file__).resolve().parents[2]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from src.paths import memory_dir, metrics_dir  # noqa: E402


def calculate_distance(v1, v2):
    """計算兩個特徵向量之間的歐幾里得距離"""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


def process_video_analytics(video_name, detected_features_list, raw_metrics_list):
    memory_dir()
    db_path = memory_dir() / "identity_features.db.json"
    if not db_path.exists():
        db_path.write_text(json.dumps({"identities": []}, indent=2, ensure_ascii=False), encoding="utf-8")
    db = json.loads(db_path.read_text(encoding="utf-8"))

    identities = db["identities"]
    results = []

    for i, detected_feat in enumerate(detected_features_list):
        best_row = None
        min_dist = float("inf")

        for identity_row in identities:
            emb = identity_row["features"]["face_embedding_sample"]
            dist = calculate_distance(detected_feat, emb)
            if dist < min_dist:
                min_dist = dist
                best_row = identity_row

        if best_row is not None and min_dist < 0.5:
            matched_id = best_row
            status = "returning"
            student_id = matched_id["student_id"]
            name_code = matched_id["display_name"]
        else:
            matched_id = None
            status = "new"
            student_id = f"S_NEW_{len(results) + 1}"
            name_code = f"Child_New_{len(results) + 1}"

        metrics_entry = {
            "student_id": student_id,
            "name_code": name_code,
            "session_date": "2026-05-05",
            "video_ref": video_name,
            "status": status,
            "metrics": raw_metrics_list[i],
        }

        output_path = metrics_dir() / f"2026-05-05_{student_id}_metrics.json"
        with open(output_path, "w", encoding="utf-8") as out_f:
            json.dump(metrics_entry, out_f, indent=2, ensure_ascii=False)

        results.append(name_code)
        print(f"✅ 已完成歸戶：{name_code} (Status: {status}, Dist: {min_dist:.4f})")

    return results


if __name__ == "__main__":
    mock_detected_features = [
        [0.89, 0.11, -0.21, 0.46, 0.68, -0.04, 0.15, 0.54],
        [0.13, -0.44, 0.77, 0.22, -0.10, 0.88, 0.04, -0.31],
        [0.99, 0.99, 0.99, 0.99, 0.99, 0.99, 0.99, 0.99],
    ]

    mock_metrics = [
        {"rhythmic_sync": {"avg_error_ms": 38}, "inhibitory_control": {"max_displacement_cm": 6.2}},
        {"rhythmic_sync": {"avg_error_ms": 24}, "inhibitory_control": {"max_displacement_cm": 2.1}},
        {"rhythmic_sync": {"avg_error_ms": 150}, "inhibitory_control": {"max_displacement_cm": 20.0}},
    ]

    print("🚀 啟動 Kinder Vision 自動歸戶處理器（src/scratch 示範）...")
    process_video_analytics("W4-6 Musical Movement.MOV", mock_detected_features, mock_metrics)
