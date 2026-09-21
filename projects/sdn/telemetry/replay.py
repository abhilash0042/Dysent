"""
Replay 1-second windows from cicddos2019_temporal_windows.npz as live telemetry.

Each window row is treated as one source IP's 10-second history unfolded
second-by-second for demo purposes on Windows (no Mininet required).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator, Tuple

import numpy as np

logger = logging.getLogger(__name__)

WINDOWS_NPZ = Path(__file__).resolve().parents[3] / 'data' / 'processed' / 'cicddos2019_temporal_windows.npz'


def load_replay_sequences(max_windows: int | None = None):
    z = np.load(WINDOWS_NPZ, allow_pickle=True)
    X, y = z['X'], z['y']
    src = z['source_ip'] if 'source_ip' in z.files else np.array([f'10.0.0.{i % 250 + 1}' for i in range(len(y))])
    if max_windows:
        idx = np.random.default_rng(42).choice(len(y), min(max_windows, len(y)), replace=False)
        X, y, src = X[idx], y[idx], src[idx]
    return X, y, src.astype(str), list(z['class_names'])


def replay_stream(
    speed: float = 0.0,
    max_windows: int = 200,
    attack_only_after: int = 30,
) -> Iterator[Tuple[str, np.ndarray, float, int]]:
    """
    Yields (source_ip, raw_features_40, pps, label_index) one second at a time.

    First `attack_only_after` windows are biased toward benign (label 0).
    """
    X, y, src, _ = load_replay_sequences(max_windows)
    rng = np.random.default_rng(0)

    # Unscale is not stored; windows in NPZ are already scaled. Contract.scale_features
    # expects raw — for replay we pass scaled rows directly by temporarily identity-scaling
    # in the demo runner (see run_sdn_defense._replay_demo).

    order = np.arange(len(y))
    rng.shuffle(order)
    benign = np.where(y == 0)[0]
    attack = np.where(y != 0)[0]
    seq = list(benign[:attack_only_after]) + list(attack) + list(benign[attack_only_after:])
    seq = seq[:max_windows]

    for wi in seq:
        window = X[wi]  # (10, 40) already scaled
        ip = str(src[wi])
        label = int(y[wi])
        pps_base = 50.0 if label == 0 else 8000.0
        for t in range(window.shape[0]):
            pps = pps_base * (1.0 + 0.1 * rng.random())
            yield ip, window[t], pps, label
