"""
Federated Learning Aggregation Server

Implements FedAvg (Federated Averaging) algorithm for distributed model training.
Coordinates multiple FL nodes and aggregates their model updates.
"""

import numpy as np
import logging
from typing import List, Dict, Optional, Tuple
from pathlib import Path
import pickle
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FederatedServer:
    """
    Central aggregation server for Federated Learning.
    
    Responsibilities:
    - Register participating nodes
    - Distribute global model to nodes
    - Collect local model updates
    - Perform FedAvg aggregation
    - Manage FL training rounds
    """
    
    def __init__(
        self,
        global_model,
        num_rounds: int = 20,
        min_nodes: int = 2,
        selection_fraction: float = 1.0,
        save_dir: str = "./fl_checkpoints"
    ):
        """
        Initialize FL server.
        
        Args:
            global_model: Initial global model (Keras model)
            num_rounds: Number of FL training rounds
            min_nodes: Minimum nodes required to start
            selection_fraction: Fraction of nodes to select per round (1.0 = all)
            save_dir: Directory to save models and logs
        """
        self.global_model = global_model
        self.num_rounds = num_rounds
        self.min_nodes = min_nodes
        self.selection_fraction = selection_fraction
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)
        
        # Track registered nodes
        self.registered_nodes = {}  # {node_id: {'data_size': int, 'status': str}}
        self.current_round = 0
        
        # Store metrics
        self.round_metrics = []
        
        logger.info("="*70)
        logger.info("Federated Learning Server Initialized")
        logger.info("="*70)
        logger.info(f"Total rounds: {num_rounds}")
        logger.info(f"Minimum nodes: {min_nodes}")
        logger.info(f"Selection fraction: {selection_fraction}")
        
    def register_node(self, node_id: str, data_size: int) -> bool:
        """
        Register a new FL node.
        
        Args:
            node_id: Unique identifier for the node
            data_size: Number of training samples at this node
            
        Returns:
            True if registration successful
        """
        if node_id in self.registered_nodes:
            logger.warning(f"Node {node_id} already registered")
            return False
        
        self.registered_nodes[node_id] = {
            'data_size': data_size,
            'status': 'active',
            'registered_at': datetime.now()
        }
        
        logger.info(f"✓ Registered node {node_id} with {data_size:,} samples")
        logger.info(f"Total nodes: {len(self.registered_nodes)}")
        
        return True
    
    def get_global_model_weights(self) -> List[np.ndarray]:
        """Get current global model weights"""
        return self.global_model.get_weights()
    
    def set_global_model_weights(self, weights: List[np.ndarray]):
        """Update global model weights"""
        self.global_model.set_weights(weights)
    
    def federated_averaging(
        self,
        local_weights_list: List[List[np.ndarray]],
        data_sizes: List[int]
    ) -> List[np.ndarray]:
        """
        Perform FedAvg: weighted average of local model weights.
        
        Formula: w_global = Σ(n_k / N) * w_k
        where n_k is local data size, N is total data size
        
        Args:
            local_weights_list: List of local model weights from nodes
            data_sizes: List of data sizes corresponding to each node
            
        Returns:
            Aggregated global model weights
        """
        total_data = sum(data_sizes)
        
        # Get number of weight arrays
        num_layers = len(local_weights_list[0])
        
        # Initialize aggregated weights (same structure as model)
        aggregated_weights = []
        
        for layer_idx in range(num_layers):
            # Weighted sum for this layer
            layer_sum = np.zeros_like(local_weights_list[0][layer_idx])
            
            for node_weights, data_size in zip(local_weights_list, data_sizes):
                weight = data_size / total_data
                layer_sum += weight * node_weights[layer_idx]
            
            aggregated_weights.append(layer_sum)
        
        return aggregated_weights
    
    def run_round(
        self,
        local_updates: Dict[str, Dict]
    ) -> Dict:
        """
        Execute one FL training round.
        
        Args:
            local_updates: Dictionary mapping node_id to update data
                          {node_id: {'weights': [...], 'metrics': {...}}}
        
        Returns:
            Round summary with metrics
        """
        self.current_round += 1
        
        logger.info("\n" + "="*70)
        logger.info(f"FL ROUND {self.current_round}/{self.num_rounds}")
        logger.info("="*70)
        
        # Extract weights and data sizes
        local_weights_list = []
        data_sizes = []
        node_metrics = {}
        
        for node_id, update in local_updates.items():
            local_weights_list.append(update['weights'])
            data_sizes.append(self.registered_nodes[node_id]['data_size'])
            node_metrics[node_id] = update.get('metrics', {})
        
        logger.info(f"Received updates from {len(local_updates)} nodes")
        
        # Perform FedAvg
        logger.info("Aggregating model weights (FedAvg)...")
        aggregated_weights = self.federated_averaging(local_weights_list, data_sizes)
        
        # Update global model
        self.global_model.set_weights(aggregated_weights)
        
        logger.info("✓ Global model updated")
        
        # Compute average metrics
        avg_metrics = self._compute_average_metrics(node_metrics, data_sizes)
        
        # Store round summary
        round_summary = {
            'round': self.current_round,
            'num_nodes': len(local_updates),
            'avg_metrics': avg_metrics,
            'timestamp': datetime.now()
        }
        
        self.round_metrics.append(round_summary)
        
        # Log metrics
        logger.info(f"\nRound {self.current_round} Summary:")
        logger.info(f"  Participating nodes: {len(local_updates)}")
        if 'accuracy' in avg_metrics:
            logger.info(f"  Average accuracy: {avg_metrics['accuracy']:.4f}")
        if 'loss' in avg_metrics:
            logger.info(f"  Average loss: {avg_metrics['loss']:.4f}")
        
        # Save checkpoint
        if self.current_round % 5 == 0:
            self.save_checkpoint()
        
        return round_summary
    
    def _compute_average_metrics(
        self,
        node_metrics: Dict[str, Dict],
        data_sizes: List[int]
    ) -> Dict:
        """Compute weighted average of node metrics"""
        total_data = sum(data_sizes)
        avg_metrics = {}
        
        if not node_metrics:
            return avg_metrics
        
        # Get metric keys from first node
        first_node_metrics = next(iter(node_metrics.values()))
        
        for metric_name in first_node_metrics.keys():
            weighted_sum = 0
            for (node_id, metrics), data_size in zip(node_metrics.items(), data_sizes):
                weight = data_size / total_data
                weighted_sum += weight * metrics.get(metric_name, 0)
            
            avg_metrics[metric_name] = weighted_sum
        
        return avg_metrics
    
    def save_checkpoint(self):
        """Save global model and round metrics"""
        # Save model
        model_path = self.save_dir / f"global_model_round_{self.current_round}.keras"
        self.global_model.save(model_path)
        
        # Save metrics
        metrics_path = self.save_dir / "round_metrics.pkl"
        with open(metrics_path, 'wb') as f:
            pickle.dump(self.round_metrics, f)
        
        logger.info(f"✓ Checkpoint saved: {model_path}")
    
    def get_round_metrics(self) -> List[Dict]:
        """Get all round metrics"""
        return self.round_metrics
    
    def is_training_complete(self) -> bool:
        """Check if FL training is complete"""
        return self.current_round >= self.num_rounds
    
    def summary(self):
        """Print FL training summary"""
        logger.info("\n" + "="*70)
        logger.info("FEDERATED LEARNING SUMMARY")
        logger.info("="*70)
        logger.info(f"Total rounds completed: {self.current_round}")
        logger.info(f"Total nodes participated: {len(self.registered_nodes)}")
        
        if self.round_metrics:
            final_metrics = self.round_metrics[-1]['avg_metrics']
            logger.info(f"\nFinal Global Model Performance:")
            for metric, value in final_metrics.items():
                logger.info(f"  {metric}: {value:.4f}")
        
        logger.info(f"\nModel saved to: {self.save_dir}")
        logger.info("="*70)


class SimpleFLServer:
    """
    Simplified synchronous FL server for simulation.
    No REST API - direct Python function calls.
    """
    
    def __init__(self, global_model, num_rounds=20):
        self.server = FederatedServer(
            global_model=global_model,
            num_rounds=num_rounds
        )
    
    def register_node(self, node_id, data_size):
        return self.server.register_node(node_id, data_size)
    
    def get_global_weights(self):
        return self.server.get_global_model_weights()
    
    def aggregate_and_update(self, local_updates):
        return self.server.run_round(local_updates)
    
    def is_complete(self):
        return self.server.is_training_complete()
    
    def get_metrics(self):
        return self.server.get_round_metrics()
    
    def summary(self):
        self.server.summary()
