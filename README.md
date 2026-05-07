# Kinder Vision 幼兒行為分析系統

基於論文《解碼教室裡的舞蹈：AI 如何看懂孩子的肢體學習語言》設計，結合電腦視覺與音樂教育心理學的輔助分析系統。

## 開發維護索引

- 程式檔與 agent 說明對應（含高/中/低關聯度）：`docs/AGENTS_REVERSE_INDEX.md`
- Agent／維護者說明（檔名沿用模組名）：`docs/agents/README.md`
- VM 部署指南：`docs/deploy-vm.md`
- 部署資源索引（腳本、`systemd` 範本）：`deploy/README.md`
- 本地範例影片慣例：`media/demo.mp4`（說明見 `media/README.md`）
- JSON 欄位範例（對齊 `docs/agents/*.md`）：`docs/skill-json-schemas.md`
- 環境變數範本：`.env.example`
- OpenClaw 專用 skill 設定：`skills/openclaw.skill.json`
- OpenClaw workflow 範例：`skills/openclaw.workflow.json`

## 核心分析技術 (Core Analytics Technologies)

### 1. 節奏同步度分析 (Rhythmic Synchronization)
- **技術**：`librosa` (音訊強拍偵測) + **MediaPipe Holistic** (肢體位移峰值偵測)。
- **原理**：將肢體動作（如跳躍、拍手）的峰值時間與音樂強拍進行毫秒級比對。
- **指標**：計算平均誤差 (ms)，評估幼兒的節奏感與對音樂信號的反應延遲。

### 2. 抑制控制分析 (Inhibitory Control)
- **技術**：音訊能量衰減偵測 (Audio Stop Signal) + 持續性位移追蹤。
- **原理**：自動識別音樂停止瞬間，並捕捉幼兒在隨後 1 秒內的身體座標變化。
- **指標**：累積位移量 (cm)。位移愈小，代表幼兒的衝動控制與自我調節能力愈強。

### 3. 動作流暢度分析 (Movement Fluency)
- **技術**：**Jerk Analysis (加加速度分析)**。
- **原理**：計算肢體運動加速度的變化率。
- **指標**：平均 Jerk 值 (m/s³)。流暢的動作具有穩定的加速度變化（低 Jerk），而僵硬或遲疑的動作則會產生劇烈的數值波動。

### 4. 個別追蹤軌跡 (Individual Trajectory)
- **技術**：**YOLOv8** + **ByteTrack** (多目標追蹤) + 透視投影轉換。
- **原理**：將監視器視角映射為教室 3D 平面座標，分析幼兒的移動路徑。
- **指標**：探索廣度、社交距離與移動速度變異，視覺化幼兒在空間中的參與程度。

## 技術棧 (Technology Stack)
- **Macro 分析**：YOLOv8-Pose (群體追蹤、隊形偵測)
- **Micro 分析**：MediaPipe Holistic (個體精細動作、表情與手指追蹤)
- **多目標追蹤**：ByteTrack
- **音訊處理**：librosa (BPM 與靜音偵測)

### 5. 人像資料庫與個案追蹤 (Face Database & ID Link)
- **技術**：**InsightFace** (特徵向量提取) + **Person Re-identification (ReID)**。
- **原理**：將幼兒臉部特徵轉化為去識別化的特徵向量（Embedding），實現跨時段數據歸戶。
- **指標**：跨日成長趨勢、個案動作流暢度改善曲線。

### 6. LLM 增強型教育建議 (LLM-Enhanced Advisor)
- **技術**：Large Language Model (LLM) 數據翻譯引擎。
- **原理**：將微觀與巨觀數據（如誤差 ms、位移 cm）轉譯為富有教育意義且具溫度的自然語言報告。
- **指標**：班級整體亮點、個案進步見證、具體家庭互動建議。

## 技術棧 (Technology Stack)
- **Macro 分析**：YOLOv8-Pose (群體追蹤、隊形偵測)
- **Micro 分析**：MediaPipe Holistic (個體精細動作)
- **身分識別**：InsightFace / ArcFace (ReID & Edge Recovery)
- **報告生成**：LLM-Enhanced Generator
- **音訊處理**：librosa (BPM 與靜音偵測)

## 系統技術總結 (v2.1 Summary)

### 1. 核心願景與定位
Kinder Vision 是一套結合 **電腦視覺 (Computer Vision)** 與 **教育心理學** 的 AI 輔助系統。其核心價值在於將原本難以量化的「幼兒音樂律動表現」，轉化為具備科學證據的「長期成長軌跡」。

### 2. 關鍵技術突破：個案追蹤與 ReID
系統從「單次匿名分析」演進為「具備記憶能力的追蹤系統」：
- **Identity Manager (身分中樞)**：利用 **InsightFace** 提取特徵向量，建立身分資料庫。
- **自動化歸戶邏輯**：透過歐幾里得距離計算，自動識別回流幼兒或標註新生。
- **環境邊緣化補償**：整合了外觀 ReID 與時空預測，解決了遮蔽或中斷問題。

### 3. 三大指標分析引擎
- **Rhythmic Sync**：毫秒級動作誤差量化。
- **Inhibitory Control**：測量靜止穩定度（位移 cm），評估衝動調節能力。
- **Movement Fluency**：應用 **Jerk Analysis** 評估肢體發育協調性。

### 4. LLM 增強型教育溝通
- **數據故事化**：將指標轉化為富有溫度的家長聯絡簿文字。
- **進步見證**：自動比對歷史存檔，生成成長趨勢報告。

## CLI 與環境變數（與程式對齊）

### 安裝

