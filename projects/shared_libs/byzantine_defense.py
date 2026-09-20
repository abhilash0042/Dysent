"""
Byzantine-Resistant Aggregation and Attack Simulation

Separate module for Byzantine-resistant algorithms and malicious node simulation.
"""

import numpy as np
import logging
from typing import List

logger = logging.getLogger(__name__)


class ByzantineRobustAggregator:
    """Byzantine-resistant aggregation algorithms for FL"""
    
    @staticmethod
    def krum(
        local_weights_list: List[List[np.ndarray]],
        num_byzantine: int = 1
    ) -> List[np.ndarray]:
        """
        Krum aggregation: Select the update closest to majority.
        
        Args:
            local_weights_list: List of model weights from nodes
            num_byzantine: Estimated number of Byzantine nodes
            
        Returns:
            Selected model weights
        """
        logger.info(f"Krum aggregation (f={num_byzantine} Byzantine nodes)...")
        
        n = len(local_weights_list)
        m = n - num_byzantine - 2
        
        if m <= 0:
            logger.warning("Too many Byzantine nodes for Krum, using first update")
            return local_weights_list[0]
        
        # Flatten all updates
        flattened = [
            np.concatenate([w.flatten() for w in weights])
            for weights in local_weights_list
        ]
        
        # Compute pairwise distances
        distances = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i != j:
                    distances[i, j] = np.linalg.norm(flattened[i] - flattened[j])
        
        # For each node, sum distances to m closest neighbors
        scores = np.zeros(n)
        for i in range(n):
            sorted_dist = np.sort(distances[i])
            scores[i] = np.sum(sorted_dist[1:m+1])
        
        # Select node with minimum score
        selected_idx = np.argmin(scores)
        
        logger.info(f"✓ Krum selected node {selected_idx}")
        
        return local_weights_list[selected_idx]
    
    @staticmethod
    def trimmed_mean(
        local_weights_list: List[List[np.ndarray]],
        trim_ratio: float = 0.2
    ) -> List[np.ndarray]:
        """
        TrimmedMean: Average after removing top/bottom outliers.
        """
        logger.info(f"TrimmedMean aggregation (trim={trim_ratio})...")
        
        n = len(local_weights_list)
        num_trim = int(n * trim_ratio)
        
        if num_trim >= n // 2:
            num_trim = max(1, int(n * 0.1))
        
        num_layers = len(local_weights_list[0])
        aggregated = []
        
        for layer_idx in range(num_layers):
            layer_weights = np.array([
                weights[layer_idx] for weights in local_weights_list
            ])
            
            sorted_weights = np.sort(layer_weights, axis=0)
            trimmed = sorted_weights[num_trim:-num_trim] if num_trim > 0 else sorted_weights
            
            layer_mean = np.mean(trimmed, axis=0)
            aggregated.append(layer_mean)
        
        logger.info(f"✓ TrimmedMean computed (kept {n - 2*num_trim}/{n} nodes)")
        
        return aggregated
    
    @staticmethod
    def median(local_weights_list: List[List[np.ndarray]]) -> List[np.ndarray]:
        """Coordinate-wise median aggregation"""
        logger.info("Median aggregation...")
        
        num_layers = len(local_weights_list[0])
        aggregated = []
        
        for layer_idx in range(num_layers):
            layer_weights = np.array([
                weights[layer_idx] for weights in local_weights_list
            ])
            
            layer_median = np.median(layer_weights, axis=0)
            aggregated.append(layer_median)
        
        logger.info("✓ Median aggregation computed")
        
        return aggregated


class MaliciousNodeSimulator:
    """Simulates various attack scenarios"""
    
    @staticmethod
    def label_flip_attack(y: np.ndarray, flip_ratio: float = 0.3) -> np.ndarray:
        """Flip a fraction of labels"""
        y_poisoned = y.copy()
        num_flip = int(len(y) * flip_ratio)
        flip_indices = np.random.choice(len(y), num_flip, replace=False)
        
        num_classes = len(np.unique(y))
        for idx in flip_indices:
            original_class = y[idx]
            new_class = (original_class + np.random.randint(1, num_classes)) % num_classes
            y_poisoned[idx] = new_class
        
        logger.warning(f"⚠ Label flip attack: {num_flip} labels flipped")
        
        return y_poisoned
    
    @staticmethod
    def gaussian_noise_attack(
        weights: List[np.ndarray],
        noise_scale: float = 0.1
    ) -> List[np.ndarray]:
        """Add Gaussian noise to model weights"""
        poisoned = []
        for w in weights:
            noise = np.random.normal(0, noise_scale, w.shape)
            poisoned.append(w + noise)
        
        logger.warning(f"⚠ Gaussian noise attack: scale={noise_scale}")
        
        return poisoned
    
    @staticmethod
    def model_poisoning_attack(
        weights: List[np.ndarray],
        scale_factor: float = 10.0
    ) -> List[np.ndarray]:
        """Scale model updates to poison aggregation"""
        poisoned = [w * scale_factor for w in weights]
        
        logger.warning(f"⚠ Model poisoning attack: scale={scale_factor}")
        
        return poisoned
    
    @staticmethod
    def byzantine_attack(weights: List[np.ndarray]) -> List[np.ndarray]:
        """Random Byzantine attack"""
        poisoned = [np.random.randn(*w.shape) for w in weights]
        
        logger.warning("⚠ Byzantine attack: random weights")
        
        return poisoned
