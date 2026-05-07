"""將 Markdown 報告（彙總 + 教育建議）匯出為 PDF。依賴：requirements-pdf.txt"""
from __future__ import annotations

from pathlib import Path

_PDF_CSS = """
    @page { margin: 16mm 18mm; size: A4; }
    body {
      font-family: "PingFang SC", "Hiragino Sans GB", "Noto Sans CJK TC",
        "Microsoft JhengHei", "Microsoft YaHei", sans-serif;
      font-size: 10.5pt;
      line-height: 1.55;
      color: #1a1a1a;
    }
    h1 { font-size: 17pt; margin: 0.6em 0 0.35em; border-bottom: 1px solid #bbb; padding-bottom: 0.15em; }
    h2 { font-size: 13pt; margin: 1.1em 0 0.4em; }
    h3 { font-size: 11.5pt; margin: 0.9em 0 0.3em; }
    hr { border: none; border-top: 1px solid #ccc; margin: 1.2em 0; }
    p { margin: 0.45em 0; }
    ul, ol { margin: 0.4em 0 0.6em 1.2em; padding-left: 0.2em; }
    li { margin: 0.2em 0; }
    code {
      font-family: ui-monospace, Menlo, Consolas, monospace;
      font-size: 9pt;
      background: #f4f4f4;
      padding: 0.1em 0.35em;
      border-radius: 3px;
    }
    pre {
      font-family: ui-monospace, Menlo, Consolas, monospace;
      font-size: 8.5pt;
      background: #f6f6f6;
      border: 1px solid #e0e0e0;
      border-radius: 4px;
      padding: 0.65em 0.75em;
      overflow-x: auto;
      white-space: pre-wrap;
      word-break: break-word;
    }
    pre code { background: none; padding: 0; }
    table { border-collapse: collapse; width: 100%; margin: 0.6em 0; font-size: 9.5pt; }
    th, td { border: 1px solid #ccc; padding: 5px 8px; text-align: left; vertical-align: top; }
    th { background: #f0f0f0; }
    blockquote {
      margin: 0.6em 0;
      padding: 0.2em 0 0.2em 0.85em;
      border-left: 3px solid #888;
      color: #444;
    }
    strong { font-weight: 600; }
    """


def _markdown_to_html(md_source: str) -> str:
    import markdown

    md = markdown.Markdown(extensions=["tables", "fenced_code", "nl2br", "sane_lists"])
    return md.convert(md_source)


def _write_pdf_from_html(html_doc: str, base_url: str, pdf_out: Path) -> Path:
    try:
        from weasyprint import CSS, HTML
    except ImportError as e:
        raise RuntimeError(
            "無法匯出 PDF：請先執行 pip install -r requirements-pdf.txt（需 markdown、weasyprint）"
        ) from e

    pdf_out.parent.mkdir(parents=True, exist_ok=True)
    HTML(string=html_doc, base_url=base_url).write_pdf(str(pdf_out), stylesheets=[CSS(string=_PDF_CSS)])
    return pdf_out


def export_markdown_pdf(md_in: Path, pdf_out: Path, *, title: str = "Kinder Vision 分析報告") -> Path:
    """將單一 Markdown 檔轉成 PDF。"""
    if not md_in.is_file():
        raise FileNotFoundError(md_in)
    md_source = md_in.read_text(encoding="utf-8")
    body_html = _markdown_to_html(md_source)
    html_doc = (
        "<!DOCTYPE html><html lang=\"zh-Hant\"><head><meta charset=\"utf-8\"/>"
        f"<title>{title}</title></head><body>"
        f"{body_html}</body></html>"
    )
    base = str(md_in.parent.resolve())
    return _write_pdf_from_html(html_doc, base, pdf_out)


def export_combined_report_pdf(
    analysis_md: Path,
    edu_md: Path,
    pdf_out: Path,
) -> Path:
    """合併「一頁彙總」與「教育建議」Markdown，輸出單一 PDF。"""
    parts: list[str] = []
    if analysis_md.is_file():
        parts.append(analysis_md.read_text(encoding="utf-8"))
    if edu_md.is_file():
        parts.append(edu_md.read_text(encoding="utf-8"))
    if not parts:
        raise FileNotFoundError(f"找不到報告 Markdown：{analysis_md} / {edu_md}")

    md_source = "\n\n---\n\n".join(parts)
    body_html = _markdown_to_html(md_source)

    html_doc = (
        "<!DOCTYPE html><html lang=\"zh-Hant\"><head><meta charset=\"utf-8\"/>"
        "<title>Kinder Vision 分析報告</title></head><body>"
        f"{body_html}</body></html>"
    )

    base = str(edu_md.parent.resolve()) if edu_md.is_file() else str(analysis_md.parent.resolve())
    return _write_pdf_from_html(html_doc, base, pdf_out)


def _cli() -> None:
    import argparse

    ap = argparse.ArgumentParser(description="將既有 Markdown 報告合併為 PDF（不需重跑影片）")
    ap.add_argument("--analysis", type=Path, required=True, help="彙總 .md 路徑")
    ap.add_argument("--edu", type=Path, required=True, help="教育建議 .md 路徑")
    ap.add_argument("--out", type=Path, required=True, help="輸出 .pdf 路徑")
    args = ap.parse_args()
    p = export_combined_report_pdf(args.analysis, args.edu, args.out)
    print(p)


if __name__ == "__main__":
    _cli()
