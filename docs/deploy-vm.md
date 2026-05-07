# Deploy on VM

本文件提供在 Linux VM（Ubuntu/Debian）部署 Kinder Vision 的最小可行流程。

## 1) 系統需求

- Python 3.10+
- `ffmpeg`（區間切片需要）
- 可寫入的資料目錄（`KINDER_MEMORY_DIR`、`KINDER_TMP_DIR`、`KINDER_REPORTS_DIR`）

## 2) 一鍵安裝（建議）

在專案根目錄執行：

```bash
bash deploy/scripts/bootstrap_vm.sh
```

## 3) 手動安裝

```bash
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip ffmpeg

python3 -m venv .venv   # 僅使用專案根目錄的 .venv，勿另建對照環境
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

可選依賴：

```bash
pip install -r requirements-insightface.txt
pip install -r requirements-llm.txt
pip install -r requirements-pdf.txt
pip install -r requirements-api.txt
```

## 4) 環境變數（VM 建議）

可把輸出目錄指到持久磁碟：

```bash
export KINDER_MEMORY_DIR=/var/lib/kinder-vision/memory
export KINDER_TMP_DIR=/var/lib/kinder-vision/tmp
export KINDER_REPORTS_DIR=/var/lib/kinder-vision/reports
```

LLM（可選）：

```bash
export KINDER_LLM_API_KEY=...
export KINDER_LLM_BASE_URL=https://api.openai.com/v1
export KINDER_LLM_MODEL=gpt-4o-mini
```

API 安全與任務保留（建議）：

```bash
export KINDER_API_KEY=replace-with-strong-token
export KINDER_TASK_TTL_SEC=86400
```

## 5) 執行

```bash
python -m src "<video_path>" --stride 4 --pose pose
```

常用選項：

- `--no-track`
- `--no-video-reid`
- `--no-llm`
- `--pdf`
- `--no-accumulate-sessions`

## 6) 啟動 API（可選）

```bash
uvicorn src.api:app --host 0.0.0.0 --port 8000
```

若要用 systemd 常駐（建議）：

```bash
bash deploy/scripts/install_systemd.sh api
```

測試：

```bash
curl http://127.0.0.1:8000/health
```

非同步分析：

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${KINDER_API_KEY}" \
  -d '{"video_path":"media/demo.mp4","model":"yolov8n-pose.pt","stride":4,"pose":"pose","no_llm":true}'
```

用回傳的 `task_id` 查詢：

```bash
curl http://127.0.0.1:8000/tasks/<task_id>
```

列出最近任務：

```bash
curl http://127.0.0.1:8000/tasks?limit=50
```

取消任務：

```bash
curl -X POST -H "X-API-Key: ${KINDER_API_KEY}" http://127.0.0.1:8000/tasks/<task_id>/cancel
```

## 7) 產出位置

- 暫存：`$KINDER_TMP_DIR`（未設定時為 `./tmp`）
- 身分資料庫：`$KINDER_MEMORY_DIR/identity_features.db.json`（未設定時為 `./memory`）
- 分析報告、個別 metrics、跨影片累積：`$KINDER_REPORTS_DIR`（未設定時為 `./reports`）
  - `metrics/`：單次分析 per-child JSON
  - `students/<slug>/`：`sessions.jsonl`（跨影片累積）、`longitudinal-report.md`（個人長期報告）等

升級自舊版時：若曾有 `memory/metrics/*.json`，請搬到 `reports/metrics/`；若曾有 `memory/students/`，請搬到 `reports/students/`（或調整 `KINDER_REPORTS_DIR`／符號連結）。

## 8) 健康檢查與故障排除

### Linux 套件 smoke test（建議先跑）

```bash
python -m src.scripts.smoke_linux
```

### Smoke test（部署後先跑）

1. 健康檢查：

```bash
curl http://127.0.0.1:8000/health
```

2. 建立任務（請替換影片路徑與 API key）：

```bash
curl -X POST http://127.0.0.1:8000/analyze \
  -H "Content-Type: application/json" \
  -H "X-API-Key: ${KINDER_API_KEY}" \
  -d '{"video_path":"/data/media/demo.mp4","stride":4,"pose":"pose","no_llm":true}'
```

3. 查詢任務：

```bash
curl -H "X-API-Key: ${KINDER_API_KEY}" http://127.0.0.1:8000/tasks
curl -H "X-API-Key: ${KINDER_API_KEY}" http://127.0.0.1:8000/tasks/<task_id>
```

### 基本壓測（API 可用性）

若 VM 有 `ab`（apachebench）：

```bash
ab -n 100 -c 10 -H "X-API-Key: ${KINDER_API_KEY}" http://127.0.0.1:8000/health
```

或用 `curl` 快速連續測試：

```bash
for i in $(seq 1 20); do
  curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8000/health
done
```

- `ffmpeg` 找不到：`ffmpeg -version`
- Python 套件問題：`python -m pip list`
- LLM 無輸出：檢查 `KINDER_LLM_API_KEY` 與 `requirements-llm.txt` 是否已安裝
- MediaPipe 不可用：流程會回退僅 YOLO，並在 `micro.warnings` 記錄原因
- API 重啟後任務仍可查：狀態保存在 `tmp/kinder-api-tasks.json`（中斷中的任務會標記為 cancelled）
