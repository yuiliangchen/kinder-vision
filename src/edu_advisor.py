from __future__ import annotations

from datetime import datetime
from typing import Any


def _tracking_label_zh(micro: dict[str, Any]) -> str:
    if micro.get("tracking") == "bytetrack":
        return "ByteTrack（Ultralytics 內建多目標追蹤）"
    return "由左至右槽位對齊（無 ByteTrack，等同 CLI `--no-track`）"


def render_edu_markdown(
    video_path: str,
    duration_sec: float,
    macro: dict[str, Any],
    micro: dict[str, Any],
    metrics: dict[str, Any],
    include_meta: bool = True,
) -> str:
    mm = int(duration_sec // 60)
    ss = int(duration_sec % 60)
    lines = ["# 🌟 幼兒行為分析教育建議報告", ""]
    if include_meta:
        lines += [
            f"**分析日期**：{datetime.now().strftime('%Y-%m-%d')}",
            f"**影片**：`{video_path}`",
            f"**本次分析片長**：{mm} 分 {ss} 秒（實際送入模型的影片長度）",
        ]
        win = micro.get("analysis_window_original")
        if win:
            lines.append(f"**分析區間**（對應原片時間線）：{win}")
        pose_b = micro.get("pose_backend", "yolo_only")
        if pose_b == "yolo+mediapipe_holistic":
            pose_line = "YOLO 關節 + MediaPipe Holistic（人框內精化）"
        elif pose_b in ("yolo+mediapipe", "yolo+mediapipe_pose"):
            pose_line = "YOLO 關節 + MediaPipe Pose（於人框內精化）"
        else:
            pose_line = "僅 YOLO 關節"
        lines.append(
            f"**追蹤模式**：{_tracking_label_zh(micro)}；取樣 `vid_stride` = {micro.get('vid_stride', '—')}"
        )
        lines.append(f"**姿勢後端**：{pose_line}（`pose_backend` = `{pose_b}`）")
        reid_n = len(micro.get("reid_by_track") or {})
        if reid_n:
            lines.append(f"**軌跡 ReID**：已對 {reid_n} 條 ByteTrack 軌跡與身分庫比對（整片累積嵌入）。")
    # Normalize heading spacing so merged reports keep exactly one blank line.
    while lines and lines[-1] == "":
        lines.pop()
    lines += [
        "---",
        "",
        "## 一、班級整體回饋",
        "",
        "### 亮點觀察 🏆",
        f"- 群體參與度（活躍比例）：約 {macro.get('engagement_score', 0) * 100:.0f}%",
        f"- 主要熱區：{', '.join(macro.get('hotspot_zones', [])[:4]) or '（資料不足）'}",
        "",
        "### 觀注重點 ⚠️",
        f"- 指標總覽：{metrics.get('overall_status', '')}",
        "",
        "### 改進方向 💡",
        "- 若隊形切換混亂：切換前加入倒數與地板標記（見 MANUAL）",
        "- 若停止信號後位移偏大：增加「音樂停→立刻靜止」迷你遊戲頻率",
        "",
        "---",
        "",
        "## 二、個別關注建議",
        "",
    ]
    for c in metrics.get("concern_children", []) or []:
        label = str(c.get("display_label") or "").strip() or f"孩子 {c.get('child_id', '?')}"
        lines += [
            f"### 👤 {label}（{c.get('priority', 'medium')}）",
            f"- **觀察摘要**：{c.get('reason', '')}",
            "- **建議**：以正向框架安排短時間、可達成小任務，並持續觀察 2–4 週。",
            "",
        ]
    if not metrics.get("concern_children"):
        lines += ["（本次未產生高優先關注名單 — 仍以教師現場觀察為準）", ""]

    lines += [
        "---",
        "",
        "## 三、教學策略調整（對照數據）",
        "",
        "| 發現 | 建議策略 |",
        "|-----|---------|",
        "| 熱區過度集中 | 設計邊界探索任務，分散活動點 |",
        "| 同步誤差偏高 | 先降 BPM 或強化身體打拍 |",
        "| 穩定度偏弱 | 木頭人／停止信號遊戲分段拉長 |",
        "",
        "---",
        "",
        "## 四、家長聯絡簿參考文字（草稿）",
        "",
        "親愛的家長，今日孩子參與音樂肢體活動。老師會綜合現場互動與本系統的量化線索，",
        "在接下來的課程中持續陪伴孩子的節奏感與自我調節練習。若您願意，在家也可透過簡單的「一二三木頭人」",
        "遊戲，以輕鬆方式延續課堂經驗。",
        "",
        "---",
        "",
        "*本報告由 AI 輔助生成，僅供教學參考，不作為正式評量依據。*",
    ]
    return "\n".join(lines)
