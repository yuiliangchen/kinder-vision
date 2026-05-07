# 部署資源

與「如何把 Kinder Vision 裝到機器上、如何常駐」相關的檔案都集中在這裡。

| 路徑 | 用途 |
|------|------|
| `deploy/scripts/bootstrap_vm.sh` | Linux VM 上一鍵建立 venv、安裝 `requirements.txt` 與系統依賴提示 |
| `deploy/scripts/install_systemd.sh` | 將 `deploy/systemd/*.service` 安裝到本機 systemd（`api` \| `worker`） |
| `deploy/systemd/` | service 範本（請依環境改 `User`、`WorkingDirectory`、`ExecStart`） |

操作流程與環境變數說明請見：**[`docs/deploy-vm.md`](../docs/deploy-vm.md)**。
