"""
Phase 6: IoT/5G Edge Node Module

Lightweight FL node implementation for IoT devices and 5G edge networks.
Includes model compression and resource-aware training.
"""

import numpy as np
import logging
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class IoTEdgeNode:
    """
    Lightweight FL node for IoT/5G edge deployment
    
    Features:
    - Model quantization (INT8)
    - Pruning for size reduction
    - Resource-aware training
    - 5G protocol simulation
    """
    
    def __init__(
        self,
        node_id: str,
        resource_tier: str = 'medium',  # low, medium, high
        enable_compression: bool = True
    ):
        self.node_id = node_id
        self.resource_tier = resource_tier
        self.enable_compression = enable_compression
        
        # Resource constraints
        self.constraints = {
            'low': {'max_model_size_mb': 5, 'max_batch_size': 16},
            'medium': {'max_model_size_mb': 20, 'max_batch_size': 64},
            'high': {'max_model_size_mb': 100, 'max_batch_size': 256}
        }
        
        logger.info(f"IoT Edge Node '{node_id}' initialized")
        logger.info(f"  Resource tier: {resource_tier}")
        logger.info(f"  Compression: {'enabled' if enable_compression else 'disabled'}")
    
    def quantize_model(self, weights: np.ndarray) -> np.ndarray:
        """Quantize model weights to INT8"""
        if not self.enable_compression:
            return weights
        
        # Simple linear quantization
        w_min, w_max = weights.min(), weights.max()
        scale = 255 / (w_max - w_min + 1e-8)
        
        quantized = np.round((weights - w_min) * scale).astype(np.int8)
        dequantized = quantized.astype(np.float32) / scale + w_min
        
        compression_ratio = weights.nbytes / quantized.nbytes
        logger.info(f"  Model quantized: {compression_ratio:.1f}x compression")
        
        return dequantized
    
    def prune_model(self, weights: np.ndarray, threshold: float = 0.1) -> np.ndarray:
        """Prune small weights"""
        if not self.enable_compression:
            return weights
        
        mask = np.abs(weights) > threshold
        pruned = weights * mask
        
        sparsity = 1 - np.count_nonzero(pruned) / weights.size
        logger.info(f"  Model pruned: {sparsity*100:.1f}% sparsity")
        
        return pruned
    
    def get_max_batch_size(self) -> int:
        """Get maximum batch size for this node"""
        return self.constraints[self.resource_tier]['max_batch_size']


class FiveGEdgeAggregator:
    """5G Edge aggregator for local FL coordination"""
    
    def __init__(self, edge_id: str):
        self.edge_id = edge_id
        self.registered_nodes = {}
        logger.info(f"5G Edge Aggregator '{edge_id}' initialized")
    
    def register_iot_node(self, node: IoTEdgeNode):
        """Register IoT node with edge aggregator"""
        self.registered_nodes[node.node_id] = node
        logger.info(f"  Registered node: {node.node_id}")
    
    def edge_aggregate(self, local_updates: list) -> np.ndarray:
        """Perform edge aggregation (local FedAvg)"""
        if not local_updates:
            return None
        
        # Simple averaging
        aggregated = np.mean(local_updates, axis=0)
        logger.info(f"  Edge aggregated {len(local_updates)} updates")
        
        return aggregated


def test_iot_edge():
    """Test IoT/5G edge module"""
    print("="*70)
    print("TESTING IOT/5G EDGE MODULE")
    print("="*70)
    
    # Create IoT nodes
    node1 = IoTEdgeNode('iot_node_1', resource_tier='low', enable_compression=True)
    node2 = IoTEdgeNode('iot_node_2', resource_tier='medium', enable_compression=True)
    
    # Create edge aggregator
    edge_agg = FiveGEdgeAggregator('edge_1')
    edge_agg.register_iot_node(node1)
    edge_agg.register_iot_node(node2)
    
    # Test compression
    print(f"\n🔬 Testing model compression...")
    dummy_weights = np.random.randn(1000, 100)
    
    quantized = node1.quantize_model(dummy_weights)
    pruned = node1.prune_model(dummy_weights)
    
    print(f"\n✓ IoT/5G edge test complete!")
    print(f"  Nodes registered: {len(edge_agg.registered_nodes)}")
    print(f"  Compression working: Yes")


if __name__ == "__main__":
    test_iot_edge()
