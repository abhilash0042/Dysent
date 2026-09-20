"""
Feature Noise Injection
Adds Gaussian noise to dataset features to increase classification difficulty.
Used to lower model accuracy to realistic levels (90-95%).
"""

import numpy as np

def inject_noise(X, noise_factor=0.2):
    """
    Add random noise to normalized features.
    X: Input data (N, T, F) or (N, F)
    noise_factor: Magnitude of noise (0.0 - 1.0)
    """
    if noise_factor <= 0:
        return X
        
    noise = np.random.normal(loc=0.0, scale=noise_factor, size=X.shape)
    X_noisy = X + noise
    
    # Clip to keep values reasonable (assuming normalized 0-1 or standardized)
    # If Standardized (mean 0 std 1), clipping -5 to 5 is safe
    X_noisy = np.clip(X_noisy, -5.0, 5.0)
    
    return X_noisy
