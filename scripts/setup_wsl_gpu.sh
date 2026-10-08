#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
cd /mnt/c/projects/Dysent-1

if ! python3 -m pip --version >/dev/null 2>&1; then
  curl -sS https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip.py
  python3 /tmp/get-pip.py --user --break-system-packages
fi

python3 -m pip install --user --break-system-packages -U pip wheel
python3 -m pip install --user --break-system-packages 'tensorflow[and-cuda]' scikit-learn numpy cryptography

python3 scripts/check_wsl_tf_gpu.py
