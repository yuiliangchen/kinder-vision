"""OpenAI 相容 API：於教育報告末段補上 AI 建議（可選依賴 openai）。"""
from __future__ import annotations

import json
import os
from typing import Any


def _trim(obj: Any, max_chars: int) -> str:
    s = json.dumps(obj, ensure_ascii=False, indent=2)
    if len(s) <= max_chars:
        return s
    return s[: max_chars - 20] + "\n…(truncated)…"


def augment_edu_report(
    base_markdown: str,
    *,
    video_path: str,
    duration_sec: float,
    macro: dict[str, Any],
    micro: dict[str, Any],
    metrics: dict[str, Any],
) -> tuple[str, list[str], bool]:
    """若環境有 API Key 且已安裝 openai，則附帶「## 五、AI 教學補充」；否則原樣回傳。第三個值表示是否已附加 AI 段落。"""
    warnings: list[str] = []
    key = os.environ.get("KINDER_AI_API_KEY") or os.environ.get("OPENAI_API_KEY")
    if not key or not str(key).strip():
        return base_markdown, warnings, False

    try:
        from openai import OpenAI  # type: ignore[import-not-found]
    except ImportError:
        warnings.append("已設定 API Key 但未安裝 openai；略過 AI（pip install -r requirements-ai.txt）")
        return base_markdown, warnings, False

    base_url = (os.environ.get("KINDER_AI_BASE_URL") or "https://api.openai.com/v1").rstrip("/")
    model = os.environ.get("KINDER_AI_MODEL") or "gpt-4o-mini"
    ctx = (
        f"影片路徑: {video_path}\n片長秒: {duration_sec:.1f}\n\n"
        "macro:\n"
        + _trim(macro, 12000)
        + "\n\nmicro:\n"
        + _trim(micro, 12000)
        + "\n\nmetrics:\n"
        + _trim(metrics, 8000)
    )
    client = OpenAI(api_key=key.strip(), base_url=base_url)
    try:
        resp = client.chat.completions.create(
            model=model,
            temperature=0.4,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是幼教現場顧問，依據下列機讀量化結果，用繁體中文撰寫簡短教學建議。"
                        "避免醫療診斷或標籤化；語氣專業、具體、可執行。"
                        "輸出為 Markdown，勿重複報告前文；以條列為主，總長約 400–900 字。"
                    ),
                },
                {
                    "role": "user",
                    "content": "以下為本支影片的分析摘要 JSON，請產出可插入教育報告的補充段落：\n\n" + ctx,
                },
            ],
        )
        choice = resp.choices[0].message.content if resp.choices else None
        if not choice or not str(choice).strip():
            warnings.append("AI 回傳空白，略過附加段落")
            return base_markdown, warnings, False
        block = (
            "\n\n---\n\n## 五、AI 教學補充建議\n\n"
            + str(choice).strip()
            + "\n\n*本段由 AI 依量化摘要生成，僅供參考。*\n"
        )
        return base_markdown.rstrip() + block, warnings, True
    except Exception as e:  # noqa: BLE001
        warnings.append(f"AI 呼叫失敗（略過）：{e!s}")
        return base_markdown, warnings, False
