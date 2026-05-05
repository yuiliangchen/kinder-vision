# systemd Service Template

本目錄提供以下範本：

- `kinder-vision-worker.service`：單次影片分析 worker
- `kinder-vision-api.service`：FastAPI 服務（`/health`, `/analyze`）

## 使用方式

1. 先修改服務檔中的路徑與帳號：
   - `User=...`
   - `WorkingDirectory=...`
   - `ExecStart=...`
   - 若使用環境檔：建立 `/etc/kinder-vision/kinder-vision.env`
2. 安裝到 systemd：

```bash
sudo cp deploy/systemd/kinder-vision-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable kinder-vision-worker.service
sudo systemctl start kinder-vision-worker.service
```

或使用一鍵腳本（建議）：

```bash
bash scripts/install_systemd.sh api
# 或
bash scripts/install_systemd.sh worker
```

3. 檢查狀態與日誌：

```bash
sudo systemctl status kinder-vision-worker.service
journalctl -u kinder-vision-worker.service -f
```

啟動 API 版本（擇一）：

```bash
sudo cp deploy/systemd/kinder-vision-api.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable kinder-vision-api.service
sudo systemctl start kinder-vision-api.service
sudo systemctl status kinder-vision-api.service
journalctl -u kinder-vision-api.service -f
```

## 注意

- 目前範本是「單次影片執行」形式，`ExecStart` 需改成你的實際影片來源策略。
- API 範本預設監聽 `0.0.0.0:8000`，請配合防火牆與反向代理設定。

## EnvironmentFile 範例

建立 `/etc/kinder-vision/kinder-vision.env`：

```bash
KINDER_MEMORY_DIR=/var/lib/kinder-vision/memory
KINDER_TMP_DIR=/var/lib/kinder-vision/tmp
KINDER_API_KEY=replace-with-strong-token
KINDER_TASK_TTL_SEC=86400
```
