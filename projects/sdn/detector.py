"""Per-source sliding window + contract-bound Keras inference."""

from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional

import numpy as np

from projects.sdn.contract import SDNModelContract

logger = logging.getLogger(__name__)


@dataclass
class DetectionAlert:
    source_ip: str
    attack_class: str
    attack_index: int
    attack_score: float
    benign_prob: float
    pps: float
    window_filled: int
    incomplete_ratio: float = 0.0
    concurrent: int = 0
    mean_iat_us: float = 0.0


class SDNDetector:
    """
    Maintains a ring buffer of scaled feature vectors per source IP.
    When the buffer reaches contract timesteps, runs the loaded model.

    Swap models by pointing sdn_model_contract.json at a new .keras file —
    no controller changes required.
    """

    def __init__(self, contract: SDNModelContract | None = None, contract_path: str | None = None, pad_incomplete: bool = False):
        self.contract = contract or SDNModelContract.load(contract_path)
        self.timesteps, self.n_features = self.contract.input_shape
        self._buffers: Dict[str, Deque[np.ndarray]] = {}
        self._pps: Dict[str, float] = {}
        self._model = None
        self.pad_incomplete = pad_incomplete

    def _load_model(self):
        if self._model is None:
            import keras
            path = self.contract.resolve_model_path()
            logger.info('Loading SDN model from %s', path)
            self._model = keras.models.load_model(path)

    def observe(
        self,
        source_ip: str,
        raw_features: np.ndarray,
        packets_this_second: float = 0.0,
        *,
        features_already_scaled: bool = False,
        incomplete_ratio: float = 0.0,
        concurrent: int = 0,
        mean_iat_us: float = 0.0,
    ) -> Optional[DetectionAlert]:
        """
        Push one 1-second observation (40 CIC features).
        Returns an alert once the window is full.

        Set features_already_scaled=True when replaying from pre-scaled NPZ windows.
        """
        raw = np.asarray(raw_features, dtype=np.float32).reshape(-1)
        if raw.shape[0] != self.n_features:
            raise ValueError(f'Expected {self.n_features} features, got {raw.shape[0]}')

        scaled = raw if features_already_scaled else self.contract.scale_features(raw)
        buf = self._buffers.setdefault(source_ip, deque(maxlen=self.timesteps))
        buf.append(scaled)
        self._pps[source_ip] = packets_this_second

        if len(buf) < self.timesteps and not self.pad_incomplete:
            return None

        self._load_model()
        rows = list(buf)
        if len(rows) < self.timesteps:
            pad = [np.zeros(self.n_features, dtype=np.float32)] * (self.timesteps - len(rows))
            rows = pad + rows
        window = np.stack(rows, axis=0).reshape(1, self.timesteps, self.n_features)
        probs = self._model.predict(window, verbose=0)[0]
        benign_p = float(probs[self.contract.benign_index])
        attack_score = 1.0 - benign_p
        pred_idx = int(np.argmax(probs))

        return DetectionAlert(
            source_ip=source_ip,
            attack_class=self.contract.class_names[pred_idx],
            attack_index=pred_idx,
            attack_score=attack_score,
            benign_prob=benign_p,
            pps=self._pps.get(source_ip, 0.0),
            window_filled=len(buf),
            incomplete_ratio=float(incomplete_ratio),
            concurrent=int(concurrent),
            mean_iat_us=float(mean_iat_us),
        )

    def reset(self, source_ip: str | None = None):
        if source_ip:
            self._buffers.pop(source_ip, None)
            self._pps.pop(source_ip, None)
        else:
            self._buffers.clear()
            self._pps.clear()
