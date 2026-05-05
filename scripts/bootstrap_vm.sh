#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "[bootstrap] Installing OS packages"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3 python3-venv python3-pip ffmpeg
else
  echo "[bootstrap] apt-get not found; please install python3/pip/ffmpeg manually."
fi

echo "[bootstrap] Creating virtual environment"
python3 -m venv .venv
source .venv/bin/activate

echo "[bootstrap] Upgrading pip"
python -m pip install --upgrade pip

echo "[bootstrap] Installing base requirements"
pip install -r requirements.txt

echo
echo "[bootstrap] Done."
echo "Optional packages:"
echo "  pip install -r requirements-insightface.txt"
echo "  pip install -r requirements-llm.txt"
echo "  pip install -r requirements-pdf.txt"
echo
echo "Recommended env vars:"
echo "  export KINDER_MEMORY_DIR=/var/lib/kinder-vision/memory"
echo "  export KINDER_TMP_DIR=/var/lib/kinder-vision/tmp"
