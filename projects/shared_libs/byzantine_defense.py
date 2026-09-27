"""
Byzantine-Resistant Aggregation and Attack Simulation

Separate module for Byzantine-resistant algorithms and malicious node simulation.
"""

import numpy as np
import logging
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)

Weights = List[np.ndarray]

# Methods that clip every client update before mixing.
# Plain FedAvg stays unclipped so it remains the undefended baseline.
CLIPPED_METHODS = frozenset({
    'fedavg_clip',
    'krum',
    'multi_krum',
    'median',
    'trimmed_mean',
    'bulyan',
    'trust_weighted',
})


class AggregationUnsupported(ValueError):
    """Raised when an aggregator cannot be applied for this n and f.

    Krum used to return client 0 in this case. That client is often the
    attacker, so the experiment now records the run as unsupported.
    """


def update_l2(weights: Sequence[np.ndarray]) -> float:
    flat = np.concatenate([np.asarray(w, dtype=np.float64).ravel() for w in weights])
    return float(np.linalg.norm(flat))


def clip_update(weights: Sequence[np.ndarray], clip_norm: float) -> Weights:
    """Scale an update so its L2 norm is at most clip_norm."""
    arrays = [np.array(w, copy=True) for w in weights]
    if clip_norm is None or clip_norm <= 0:
        return arrays
    norm = update_l2(arrays)
    if norm > clip_norm and norm > 0:
        scale = clip_norm / norm
        return [w * scale for w in arrays]
    return arrays


def _flatten(weights: Sequence[np.ndarray]) -> np.ndarray:
    return np.concatenate([np.asarray(w, dtype=np.float64).ravel() for w in weights])


def _pairwise_scores(local_weights_list: Sequence[Sequence[np.ndarray]], neighbor_count: int) -> np.ndarray:
    """Krum score: sum of distances to the closest neighbor_count other updates."""
    n = len(local_weights_list)
    flattened = [_flatten(weights) for weights in local_weights_list]
    distances = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            dist = np.linalg.norm(flattened[i] - flattened[j])
            distances[i, j] = distances[j, i] = dist
    scores = np.zeros(n)
    for i in range(n):
        sorted_dist = np.sort(distances[i])
        scores[i] = np.sum(sorted_dist[1:neighbor_count + 1])
    return scores