請在本機只使用專案根目錄的 **`.venv`**（不要用其它對照用虛擬環境目錄）：先 `python3 -m venv .venv`，再 `source .venv/bin/activate`，下列指令皆在此環境內執行。

```bash
pip install -r requirements.txt
# Linux/OpenClaw 草案（含平台條件）
# pip install -r requirements-linux.txt
# 可選：ArcFace 臉嵌入（軌跡 ReID 與片中點身分較準）
pip install -r requirements-insightface.txt
# 可選：教育報告末段 LLM 補充（OpenAI 相容 API）
pip install -r requirements-llm.txt
# 可選：HTTP API（FastAPI + Uvicorn）
pip install -r requirements-api.txt
```

### 基本執行

```bash
python -m src.cli <影片路徑> [--model yolov8n-pose.pt] [--stride 4] [--learn-identities] [--no-track] [--t0 T] [--t1 T]
# 或使用模組入口（等價）
python -m src <影片路徑> [--model yolov8n-pose.pt] [--stride 4] [--learn-identities] [--no-track] [--t0 T] [--t1 T]
```

常用參數（`--pose` 預設為 `pose`）：

| 參數 | 說明 |
|------|------|
| `--stride` | 取樣幀間隔，越大越快、越粗。 |
| `--model` | YOLO 權重路徑或模型名（預設 `yolov8n-pose.pt`，可改成新版做 A/B）。 |
| `--learn-identities` | 無法比對時將新身分寫入 `memory/identity_features.db.json`。 |
| `--no-track` | 停用 ByteTrack，改由左至右槽位對齊。 |
| `--t0` / `--t1` | 只分析原片時間區間（需本機 `ffmpeg`）。 |
| `--pose` | 人框內姿勢精化：`off`（僅 YOLO）、`pose`（MediaPipe Pose）、`holistic`（MediaPipe Holistic）。 |
| `--no-mediapipe` | 等同 `--pose off`。 |
| `--no-video-reid` | 停用整片軌跡 ReID（不產生 `micro.reid_by_track`）。 |
| `--no-llm` | 不呼叫 LLM，報告不含「## 五、AI 教學補充建議」。 |
| `--pdf` | 額外輸出合併 PDF（彙總 + 教育建議；需 `requirements-pdf.txt`）。 |
| `--no-accumulate-sessions` | 不寫入跨影片累積檔 `reports/students/<id>/sessions.jsonl`。 |

分析報告（同日 Markdown、PDF、`metrics/` 下個別 JSON）寫入 `reports/`；可設 `KINDER_REPORTS_DIR` 覆寫預設路徑（見 `.env.example`）。

MediaPipe `.task` 模型會快取於 `~/.cache/kinder-vision/`（首次執行會下載）。

### LLM（教育報告第五節）

實作見 `src/llm_edu.py`。預設會**嘗試**在機讀報告生成後附加 LLM 段落；若無 API Key 或未安裝 `openai`，會靜默略過（或將提示寫入 `micro.llm_warnings`）。

| 環境變數 | 說明 |
|----------|------|
| `KINDER_LLM_API_KEY` | 優先使用；未設則讀取 `OPENAI_API_KEY`。 |
| `KINDER_LLM_BASE_URL` | OpenAI 相容 API 根網址，預設 `https://api.openai.com/v1`。 |
| `KINDER_LLM_MODEL` | 模型名稱，預設 `gpt-4o-mini`。 |

自架相容端點（如 vLLM、LiteLLM、Azure OpenAI 等）時，請設好 `KINDER_LLM_BASE_URL` 與對應的 `KINDER_LLM_API_KEY`。

### HTTP API（可部署到 VM）

啟動：

```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

健康檢查：

```bash
curl http://127.0.0.1:8000/health
```

呼叫分析（非同步，立即回 `task_id`）：

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <your_key>" \
  -d '{
    "video_path": "media/demo.mp4",
    "model": "yolov8n-pose.pt",
    "stride": 4,
    "pose": "pose",
    "no_llm": true
  }'
```

查詢任務狀態（queued/running/succeeded/failed）：

```bash
curl -H "X-API-Key: <your_key>" http://127.0.0.1:8000/tasks/<task_id>
```

列出最近任務（預設 20 筆，可帶 `?limit=50`）：

```bash
curl -H "X-API-Key: <your_key>" http://127.0.0.1:8000/tasks
```

取消任務（queued/running）：

```bash
curl -X POST -H "X-API-Key: <your_key>" http://127.0.0.1:8000/tasks/<task_id>/cancel
```

可選安全設定（建議 VM）：

- 設定 `KINDER_API_KEY` 後，`/analyze`、`/tasks`、`/tasks/{id}` 需帶 `X-API-Key`。
- `KINDER_TASK_TTL_SEC` 可設定任務保留秒數（預設 `86400`，僅清理已完成任務）。
- 任務狀態會持久化至 `tmp/kinder-api-tasks.json`，服務重啟後可回讀（中斷中的任務會標記為 `cancelled`）。

範例（帶 API key）：

```bash
curl -H "X-API-Key: <your_key>" http://127.0.0.1:8000/tasks
```

### 身分與軌跡 ReID

- 片中點快照＋槽位：管線內 YOLO 取中間幀比對身分庫。
- **整片 ByteTrack ReID**（預設開啟）：沿 `track_id` 累積 ArcFace（若已安裝 InsightFace）與上半身外觀嵌入，軌跡平均後比對；結果在 `kinder-micro-result.json` 的 `reid_by_track`，並優先合併到各 `children` 的 `student_id`。
- 關閉軌跡 ReID：`--no-video-reid`。

---
*最後更新：2026-05-05 | 技術開發：Antigravity AI*


