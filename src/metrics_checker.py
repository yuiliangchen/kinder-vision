from __future__ import annotations

from datetime import datetime
from typing import Any

import numpy as np

from src import identity


def _light_from_sync(ms: float) -> tuple[str, float]:
    if ms < 50:
        return "🟢 綠燈", 1.0
    if ms < 150:
        return "🟡 黃燈", 0.55
    return "🔴 紅燈", 0.25


def _light_from_stability(cm: float) -> tuple[str, float]:
    if cm < 5:
        return "🟢 綠燈", 1.0
    if cm < 15:
        return "🟡 黃燈", 0.55
    return "🔴 紅燈", 0.25


def _light_from_fluency(jerk: float) -> tuple[str, float]:
    if jerk < 3.0:
        return "🟢 綠燈", 1.0
    if jerk < 6.0:
        return "🟡 黃燈", 0.55
    return "🔴 紅燈", 0.25


def _light_from_engagement(rate: float) -> tuple[str, float]:
    if rate >= 0.80:
        return "🟢 綠燈", 1.0
    if rate >= 0.60:
        return "🟡 黃燈", 0.55
    return "🔴 紅燈", 0.25


def _light_from_formation_stability(ratio: float) -> tuple[str, float]:
    if ratio >= 0.70:
        return "🟢 綠燈", 1.0
    if ratio >= 0.50:
        return "🟡 黃燈", 0.55
    return "🔴 紅燈", 0.25


def _light_from_space_std(std: float) -> tuple[str, float]:
    if std < 0.15:
        return "🟢 綠燈", 1.0
    if std <= 0.25:
        return "🟡 黃燈", 0.55
    return "🔴 紅燈", 0.25


def run_metrics(macro: dict[str, Any], micro: dict[str, Any]) -> dict[str, Any]:
    eng = float(macro.get("engagement_score", 0.0))
    eng_status, eng_sc = _light_from_engagement(eng)

    ft = macro.get("formation_timeline", []) or []
    ratios = [float(x.get("ratio", 0.0)) for x in ft]
    form_stab = float(np.mean(ratios)) if ratios else 0.0
    form_status, form_sc = _light_from_formation_stability(form_stab)

    grid = np.asarray(macro.get("heatmap_grid", [[0.0] * 3] * 3), dtype=np.float64).ravel()
    std = float(grid.std()) if grid.size else 0.0
    space_status, space_sc = _light_from_space_std(std)

    children = micro.get("children", []) or []
    if children:
        sync_ms = float(np.mean([c["avg_error_ms"] for c in children]))
        stab_cm = float(np.mean([c["avg_displacement_cm"] for c in children]))
        jerk = float(np.mean([c["avg_jerk"] for c in children]))
    else:
        sync_ms, stab_cm, jerk = 999.0, 99.0, 99.0

    sync_status, sync_sc = _light_from_sync(sync_ms)
    stab_status, stab_sc = _light_from_stability(stab_cm)
    flu_status, flu_sc = _light_from_fluency(jerk)

    overall = 0.30 * eng_sc + 0.20 * stab_sc + 0.20 * sync_sc + 0.15 * form_sc + 0.15 * flu_sc
    if overall >= 0.85:
        overall_status = "🟢 極佳"
    elif overall >= 0.70:
        overall_status = "🟡 良好"
    else:
        overall_status = "🔴 需關注"

    concern = []
    for c in children:
        reasons = []
        if float(c["avg_displacement_cm"]) > 15:
            reasons.append("抑制控制 / 穩定度偏低")
        if float(c["avg_error_ms"]) > 150:
            reasons.append("節奏同步誤差偏高")
        if float(c["avg_jerk"]) > 6:
            reasons.append("動作流暢度偏低")
        if reasons:
            concern.append(
                {
                    "child_id": c["child_id"],
                    "display_label": identity.display_label_for_child(c.get("student_id"), c.get("child_id")),
                    "reason": "；".join(reasons),
                    "priority": "high" if float(c["avg_displacement_cm"]) > 20 or float(c["avg_error_ms"]) > 220 else "medium",
                }
            )

    return {
        "check_timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "overall_status": f"{overall_status}（綜合分 {overall:.2f}）",
        "overall_score": round(float(overall), 3),
        "macro_metrics": {
            "group_engagement": {"value": eng, "status": eng_status, "interpretation": "群體關鍵點位移活躍比例（代理指標）"},
            "formation_stability": {"value": form_stab, "status": form_status, "interpretation": "隊形時間窗內幾何分類信心均值"},
            "space_utilization": {"value": std, "status": space_status, "interpretation": "熱區 3×3 分佈離散度（標準差）"},
        },
        "micro_metrics": {
            "sync_score": {"value_ms": round(sync_ms, 2), "status": sync_status, "interpretation": "個體平均同步誤差"},
            "stability_score": {"value_cm": round(stab_cm, 2), "status": stab_status, "interpretation": "停止信號後髖部位移（平均）"},
            "fluency_score": {"value_jerk": round(jerk, 3), "status": flu_status, "interpretation": "髖部軌跡 jerk 代理值"},
        },
        "concern_children": concern,
        "recommendations_summary": [
            "依紅黃燈檢視課程節奏與停止信號設計",
            "對關注名單加強一對一視線提示與分段任務",
        ],
    }
