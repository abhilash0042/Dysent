"""Reshape flat CIC-DDoS2019 feature rows for the CNN-BiLSTM FL path."""

from __future__ import annotations

import numpy as np


def reshape_for_cnn_bilstm(X, timesteps):
    """Reshape ``(N, F)`` rows into ``(N, timesteps, F // timesteps)``.

    Feature order is preserved and values are not changed. ``F`` must be
    divisible by ``timesteps``. The FL path uses 40 selected features and
    ``timesteps=10``, which yields ``(N, 10, 4)``.
    """
    if isinstance(timesteps, bool) or not isinstance(timesteps, (int, np.integer)):
        raise ValueError(f"timesteps must be a positive integer, got {timesteps!r}")
    timesteps = int(timesteps)
    if timesteps <= 0:
        raise ValueError(f"timesteps must be a positive integer, got {timesteps}")

    array = np.asarray(X)
    if array.ndim != 2:
        raise ValueError(f"X must be a 2D array of shape (N, F), got {array.shape}")

    n_samples, n_features = array.shape
    if n_features % timesteps != 0:
        raise ValueError(
            f"Feature count {n_features} is not divisible by timesteps={timesteps}. "
            "Select a feature count that divides evenly. This loader does not trim or pad."
        )

    features_per_step = n_features // timesteps
    return np.reshape(array, (n_samples, timesteps, features_per_step))
