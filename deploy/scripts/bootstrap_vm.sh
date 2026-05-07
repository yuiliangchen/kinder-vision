#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

echo "[bootstrap] Installing OS packages"
if command -v apt-get >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y curl bzip2 ffmpeg
else
  echo "[bootstrap] apt-get not found; please install curl/bzip2/ffmpeg manually."
fi

CONDA_ROOT="$HOME/miniconda"
CONDA_SH="$CONDA_ROOT/etc/profile.d/conda.sh"
CONDA_ENV_NAME="kinder-vision-py311"

if [[ -d "$CONDA_ROOT" ]]; then
  echo "[bootstrap] Found existing miniconda at $CONDA_ROOT"
else
  echo "[bootstrap] miniconda not found; installing to $CONDA_ROOT"
  ARCH="$(uname -m)"
  if [[ "$ARCH" == "x86_64" ]]; then
    CONDA_INSTALLER_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh"
  elif [[ "$ARCH" == "aarch64" ]]; then
    CONDA_INSTALLER_URL="https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-aarch64.sh"
  else
    echo "[bootstrap] Unsupported architecture: $ARCH"
    exit 1
  fi
  TMP_INSTALLER="/tmp/miniconda-installer.sh"
  curl -fsSL "$CONDA_INSTALLER_URL" -o "$TMP_INSTALLER"
  bash "$TMP_INSTALLER" -b -p "$CONDA_ROOT"
  rm -f "$TMP_INSTALLER"
fi

if [[ ! -f "$CONDA_SH" ]]; then
  echo "[bootstrap] Cannot find conda init script: $CONDA_SH"
  exit 1
fi

source "$CONDA_SH"

echo "[bootstrap] Ensuring conda env: $CONDA_ENV_NAME (python=3.11)"
if conda env list | awk '{print $1}' | while read -r name; do [[ "$name" == "$CONDA_ENV_NAME" ]] && exit 0; done; then
  conda install -n "$CONDA_ENV_NAME" -y python=3.11
else
  conda create -n "$CONDA_ENV_NAME" -y python=3.11
fi

echo "[bootstrap] Upgrading pip"
conda run -n "$CONDA_ENV_NAME" python -m pip install --upgrade pip

echo "[bootstrap] Installing base requirements"
conda run -n "$CONDA_ENV_NAME" pip install -r requirements.txt

echo
echo "[bootstrap] Done."
echo "Conda env: $CONDA_ENV_NAME"
echo "Python bin: $CONDA_ROOT/envs/$CONDA_ENV_NAME/bin/python"
echo "Uvicorn bin: $CONDA_ROOT/envs/$CONDA_ENV_NAME/bin/uvicorn"
echo "Optional packages:"
echo "  conda run -n $CONDA_ENV_NAME pip install -r requirements-insightface.txt"
echo "  conda run -n $CONDA_ENV_NAME pip install -r requirements-ai.txt"
echo "  conda run -n $CONDA_ENV_NAME pip install -r requirements-pdf.txt"
echo
echo "Recommended env vars:"
echo "  export KINDER_MEMORY_DIR=/var/lib/kinder-vision/memory"
echo "  export KINDER_TMP_DIR=/var/lib/kinder-vision/tmp"
echo "  export KINDER_REPORTS_DIR=/var/lib/kinder-vision/reports"
