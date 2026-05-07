#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR"

echo "[install-vllm] project_dir=$PROJECT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[install-vllm] python3 is required"
  exit 1
fi

echo "[install-vllm] installing system packages..."
sudo apt-get update
sudo apt-get install -y docker.io nvidia-container-toolkit ubuntu-drivers-common

echo "[install-vllm] configuring nvidia runtime for docker..."
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker

echo "[install-vllm] creating virtualenv if missing..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

echo "[install-vllm] installing python dependencies..."
. .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .
python -m pip install -U vllm

if [ ! -f "local.env" ]; then
  echo "[install-vllm] creating local.env from template..."
  cp local.env.example local.env
fi

echo "[install-vllm] done."
echo "[install-vllm] next steps:"
echo "  1) Verify driver: nvidia-smi"
echo "  2) If driver is not loaded, reboot host: sudo reboot"
echo "  3) Start vLLM: ./scripts/run-vllm.sh"
echo "  4) Run OCR: chandra-extract-pdf <file.pdf> --output-dir outputs/"
