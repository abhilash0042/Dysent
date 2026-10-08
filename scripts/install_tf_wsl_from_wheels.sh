#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
export TMPDIR="$HOME/tmp"
export PIP_CACHE_DIR="$HOME/.cache/pip"
mkdir -p "$TMPDIR" "$PIP_CACHE_DIR"

cd /mnt/c/projects/Dysent-1
WHEEL_DIR="/mnt/c/projects/Dysent-1/.wsl_wheels"

python3 -m pip install --user --break-system-packages -U pip wheel
# Core TF from local wheel if present
if ls "$WHEEL_DIR"/tensorflow-*.whl >/dev/null 2>&1; then
  python3 -m pip install --user --break-system-packages "$WHEEL_DIR"/tensorflow-*.whl
else
  python3 -m pip install --user --break-system-packages "tensorflow==2.21.0"
fi

# CUDA plugin packages for GPU
python3 -m pip install --user --break-system-packages \
  "nvidia-cublas-cu12" "nvidia-cuda-nvrtc-cu12" "nvidia-cuda-runtime-cu12" \
  "nvidia-cudnn-cu12" "nvidia-cufft-cu12" "nvidia-curand-cu12" \
  "nvidia-cusolver-cu12" "nvidia-cusparse-cu12" "nvidia-nccl-cu12" \
  "nvidia-nvjitlink-cu12" \
  scikit-learn numpy cryptography

python3 scripts/check_wsl_tf_gpu.py
