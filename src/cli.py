from __future__ import annotations

import argparse
from pathlib import Path

from src.pipeline import run_full_pipeline


def main() -> None:
    p = argparse.ArgumentParser(description="Kinder Vision — 影片分析管線（README / docs/agents 對齊）")
    p.add_argument("video", type=str, help="影片路徑（.mp4 / .mov / .avi）")
    p.add_argument(
        "--model",
        type=str,
        default="yolov8n-pose.pt",
        help="YOLO 權重路徑或模型名（例：yolov8n-pose.pt、yolo26n-pose.pt）",
    )
    p.add_argument("--stride", type=int, default=4, help="取樣幀間隔（越大越快、越粗）")
    p.add_argument(
        "--learn-identities",
        action="store_true",
        help="將無法比對的身分以 appearance embedding 寫入 memory/identity_features.db.json",
    )
    p.add_argument(
        "--no-track",
        action="store_true",
        help="停用 ByteTrack（改以每幀由左至右槽位對齊，適合追蹤不穩的影片）",
    )
    p.add_argument(
        "--t0",
        type=str,
        default=None,
        metavar="T",
        help="分析區間起點（相對原片）：秒數、或 MM:SS、或 HH:MM:SS（需 ffmpeg；與 --t1 可只填其一）",
    )
    p.add_argument(
        "--t1",
        type=str,
        default=None,
        metavar="T",
        help="分析區間終點（相對原片）：秒數或 MM:SS；省略則到片尾",
    )
    p.add_argument(
        "--pose",
        choices=["off", "pose", "holistic"],
        default="pose",
        help="人框內姿勢精化：off=僅 YOLO；pose=MediaPipe Pose；holistic=MediaPipe Holistic",
    )
    p.add_argument(
        "--no-mediapipe",
        action="store_true",
        help="等同 --pose off（停用 MediaPipe）",
    )
    p.add_argument(
        "--no-video-reid",
        action="store_true",
        help="停用整片軌跡 ReID（ArcFace／外觀嵌入軌跡平均）",
    )
    p.add_argument(
        "--no-ai",
        action="store_true",
        help="不在教育報告末段呼叫 AI（需 API Key 與 requirements-ai）",
    )
    p.add_argument(
        "--pdf",
        action="store_true",
        help="另存合併 PDF（彙總 + 教育建議）；需 pip install -r requirements-pdf.txt",
    )
    p.add_argument(
        "--no-accumulate-sessions",
        action="store_true",
        help="不寫入跨影片累積檔 memory/students/<id>/sessions.jsonl",
    )
    args = p.parse_args()

    pose_mode = "off" if args.no_mediapipe else args.pose

    paths = run_full_pipeline(
        Path(args.video),
        model_path=args.model,
        sample_stride=args.stride,
        learn_identities=args.learn_identities,
        use_tracking=not args.no_track,
        t0=args.t0,
        t1=args.t1,
        use_mediapipe=False if args.no_mediapipe else True,
        pose_mode=pose_mode,
        use_llm=not args.no_ai,
        use_video_reid=not args.no_video_reid,
        emit_pdf=args.pdf,
        accumulate_sessions=not args.no_accumulate_sessions,
    )
    print("完成。輸出：")
    for k, v in paths.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
