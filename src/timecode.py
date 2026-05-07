from __future__ import annotations

import re


def parse_timecode(s: str) -> float:
    """解析時間碼為秒。

    支援：`90`、`90.5`、`01:30`、`1:30`、`1:01:05`（時:分:秒）。
    """
    s = str(s).strip()
    if not s:
        raise ValueError("空字串無法解析為時間")
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return float(s)
    parts = s.split(":")
    if len(parts) == 2:
        m, sec = parts
        return int(m, 10) * 60 + float(sec)
    if len(parts) == 3:
        h, m, sec = parts
        return int(h, 10) * 3600 + int(m, 10) * 60 + float(sec)
    raise ValueError(f"無法解析時間碼：{s!r}")


def format_mmss(sec: float) -> str:
    """輸出 MM:SS；若有非整秒則顯示一位小數（避免 round(1.5)→2 的錯覺）。"""
    if sec < 0:
        sec = 0.0
    m = int(sec // 60)
    rem = sec - m * 60
    if abs(rem - round(rem)) < 1e-3:
        return f"{m:02d}:{int(round(rem)):02d}"
    return f"{m:02d}:{rem:05.2f}".rstrip("0").rstrip(".")
