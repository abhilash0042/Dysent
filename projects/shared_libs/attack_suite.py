"""Reusable Byzantine attack suite for FL experiments.

All attacks operate on a client's local labels/weights before aggregation.
This keeps malicious clients first-class participants in the experiment.
"""
from __future__ import annotations
import numpy as np
from typing import List

Weights = List[np.ndarray]


def clone_weights(weights: Weights) -> Weights:
    return [np.array(w, copy=True) for w in weights]


def label_flip(y: np.ndarray, seed: int | None = None, ratio: float = 1.0) -> np.ndarray:
    """Binary/multiclass label flipping on a fraction of a client's labels."""
    rng = np.random.default_rng(seed)
    y2 = np.array(y, copy=True)
    classes = np.unique(y2)
    if len(classes) < 2:
        return y2
    n = int(len(y2) * ratio)
    idx = rng.choice(len(y2), size=min(n, len(y2)), replace=False)
    for i in idx:
        choices = classes[classes != y2[i]]
        y2[i] = rng.choice(choices)
    return y2


def sign_flip(weights: Weights, scale: float = 1.0) -> Weights:
    """Negate the submitted model/update tensors and optionally scale them."""
    return [-scale * np.asarray(w) for w in weights]


def scale(weights: Weights, factor: float = 10.0) -> Weights:
    return [factor * np.asarray(w) for w in weights]


def gaussian(weights: Weights, std: float = 0.1, seed: int | None = None) -> Weights:
    rng = np.random.default_rng(seed)
    return [np.asarray(w) + rng.normal(0.0, std, size=np.asarray(w).shape) for w in weights]


def random_weights(weights: Weights, seed: int | None = None) -> Weights:
    rng = np.random.default_rng(seed)
    return [rng.normal(size=np.asarray(w).shape).astype(np.asarray(w).dtype) for w in weights]


def backdoor_labels(y: np.ndarray, target: int = 0, ratio: float = 0.1, seed: int | None = None) -> np.ndarray:
    """Simple label-targeting primitive; feature trigger injection is handled by the caller."""
    rng = np.random.default_rng(seed)
    y2 = np.array(y, copy=True)
    n = min(int(len(y2) * ratio), len(y2))
    if n:
        idx = rng.choice(len(y2), n, replace=False)
        y2[idx] = target
    return y2


def apply_weight_attack(weights: Weights, attack: str, seed: int | None = None, **kwargs) -> Weights:
    attack = attack.lower().replace('-', '_')
    if attack in ('honest', 'none'):
        return clone_weights(weights)
    if attack == 'sign_flip':
        return sign_flip(weights, kwargs.get('scale', 1.0))
    if attack in ('scale', 'model_poisoning'):
        return scale(weights, kwargs.get('factor', 10.0))
    if attack in ('gaussian', 'gaussian_noise'):
        return gaussian(weights, kwargs.get('std', 0.1), seed)
    if attack in ('random', 'byzantine'):
        return random_weights(weights, seed)
    raise ValueError(f'Unsupported weight attack: {attack}')
