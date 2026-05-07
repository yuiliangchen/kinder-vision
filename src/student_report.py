"""從跨影片累積的 sessions.jsonl 產生個人 Markdown／PDF 報告。"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from src.report_pdf import export_markdown_pdf
from src.student_longitudinal import (
    list_student_slugs,
    load_sessions,
    sessions_jsonl_path,
    student_slug,
    students_dir,
)


def _num(v: Any) -> str:
    if v is None:
        return "—"
    if isinstance(v, (int, float)):
        return f"{v:.2f}" if isinstance(v, float) else str(v)
    return str(v)


def render_longitudinal_markdown(student_id: str) -> str:
    sessions = load_sessions(student_id)
    if not sessions:
        raise FileNotFoundError(
            f"尚無累積資料：{sessions_jsonl_path(student_id)}（需先跑影片分析且未使用 --no-accumulate-sessions）"
        )
    last = sessions[-1]
    ch0 = sessions[0].get("child") or {}
    name = last.get("display_name") or ch0.get("display_name") or "孩子"
    sid = student_slug(student_id)

    lines: list[str] = [
        f"# 個人長期分析：{name}",
        "",
        f"- **查詢鍵**：`{student_id}`",
        f"- **儲存目錄（slug）**：`reports/students/{sid}/`",
        f"- **累積次數**：{len(sessions)} 支影片／分析 run",
        "",
        "## 各次表現總表",
        "",
        "| 紀錄時間 | 影片 | BPM | 節奏誤差(ms) | 節奏評級 | 靜止位移(cm) | 穩定度 | Jerk | 流暢度 |",
        "|---|---|---|---:|---|---:|---|---:|---|",
    ]
    for s in sessions:
        c = s.get("child") or {}
        vid = Path(str(s.get("video", ""))).name
        lines.append(
            "| "
            + " | ".join(
                [
                    str(s.get("recorded_at", "—")),
                    vid.replace("|", "\\|"),
                    _num(c.get("bpm")),
                    _num(c.get("avg_error_ms")),
                    str(c.get("sync_rating", "—")),
                    _num(c.get("avg_displacement_cm")),
                    str(c.get("stability_rating", "—")),
                    _num(c.get("avg_jerk")),
                    str(c.get("fluency_rating", "—")),
                ]
            )
            + " |"
        )

    lines += ["", "## 簡要觀察", ""]
    if len(sessions) >= 2:
        c_last = last.get("child") or {}
        e0 = ch0.get("avg_error_ms")
        e1 = c_last.get("avg_error_ms")
        j0 = ch0.get("avg_jerk")
        j1 = c_last.get("avg_jerk")
        if isinstance(e0, (int, float)) and isinstance(e1, (int, float)):
            d = float(e1) - float(e0)
            lines.append(f"- **節奏誤差**：由 {e0:.1f} ms → {e1:.1f} ms（變化 {d:+.1f} ms；數值愈低通常愈貼拍）。")
        if isinstance(j0, (int, float)) and isinstance(j1, (int, float)):
            d = float(j1) - float(j0)
            lines.append(f"- **動作 Jerk**：由 {j0:.2f} → {j1:.2f}（變化 {d:+.2f}）。")
    else:
        lines.append("- 目前僅有一次紀錄；累積多支影片後可觀察趨勢。")

    lines += [
        "",
        "---",
        "",
        "*資料來源：`reports/students/` 下該身分之 `sessions.jsonl`。*",
    ]
    return "\n".join(lines)


def write_longitudinal_report(student_id: str, out_md: Path) -> Path:
    text = render_longitudinal_markdown(student_id)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(text, encoding="utf-8")
    return out_md


def _generate_one(student_id: str, *, out_md: Path | None, emit_pdf: bool) -> tuple[Path, Path | None]:
    slug = student_slug(student_id)
    md_path = out_md or (students_dir() / slug / "longitudinal-report.md")
    path = write_longitudinal_report(student_id, md_path)
    pdf_path: Path | None = None
    if emit_pdf:
        pdf_path = path.with_suffix(".pdf")
        export_markdown_pdf(path, pdf_path)
    return path, pdf_path


def main() -> None:
    p = argparse.ArgumentParser(description="依跨影片累積資料產生個人長期分析報告（Markdown／PDF）")
    p.add_argument(
        "student_id",
        type=str,
        nargs="?",
        default=None,
        help="student_id 或 anon 鍵（與 metrics 檔名一致）；省略時須搭配 --all",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="為 reports/students/*/sessions.jsonl 有資料的每位孩子各產生一份報告",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="單人模式：Markdown 輸出路徑（預設 reports/students/<slug>/longitudinal-report.md）；與 --all 併用時會忽略",
    )
    p.add_argument("--pdf", action="store_true", help="另輸出 PDF（需 requirements-pdf.txt）")
    args = p.parse_args()

    if args.all:
        ids = list_student_slugs()
        n_ok = n_skip = 0
        for folder_name in ids:
            if not load_sessions(folder_name):
                n_skip += 1
                continue
            md_path, pdf_path = _generate_one(folder_name, out_md=None, emit_pdf=args.pdf)
            print(md_path)
            if pdf_path:
                print(pdf_path)
            n_ok += 1
        print(f"完成：報告 {n_ok} 份，略過空資料夾 {n_skip} 個。")
        return

    if not args.student_id or not args.student_id.strip():
        p.error("請提供 student_id，或使用 --all")

    sid = args.student_id.strip()
    path, pdf_path = _generate_one(sid, out_md=args.out, emit_pdf=args.pdf)
    print(path)
    if pdf_path:
        print(pdf_path)


if __name__ == "__main__":
    main()
