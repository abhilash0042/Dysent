"""
Federated Learning Node Client

Handles local training on private data and communication with FL server.
"""

import numpy as np
import logging
from typing import Dict, Tuple, Optional
from pathlib import Path
import pickle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FLNode:
    """
    FL node client that trains model locally on private data.
    
    Responsibilities:
    - Train model on local data subset
    - Extract and upload model weights
    - Download global model from server
    - Track local performance metrics
    """
    
    def __init__(
        self,
        node_id: str,
        local_data: Tuple[np.ndarray, np.ndarray],
        model_builder_fn,
        epochs_per_round: int = 5,
        batch_size: int = 64
    ):
        """
        Initialize FL node.
        
        Args:
            node_id: Unique identifier for this node
            local_data: Tuple of (X_local, y_local)
            model_builder_fn: Function that returns a fresh model instance
            epochs_per_round: Number of epochs to train per FL round
            batch_size: Training batch size
        """
        self.node_id = node_id
        self.X_local, self.y_local = local_data
        self.model_builder = model_builder_fn
        self.epochs_per_round = epochs_per_round
        self.batch_size = batch_size
        
        # Create local model
        self.local_model = None
        
        # Track metrics
        self.training_history = []
        
        logger.info(f"FL Node {node_id} initialized")
        logger.info(f"  Local data: {len(self.X_local):,} samples")
        logger.info(f"  Epochs per round: {epochs_per_round}")
    
    def initialize_model(self):
        """Create a fresh model instance"""
        self.local_model = self.model_builder()
        logger.info(f"Node {self.node_id}: Model initialized")
    
    def set_model_weights(self, weights):
        """
        Load global model weights from server.
        
        Args:
            weights: List of numpy arrays (model weights)
        """
        if self.local_model is None:
            self.initialize_model()
        
        self.local_model.set_weights(weights)
        logger.info(f"Node {self.node_id}: Loaded global model weights")
    
    def train_local_model(self, verbose: int = 0) -> Dict:
        """
        Train model on local data.
        
        Args:
            verbose: Keras verbosity level (0=silent, 1=progress, 2=one line per epoch)
            
        Returns:
            Training metrics
        """
        logger.info(f"\nNode {self.node_id}: Starting local training...")
        logger.info(f"  Epochs: {self.epochs_per_round}")
        logger.info(f"  Batch size: {self.batch_size}")
        logger.info(f"  Training samples: {len(self.X_local):,}")
        
        # Train
        history = self.local_model.fit(
            self.X_local,
            self.y_local,
            epochs=self.epochs_per_round,
            batch_size=self.batch_size,
            verbose=verbose,
            validation_split=0.1  # Use 10% for local validation
        )
        
        # Extract final epoch metrics
        final_metrics = {
            'loss': float(history.history['loss'][-1]),
            'accuracy': float(history.history.get('accuracy', [0])[-1]),
            'val_loss': float(history.history.get('val_loss', [0])[-1]),
            'val_accuracy': float(history.history.get('val_accuracy', [0])[-1])
        }
        
        self.training_history.append(final_metrics)
        
        logger.info(f"Node {self.node_id}: Training complete")
        logger.info(f"  Final loss: {final_metrics['loss']:.4f}")
        logger.info(f"  Final accuracy: {final_metrics['accuracy']:.4f}")
        
        return final_metrics
    
    def get_model_weights(self):
        """
        Extract local model weights for upload to server.
        
        Returns:
            List of numpy arrays (model weights)
        """
        return self.local_model.get_weights()
    
    def create_update_package(self) -> Dict:
        """
        Create update package to send to server.
        
        Returns:
            Dictionary with weights and metrics
        """
        return {
            'weights': self.get_model_weights(),
            'metrics': self.training_history[-1] if self.training_history else {},
            'data_size': len(self.X_local)
        }
    
    def participate_in_round(
        self,
        global_weights,
        verbose: int = 0
    ) -> Dict:
        """
        Complete one FL round: download, train, upload.
        
        Args:
            global_weights: Global model weights from server
            verbose: Training verbosity
            
        Returns:
            Update package for server
        """
        # 1. Download global model
        self.set_model_weights(global_weights)
        
        # 2. Train locally
        self.train_local_model(verbose=verbose)
        
        # 3. Prepare update
        update = self.create_update_package()
        
        return update
    
    def evaluate_on_test(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray
    ) -> Dict:
        """
        Evaluate model on test set.
        
        Args:
            X_test: Test features
            y_test: Test labels
            
        Returns:
            Test metrics
        """
        results = self.local_model.evaluate(X_test, y_test, verbose=0)
        
        # Keras returns list: [loss, accuracy, ...]
        metrics = {
            'test_loss': float(results[0]),
            'test_accuracy': float(results[1]) if len(results) > 1 else 0.0
        }
        
        logger.info(f"\nNode {self.node_id} Test Evaluation:")
        logger.info(f"  Test loss: {metrics['test_loss']:.4f}")
        logger.info(f"  Test accuracy: {metrics['test_accuracy']:.4f}")
        
        return metrics
    
    def get_training_history(self):
        """Get all training metrics across rounds"""
        return self.training_history
    
    def save_local_model(self, save_path: str):
        """Save local model to disk"""
        self.local_model.save(save_path)
        logger.info(f"Node {self.node_id}: Model saved to {save_path}")
