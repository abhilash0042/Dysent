"""Load models/sdn_model_contract.json — single source of truth for inference."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_CONTRACT = Path(__file__).resolve().parents[2] / 'models' / 'sdn_model_contract.json'


class SDNModelContract:
    def __init__(self, data: dict[str, Any]):
        self.raw = data
        self.model_path = Path(data['model_path'])
        self.input_shape = tuple(data['input_shape'])  # (timesteps, features)
        self.num_classes = int(data['num_classes'])
        self.class_names = list(data['class_names'])
        self.feature_names = list(data['feature_names'])
        self.benign_index = int(data.get('benign_index', 0))
        self.mean = np.array(data['scaler']['mean_40'], dtype=np.float32)
        self.scale = np.array(data['scaler']['scale_40'], dtype=np.float32)
        self.scale[self.scale == 0] = 1.0

        thr = data.get('thresholds', {})
        self.alert_threshold = float(thr.get('alert', 0.80))
        self.block_threshold = float(thr.get('block', 0.90))
        self.rate_limit_threshold = float(thr.get('rate_limit', 0.60))
        self.pps_threshold = float(thr.get('pps', 500.0))

    @classmethod
    def load(cls, path: Path | str | None = None) -> 'SDNModelContract':
        path = Path(path) if path else DEFAULT_CONTRACT
        with open(path, 'r', encoding='utf-8') as f:
            return cls(json.load(f))

    def scale_features(self, x: np.ndarray) -> np.ndarray:
        """x: (40,) or (T, 40) raw CIC features."""
        return (x - self.mean) / self.scale

    def resolve_model_path(self) -> Path:
        p = self.model_path
        if p.exists():
            return p
        alt = Path(__file__).resolve().parents[2] / 'models' / p.name
        if alt.exists():
            return alt
        raise FileNotFoundError(f'Model not found: {p} or {alt}')
