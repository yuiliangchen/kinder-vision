# Agent 文件反向索引（`src/*.py` → `docs/agents/*.md`）

這份文件提供「程式檔 -> 最可能對應的說明」之反向索引，方便維護時快速判斷應參考哪份 `docs/agents/*.md`。

關聯度標記：
- `高`：主要責任，功能與該文件核心範圍直接對應。
- `中`：次要關聯，常被同一流程調用或依賴。
- `低`：間接關聯，僅提供共用基礎能力或包裝層。

## Core / Orchestration

- `src/__main__.py`
  - `高` `docs/agents/pipeline.md`
  - `中` `docs/agents/cli.md`
- `src/cli.py`
  - `高` `docs/agents/pipeline.md`
  - `中` `docs/agents/cli.md`
- `src/pipeline.py`
  - `高` `docs/agents/pipeline.md`
  - `高` `docs/agents/cli.md`
- `src/video_ingest.py`
  - `高` `docs/agents/pipeline.md`
- `src/segment.py`
  - `高` `docs/agents/pipeline.md`
- `src/timecode.py`
  - `中` `docs/agents/pipeline.md`
- `src/paths.py`
  - `中` `docs/agents/pipeline.md`
  - `中` `docs/agents/identity.md`

## Macro Analytics

- `src/macro_analytics.py`
  - `高` `docs/agents/macro_analytics.md`
  - `中` `docs/agents/cli.md`
- `src/viz.py`
  - `中` `docs/agents/macro_analytics.md`
  - `中` `docs/agents/micro_analytics.md`

## Micro Analytics

- `src/micro_analytics.py`
  - `高` `docs/agents/micro_analytics.md`
  - `中` `docs/agents/cli.md`
- `src/mediapipe_pose.py`
  - `高` `docs/agents/micro_analytics.md`
- `src/mediapipe_holistic.py`
  - `高` `docs/agents/micro_analytics.md`
- `src/mediapipe_kp_common.py`
  - `中` `docs/agents/micro_analytics.md`

## Identity / ReID

- `src/identity.py`
  - `高` `docs/agents/identity.md`
  - `中` `docs/agents/pipeline.md`
- `src/face_insight.py`
  - `高` `docs/agents/identity.md`

## Metrics / Validation

- `src/metrics_checker.py`
  - `高` `docs/agents/metrics_checker.md`
  - `中` `docs/agents/cli.md`
- `src/student_metrics_import.py`
  - `中` `docs/agents/metrics_checker.md`
- `src/student_longitudinal.py`
  - `中` `docs/agents/metrics_checker.md`
  - `中` `docs/agents/identity.md`

## Education Advice / Report

- `src/edu_advisor.py`
  - `高` `docs/agents/edu_advisor.md`
  - `中` `docs/agents/cli.md`
- `src/ai_edu.py`
  - `高` `docs/agents/edu_advisor.md`
- `src/student_report.py`
  - `中` `docs/agents/edu_advisor.md`
- `src/report_pdf.py`
  - `中` `docs/agents/edu_advisor.md`

## Package Metadata

- `src/__init__.py`
  - `低` `docs/agents/cli.md`

---

## Maintenance Rule (Recommended)

當你修改某個 `src/*.py` 時，若該檔案對應的 `docs/agents/*.md` 有描述流程、輸出格式或限制，建議同步檢查該 Markdown 是否需要更新，以避免「程式已改、說明未對齊」。
