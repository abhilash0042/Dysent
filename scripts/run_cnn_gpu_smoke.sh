#!/usr/bin/env bash
set -euo pipefail
export PATH="$HOME/.local/bin:$PATH"
cd /mnt/c/projects/Dysent-1

echo "=== GPU check ==="
python3 scripts/check_wsl_tf_gpu.py

echo "=== CNN Byzantine smoke on GPU ==="
python3 experiments/federated_learning/run_real_byzantine_fl.py \
  --smoke \
  --output results/real_byzantine_fl_smoke.json
