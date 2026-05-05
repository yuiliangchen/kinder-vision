#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SYSTEMD_DIR="$ROOT_DIR/deploy/systemd"

MODE="${1:-api}" # api | worker
SERVICE_NAME="kinder-vision-api.service"
if [[ "$MODE" == "worker" ]]; then
  SERVICE_NAME="kinder-vision-worker.service"
elif [[ "$MODE" != "api" ]]; then
  echo "Usage: $0 [api|worker]"
  exit 1
fi

SRC_SERVICE="$SYSTEMD_DIR/$SERVICE_NAME"
DST_SERVICE="/etc/systemd/system/$SERVICE_NAME"
ENV_DIR="/etc/kinder-vision"
ENV_FILE="$ENV_DIR/kinder-vision.env"

if [[ ! -f "$SRC_SERVICE" ]]; then
  echo "Service file not found: $SRC_SERVICE"
  exit 1
fi

echo "[install] Installing $SERVICE_NAME"
sudo mkdir -p "$ENV_DIR"
sudo cp "$SRC_SERVICE" "$DST_SERVICE"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[install] Creating $ENV_FILE from .env.example"
  sudo cp "$ROOT_DIR/.env.example" "$ENV_FILE"
  sudo chmod 600 "$ENV_FILE"
else
  echo "[install] Keep existing env file: $ENV_FILE"
fi

echo "[install] Reloading systemd"
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

echo "[install] Done."
echo "Service status:"
sudo systemctl --no-pager --full status "$SERVICE_NAME" || true
echo
echo "Tail logs:"
echo "  journalctl -u $SERVICE_NAME -f"
