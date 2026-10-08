#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
export TMPDIR="$HOME/tmp"
export PIP_CACHE_DIR="$HOME/.cache/pip"
mkdir -p "$TMPDIR" "$PIP_CACHE_DIR"
cd /mnt/c/projects/Dysent-1

python3 -m pip install --user --break-system-packages -U pip wheel
python3 -m pip install --user --break-system-packages 'tensorflow[and-cuda]' scikit-learn numpy cryptography
python3 scripts/check_wsl_tf_gpu.py
