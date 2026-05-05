# SKILL Reverse Index (`kv/*.py` -> `SKILL.md`)

這份文件提供「程式檔 -> 最可能對應 Skill」的反向索引，方便維護時快速判斷應參考哪份 `SKILL.md`。

關聯度標記：
- `高`：主要責任，功能與該 Skill 核心範圍直接對應。
- `中`：次要關聯，常被同一流程調用或依賴。
- `低`：間接關聯，僅提供共用基礎能力或包裝層。

## Core / Orchestration

- `kv/__main__.py`
  - `高` `kinder-vision-core/SKILL.md`
  - `中` `kinder-vision/SKILL.md`
- `kv/cli.py`
  - `高` `kinder-vision-core/SKILL.md`
  - `中` `kinder-vision/SKILL.md`
- `kv/pipeline.py`
  - `高` `kinder-vision-core/SKILL.md`
  - `高` `kinder-vision/SKILL.md`
- `kv/video_ingest.py`
  - `高` `kinder-vision-core/SKILL.md`
- `kv/segment.py`
  - `高` `kinder-vision-core/SKILL.md`
- `kv/timecode.py`
  - `中` `kinder-vision-core/SKILL.md`
- `kv/paths.py`
  - `中` `kinder-vision-core/SKILL.md`
  - `中` `kinder-identity-manager/SKILL.md`

## Macro Analytics

- `kv/macro_analytics.py`
  - `高` `kinder-macro-analytics/SKILL.md`
  - `中` `kinder-vision/SKILL.md`
- `kv/viz.py`
  - `中` `kinder-macro-analytics/SKILL.md`
  - `中` `kinder-micro-analytics/SKILL.md`

## Micro Analytics

- `kv/micro_analytics.py`
  - `高` `kinder-micro-analytics/SKILL.md`
  - `中` `kinder-vision/SKILL.md`
- `kv/mediapipe_pose.py`
  - `高` `kinder-micro-analytics/SKILL.md`
- `kv/mediapipe_holistic.py`
  - `高` `kinder-micro-analytics/SKILL.md`
- `kv/mediapipe_kp_common.py`
  - `中` `kinder-micro-analytics/SKILL.md`

## Identity / ReID

- `kv/identity.py`
  - `高` `kinder-identity-manager/SKILL.md`
  - `中` `kinder-vision-core/SKILL.md`
- `kv/face_insight.py`
  - `高` `kinder-identity-manager/SKILL.md`

## Metrics / Validation

- `kv/metrics_checker.py`
  - `高` `kinder-metrics-checker/SKILL.md`
  - `中` `kinder-vision/SKILL.md`
- `kv/student_metrics_import.py`
  - `中` `kinder-metrics-checker/SKILL.md`
- `kv/student_longitudinal.py`
  - `中` `kinder-metrics-checker/SKILL.md`
  - `中` `kinder-identity-manager/SKILL.md`

## Education Advice / Report

- `kv/edu_advisor.py`
  - `高` `kinder-edu-advisor/SKILL.md`
  - `中` `kinder-vision/SKILL.md`
- `kv/llm_edu.py`
  - `高` `kinder-edu-advisor/SKILL.md`
- `kv/student_report.py`
  - `中` `kinder-edu-advisor/SKILL.md`
- `kv/report_pdf.py`
  - `中` `kinder-edu-advisor/SKILL.md`

## Package Metadata

- `kv/__init__.py`
  - `低` `kinder-vision/SKILL.md`

---

## Maintenance Rule (Recommended)

當你修改某個 `kv/*.py` 時，若該檔案對應的 Skill 有描述流程、輸出格式或限制，建議同步檢查該 `SKILL.md` 是否需要更新，以避免「程式已改、Skill 文件未對齊」。
