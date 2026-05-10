#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

# Optional flags:
#   SKIP_OPTIONAL=1       skip installing optional groups (insightface/ai/pdf/api)
#   SKIP_INSIGHTFACE=1    skip insightface group only
#   SKIP_AI=1             skip ai (openai) group only
#   SKIP_PDF=1            skip pdf (markdown/weasyprint) group only
#   SKIP_API=1            skip api (fastapi/uvicorn) group only
SKIP_OPTIONAL="${SKIP_OPTIONAL:-0}"
SKIP_INSIGHTFACE="${SKIP_INSIGHTFACE:-$SKIP_OPTIONAL}"
SKIP_AI="${SKIP_AI:-$SKIP_OPTIONAL}"
SKIP_PDF="${SKIP_PDF:-$SKIP_OPTIONAL}"
SKIP_API="${SKIP_API:-$SKIP_OPTIONAL}"

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

# shellcheck disable=SC1090
source "$CONDA_SH"

echo "[bootstrap] Ensuring conda env: $CONDA_ENV_NAME (python=3.11)"
if conda env list | awk '{print $1}' | grep -Fxq "$CONDA_ENV_NAME"; then
  echo "[bootstrap] Env exists; ensuring python=3.11 is installed"
  conda install -n "$CONDA_ENV_NAME" -y python=3.11
else
  conda create -n "$CONDA_ENV_NAME" -y python=3.11
fi

PIP=(conda run --no-capture-output -n "$CONDA_ENV_NAME" pip)

echo "[bootstrap] Upgrading pip"
"${PIP[@]}" install --upgrade pip

echo "[bootstrap] Installing base requirements (requirements.txt)"
"${PIP[@]}" install -r requirements.txt

if [[ "$SKIP_API" != "1" ]]; then
  echo "[bootstrap] Installing API requirements (requirements-api.txt)"
  "${PIP[@]}" install -r requirements-api.txt
else
  echo "[bootstrap] Skipping API requirements (SKIP_API=1)"
fi

if [[ "$SKIP_INSIGHTFACE" != "1" ]]; then
  echo "[bootstrap] Installing InsightFace requirements (requirements-insightface.txt)"
  "${PIP[@]}" install -r requirements-insightface.txt
else
  echo "[bootstrap] Skipping InsightFace requirements (SKIP_INSIGHTFACE=1)"
fi

if [[ "$SKIP_AI" != "1" ]]; then
  echo "[bootstrap] Installing AI requirements (requirements-ai.txt)"
  "${PIP[@]}" install -r requirements-ai.txt
else
  echo "[bootstrap] Skipping AI requirements (SKIP_AI=1)"
fi

if [[ "$SKIP_PDF" != "1" ]]; then
  echo "[bootstrap] Installing PDF requirements (requirements-pdf.txt)"
  "${PIP[@]}" install -r requirements-pdf.txt
else
  echo "[bootstrap] Skipping PDF requirements (SKIP_PDF=1)"
fi

echo
echo "[bootstrap] Done."
echo "Conda env: $CONDA_ENV_NAME"
echo "Python bin: $CONDA_ROOT/envs/$CONDA_ENV_NAME/bin/python"
echo "Uvicorn bin: $CONDA_ROOT/envs/$CONDA_ENV_NAME/bin/uvicorn"
echo
echo "To skip optional groups on re-run:"
echo "  SKIP_OPTIONAL=1 $0           # skip api/insightface/ai/pdf"
echo "  SKIP_INSIGHTFACE=1 $0        # skip just insightface"
echo "  SKIP_AI=1 SKIP_PDF=1 $0      # combine flags"
echo
echo "Recommended env vars:"
echo "  export KINDER_MEMORY_DIR=/var/lib/kinder-vision/memory"
echo "  export KINDER_TMP_DIR=/var/lib/kinder-vision/tmp"
echo "  export KINDER_REPORTS_DIR=/var/lib/kinder-vision/reports"
