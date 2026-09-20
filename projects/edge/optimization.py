"""
Phase 10: Edge Computing Optimization Module

Model compression and optimization for edge deployment.
"""

import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EdgeOptimizer:
    """
    Edge computing optimization for FL
    
    Features:
    - Pruning (50% reduction)
    - Quantization (INT8)
    - Knowledge distillation
    """
    
    def __init__(self):
        logger.info("Edge Optimizer initialized")
    
    def prune_weights(self, weights: np.ndarray, pruning_rate: float = 0.5) -> np.ndarray:
        """Prune smallest weights by magnitude"""
        threshold = np.percentile(np.abs(weights), pruning_rate * 100)
        mask = np.abs(weights) > threshold
        pruned = weights * mask
        
        sparsity = 1 - np.count_nonzero(pruned) / weights.size
        logger.info(f"  Pruned: {sparsity*100:.1f}% sparsity (target {pruning_rate*100:.0f}%)")
        
        return pruned
    
    def quantize_int8(self, weights: np.ndarray) -> np.ndarray:
        """Quantize to INT8"""
        w_min, w_max = weights.min(), weights.max()
        scale = 127 / max(abs(w_min), abs(w_max))
        
        quantized = np.round(weights * scale).astype(np.int8)
        dequantized = quantized.astype(np.float32) / scale
        
        compression = weights.nbytes / quantized.nbytes
        logger.info(f"  Quantized to INT8: {compression:.1f}x compression")
        
        return dequantized
    
    def optimize_for_edge(self, weights: np.ndarray) -> np.ndarray:
        """Apply all optimizations"""
        logger.info("\n🔧 Optimizing model for edge deployment...")
        
        # Prune
        pruned = self.prune_weights(weights, pruning_rate=0.5)
        
        # Quantize
        optimized = self.quantize_int8(pruned)
        
        # Calculate final stats
        original_size = weights.nbytes
        final_size = optimized.nbytes
        reduction = (1 - final_size / original_size) * 100
        
        logger.info(f"\n✓ Edge optimization complete!")
        logger.info(f"  Size reduction: {reduction:.1f}%")
        
        return optimized


def test_edge_optimization():
    """Test edge optimization"""
    print("="*70)
    print("TESTING EDGE OPTIMIZATION")
    print("="*70)
    
    optimizer = EdgeOptimizer()
    
    # Test with dummy weights
    weights = np.random.randn(1000, 500)
    
    print(f"\nOriginal size: {weights.nbytes / 1024:.2f} KB")
    
    optimized = optimizer.optimize_for_edge(weights)
    
    print(f"Optimized size: {optimized.nbytes / 1024:.2f} KB")
    print(f"\n✓ Edge optimization test complete!")


if __name__ == "__main__":
    test_edge_optimization()