class ByzantineRobustAggregator:
    """Byzantine-resistant aggregation algorithms for FL"""
    
    @staticmethod
    def fedavg(local_weights_list: List[List[np.ndarray]]) -> List[np.ndarray]:
        """Standard Federated Averaging."""
        if not local_weights_list:
            raise ValueError("No local model updates supplied")

        num_layers = len(local_weights_list[0])
        aggregated = []

        for layer_idx in range(num_layers):
            layer_weights = np.asarray([
                weights[layer_idx]
                for weights in local_weights_list
            ])

            aggregated.append(np.mean(layer_weights, axis=0))

        logger.info("✓ FedAvg aggregation computed")
        return aggregated

    @staticmethod
    def krum(
        local_weights_list: List[List[np.ndarray]],
        num_byzantine: int = 1
    ) -> List[np.ndarray]:
        """Select the update closest to the majority.

        Requires n >= f + 3 so there is at least one neighbor in the score.
        """
        logger.info(f"Krum aggregation (f={num_byzantine} Byzantine nodes)...")
        selected = ByzantineRobustAggregator.krum_index(local_weights_list, num_byzantine)
        logger.info(f"✓ Krum selected node {selected}")
        return [np.array(w, copy=True) for w in local_weights_list[selected]]

    @staticmethod
    def krum_index(local_weights_list: List[List[np.ndarray]], num_byzantine: int = 1) -> int:
        n = len(local_weights_list)
        m = n - int(num_byzantine) - 2
        if m <= 0:
            raise AggregationUnsupported(
                f"Krum needs n >= f+3 (n={n}, f={num_byzantine})"
            )
        scores = _pairwise_scores(local_weights_list, m)
        return int(np.argmin(scores))

    @staticmethod
    def multi_krum(
        local_weights_list: List[List[np.ndarray]],
        num_byzantine: int = 1,
    ) -> List[np.ndarray]:
        """Average the n-f updates with the best Krum scores."""
        n = len(local_weights_list)
        f = int(num_byzantine)
        m = n - f - 2
        if m <= 0:
            raise AggregationUnsupported(
                f"Multi-Krum needs n >= f+3 (n={n}, f={f})"
            )
        keep = max(1, n - f)
        scores = _pairwise_scores(local_weights_list, m)
        chosen = np.argsort(scores)[:keep]
        logger.info(f"✓ Multi-Krum averaged {len(chosen)}/{n} updates")
        return ByzantineRobustAggregator.fedavg(
            [local_weights_list[i] for i in chosen]
        )

    @staticmethod
    def bulyan(
        local_weights_list: List[List[np.ndarray]],
        num_byzantine: int = 1,
    ) -> List[np.ndarray]:
        """Multi-Krum selection followed by a coordinate-wise trimmed mean.

        Requires n >= 4f + 3.
        """
        n = len(local_weights_list)
        f = int(num_byzantine)
        if n < 4 * f + 3:
            raise AggregationUnsupported(
                f"Bulyan needs n >= 4f+3 (n={n}, f={f})"
            )
        theta = n - 2 * f
        m = n - f - 2
        scores = _pairwise_scores(local_weights_list, m)
        chosen = [local_weights_list[i] for i in np.argsort(scores)[:theta]]
        aggregated = []
        for layer_idx in range(len(chosen[0])):
            stacked = np.stack([np.asarray(weights[layer_idx]) for weights in chosen], axis=0)
            ordered = np.sort(stacked, axis=0)
            kept = ordered[f:theta - f] if f > 0 else ordered
            aggregated.append(np.mean(kept, axis=0))
        logger.info(f"✓ Bulyan computed (selected {theta}, trimmed f={f})")
        return aggregated

    @staticmethod
    def trust_weighted(local_weights_list: List[List[np.ndarray]]) -> List[np.ndarray]:
        """Weighted average. Clients far from the coordinate median get less weight."""
        center = ByzantineRobustAggregator.median(local_weights_list)
        center_flat = _flatten(center)
        distances = np.array([
            np.linalg.norm(_flatten(weights) - center_flat)
            for weights in local_weights_list
        ], dtype=np.float64)
        weights = 1.0 / (distances + 1e-8)
        weights = weights / weights.sum()
        aggregated = []
        for layer_idx in range(len(center)):
            stacked = np.stack([
                np.asarray(update[layer_idx], dtype=np.float64)
                for update in local_weights_list
            ], axis=0)
            shape = stacked.shape[1:]
            mixed = np.tensordot(weights, stacked.reshape(len(weights), -1), axes=(0, 0))
            aggregated.append(mixed.reshape(shape))
        logger.info("✓ Trust-weighted aggregation computed")
        return aggregated
    
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
    def sign_flip_attack(
        weights: List[np.ndarray],
        scale_factor: float = 1.0
    ) -> List[np.ndarray]:
        """Negate submitted weights/update tensors."""
        poisoned = [-scale_factor * np.asarray(w) for w in weights]
        logger.warning(f"⚠ Sign-flip attack: scale={scale_factor}")
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


def aggregate_updates(
    local_weights_list: Sequence[Sequence[np.ndarray]],
    method: str,
    num_byzantine: int = 0,
    trim_ratio: float = 0.2,
    clip_norm: Optional[float] = 1.0,
) -> Weights:
    """Dispatch one aggregation step.

    fedavg is the unclipped baseline. Every other method clips first.
    """
    if not local_weights_list:
        raise ValueError("No local model updates supplied")
    method = method.lower().replace('-', '_')
    updates: List[Weights] = [
        [np.array(w, copy=True) for w in weights] for weights in local_weights_list
    ]
    if method in CLIPPED_METHODS:
        if clip_norm is None or clip_norm <= 0:
            raise ValueError(f"{method} requires a positive clip_norm")
        updates = [clip_update(weights, clip_norm) for weights in updates]

    if method in ('fedavg', 'fedavg_clip'):
        return ByzantineRobustAggregator.fedavg(updates)
    if method == 'krum':
        return ByzantineRobustAggregator.krum(updates, num_byzantine)
    if method in ('multi_krum', 'multikrum'):
        return ByzantineRobustAggregator.multi_krum(updates, num_byzantine)
    if method == 'median':
        return ByzantineRobustAggregator.median(updates)
    if method in ('trimmed_mean', 'trimmedmean'):
        return ByzantineRobustAggregator.trimmed_mean(updates, trim_ratio)
    if method == 'bulyan':
        return ByzantineRobustAggregator.bulyan(updates, num_byzantine)
    if method in ('trust_weighted', 'trust'):
        return ByzantineRobustAggregator.trust_weighted(updates)
    raise ValueError(f"Unknown aggregation method: {method}")
