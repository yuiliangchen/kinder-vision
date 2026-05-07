# pipeline — 核心調度（對齊 `src/pipeline.py`）

## 角色定位
負責啟動並串接完整分析管線：影片讀取 -> 身分映射 -> macro -> micro -> metrics -> 教學報告 -> 檔案落地。

---

## 觸發時機
- 使用者要求「分析影片 / 跑完整流程」。
- CLI 執行 `python -m src.cli <video>`（或 `python -m src`）。

---

## 實際流程（以程式為準）

### Step 1: 影片與區間處理
- 讀取影片 meta（fps、frame_count、duration）。
- 若提供 `t0/t1`，先用 `ffmpeg` 匯出片段（`tmp/kinder-segment.mp4`），後續皆以片段分析。

### Step 2: 中間幀身分映射（slot map）
- 使用 YOLO 在影片中間幀偵測人框，按 x 座標由左到右排序成槽位。
- 優先嘗試 ArcFace（若可用），否則用外觀 embedding。
- 以 `identity.assign_identity` 比對 `memory/identity_features.db.json`，可依 `learn_identities` 寫入新身分。
- 輸出：`tmp/kinder-identity-map.json`。

### Step 3: 巨觀分析（Macro）
- 呼叫 `src.macro_analytics.run_macro(...)`。
- 產出 `tmp/kinder-macro-result.json` 與 `tmp/kinder-heatmap.png`。
- 同步機讀摘要到 `reports/YYYY-MM-DD-kinder-macro.md`。

### Step 4: 微觀分析（Micro）
- 呼叫 `src.micro_analytics.run_micro(...)`，預設使用 ByteTrack；無法穩定追蹤時會回退到「槽位對齊（無追蹤）」。
- 可選姿勢後端：`off | pose | holistic`（MediaPipe 初始化失敗會回退僅 YOLO 並寫 warnings）。
- 若啟用 `use_video_reid`，會輸出 `reid_by_track`。
- 產出：`tmp/kinder-micro-result.json` 與個別軌跡圖 `tmp/kinder-child-*-trajectory.png`。

### Step 5: 身分合併與名稱正規化
- 先採用 `micro.reid_by_track` 的軌跡 ReID；缺失時回退中間幀槽位映射。
- 對外顯示名稱統一轉成「孩子 N」。

### Step 6: 指標核查與教育建議
- `src.metrics_checker.run_metrics(macro, micro)` -> `tmp/kinder-metrics-check.json`。
- `src.edu_advisor.render_edu_markdown(...)` -> `tmp/kinder-report.md`。
- 若 `use_llm=True`，嘗試附加「## 五、AI 教學補充建議」（無 key 或套件缺失會靜默略過並紀錄 warning）。

### Step 7: 歸檔與可選 PDF
- 同步寫入 `reports/` 同日摘要檔（macro/micro/metrics/edu/analysis）。
- 每位幼兒寫入 `reports/metrics/YYYY-MM-DD_<student_id>_metrics.json`。
- 預設累積 `memory/students/<student_id>/sessions.jsonl`（可由 `--no-accumulate-sessions` 關閉）。個人長期報告預設寫入 `reports/students/<slug>/`。
- 若 `emit_pdf=True`，輸出 `tmp/kinder-report.pdf` 並複製到 `reports/<timestamp>-kinder-report.pdf`。

---

## 主要輸出檔
- `tmp/kinder-identity-map.json`
- `tmp/kinder-macro-result.json`
- `tmp/kinder-micro-result.json`
- `tmp/kinder-metrics-check.json`
- `tmp/kinder-report.md`
- `reports/YYYY-MM-DD-kinder-report.md`（含前置自動彙總段落 + 教育建議）

---

## 限制與原則
- 僅為教學輔助，不替代教師判斷。
- 對外應使用去識別稱呼（孩子 N）。
- 若模型或依賴不可用，應回退並在 `warnings` 清楚註記，而非中止整個流程。
