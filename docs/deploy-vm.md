# Deploy on VM

本文件提供在 Linux VM（Ubuntu/Debian）部署 Kinder Vision 的最小可行流程。

## 1) 系統需求

- 建議使用 Miniconda + Python 3.11（MediaPipe 在 Python 3.13 上相容性較差）
- `ffmpeg`（區間切片需要）
- 可寫入的資料目錄（`KINDER_MEMORY_DIR`、`KINDER_TMP_DIR`、`KINDER_REPORTS_DIR`）

## 2) 一鍵安裝（建議）

在專案根目錄執行：

```bash
bash deploy/scripts/bootstrap_vm.sh
```

## 3) 手動安裝

```bash
# 先檢查是否已有 ~/miniconda；有就直接用，沒有才安裝
if [ -d "$HOME/miniconda" ]; then
  echo "use existing miniconda"
else
  sudo apt-get update
  sudo apt-get install -y curl bzip2 ffmpeg
  curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o /tmp/miniconda.sh
  bash /tmp/miniconda.sh -b -p "$HOME/miniconda"
fi

source "$HOME/miniconda/etc/profile.d/conda.sh"
conda create -n kinder-vision-py311 -y python=3.11
conda run -n kinder-vision-py311 python -m pip install --upgrade pip
conda run -n kinder-vision-py311 pip install -r requirements.txt
```

可選依賴：

```bash
conda run -n kinder-vision-py311 pip install -r requirements-insightface.txt
conda run -n kinder-vision-py311 pip install -r requirements-ai.txt
conda run -n kinder-vision-py311 pip install -r requirements-pdf.txt
conda run -n kinder-vision-py311 pip install -r requirements-api.txt
```

## 4) 環境變數（VM 建議）

可把輸出目錄指到持久磁碟：

```bash
export KINDER_MEMORY_DIR=/var/lib/kinder-vision/memory
export KINDER_TMP_DIR=/var/lib/kinder-vision/tmp
export KINDER_REPORTS_DIR=/var/lib/kinder-vision/reports
```

AI（可選）：

```bash
export KINDER_AI_API_KEY=...
export KINDER_AI_BASE_URL=https://api.openai.com/v1
export KINDER_AI_MODEL=gpt-4o-mini
```

API 安全與任務保留（建議）：

```bash
export KINDER_API_KEY=replace-with-strong-token
export KINDER_TASK_TTL_SEC=86400
```

## 5) 執行

```bash
$HOME/miniconda/envs/kinder-vision-py311/bin/python -m src "<video_path>" --stride 4 --pose pose
```

常用選項：

- `--no-track`
- `--no-video-reid`
- `--no-ai`
- `--pdf`
- `--no-accumulate-sessions`

## 6) 啟動 API（可選）

```bash
$HOME/miniconda/envs/kinder-vision-py311/bin/uvicorn src.api:app --host 0.0.0.0 --port 8000
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
  -d '{"video_path":"media/demo.mp4","model":"yolov8n-pose.pt","stride":4,"pose":"pose","no_ai":true}'
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
- 身分與跨影片累積：`$KINDER_MEMORY_DIR`（未設定時為 `./memory`）：`identity_features.db.json`、`students/<slug>/sessions.jsonl`
- 分析報告、個別 metrics、個人長期報告輸出：`$KINDER_REPORTS_DIR`（未設定時為 `./reports`）
  - `metrics/`：單次分析 per-child JSON
  - `students/<slug>/`：個人長期 `longitudinal-report.md`／`.pdf`（累積 JSONL 在 `memory/students/`）

升級自舊版時：若曾有 `memory/metrics/*.json`，請搬到 `reports/metrics/`。若曾把 `sessions.jsonl` 放在 `reports/students/<slug>/`，請移回 `memory/students/<slug>/`。

## 8) 健康檢查與故障排除

### Linux 套件 smoke test（建議先跑）

```bash
$HOME/miniconda/envs/kinder-vision-py311/bin/python -m src.scripts.smoke_linux
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
  -d '{"video_path":"/data/media/demo.mp4","stride":4,"pose":"pose","no_ai":true}'
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
- AI 無輸出：檢查 `KINDER_AI_API_KEY` 與 `requirements-ai.txt` 是否已安裝
- MediaPipe 不可用：流程會回退僅 YOLO，並在 `micro.warnings` 記錄原因
- API 重啟後任務仍可查：狀態保存在 `tmp/kinder-api-tasks.json`（中斷中的任務會標記為 cancelled）
