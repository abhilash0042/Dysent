"""
Local Trainer for Federated Learning Node

Handles local model training on each FL node with privacy preservation.
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras
from typing import Dict, List, Optional, Tuple, Any
import logging
from pathlib import Path
import pickle
import hashlib
import json

logger = logging.getLogger(__name__)


class LocalTrainer:
    """Local model training for FL nodes"""
    
    def __init__(
        self,
        model: keras.Model,
        node_id: str,
        data_dir: str = "./data/node_data",
        checkpoint_dir: str = "./checkpoints"
    ):
        """
        Initialize local trainer
        
        Args:
            model: Keras model to train
            node_id: Node identifier
            data_dir: Directory for node's local data
            checkpoint_dir: Directory for checkpoints
        """
        self.model = model
        self.node_id = node_id
        self.data_dir = Path(data_dir)
        self.checkpoint_dir = Path(checkpoint_dir) / node_id
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
        self.training_history = []
        self.round_metrics = {}
        
        logger.info(f"Initialized LocalTrainer for node {node_id}")
    
    def train_local_model(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 5,
        batch_size: int = 32,
        round_number: int = 0,
        class_weights: Optional[Dict[int, float]] = None
    ) -> Dict[str, Any]:
        """
        Train model on local data
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            epochs: Number of local epochs
            batch_size: Batch size
            round_number: Current FL round
            class_weights: Class weights for imbalanced data
            
        Returns:
            Training metrics dictionary
        """
        logger.info(
            f"[Node {self.node_id}] Starting local training for round {round_number}, "
            f"{epochs} epochs, {len(X_train)} samples"
        )
        
        # Prepare validation data
        validation_data = None
        if X_val is not None and y_val is not None:
            validation_data = (X_val, y_val)
        
        # Train model
        history = self.model.fit(
            X_train, y_train,
            validation_data=validation_data,
            epochs=epochs,
            batch_size=batch_size,
            class_weight=class_weights,
            verbose=0  # Quiet training
        )
        
        # Extract metrics
        metrics = {
            "round": round_number,
            "node_id": self.node_id,
            "epochs": epochs,
            "num_samples": len(X_train),
            "train_loss": float(history.history['loss'][-1]),
            "train_accuracy": float(history.history.get('accuracy', [0])[-1])
        }
        
        if validation_data:
            metrics.update({
                "val_loss": float(history.history.get('val_loss', [0])[-1]),
                "val_accuracy": float(history.history.get('val_accuracy', [0])[-1])
            })
        
        # Store in history
        self.training_history.append(history.history)
        self.round_metrics[round_number] = metrics
        
        logger.info(
            f"[Node {self.node_id}] Training complete - "
            f"Loss: {metrics['train_loss']:.4f}, "
            f"Accuracy: {metrics['train_accuracy']:.4f}"
        )
        
        return metrics
    
    def get_model_weights(self) -> List[np.ndarray]:
        """
        Get current model weights
        
        Returns:
            List of weight arrays
        """
        return self.model.get_weights()
    
    def set_model_weights(self, weights: List[np.ndarray]):
        """
        Set model weights (from global model)
        
        Args:
            weights: List of weight arrays
        """
        self.model.set_weights(weights)
        logger.info(f"[Node {self.node_id}] Updated model weights from global model")
    
    def compute_weight_delta(
        self,
        initial_weights: List[np.ndarray]
    ) -> List[np.ndarray]:
        """
        Compute weight delta (current - initial)
        
        Args:
            initial_weights: Initial weights before training
            
        Returns:
            List of weight delta arrays
        """
        current_weights = self.get_model_weights()
        deltas = [
            curr - init 
            for curr, init in zip(current_weights, initial_weights)
        ]
        return deltas
    
    def compute_model_hash(self) -> str:
        """
        Compute hash of current model weights
        
        Returns:
            SHA256 hash of model weights
        """
        weights = self.get_model_weights()
        weights_bytes = b''.join([w.tobytes() for w in weights])
        return hashlib.sha256(weights_bytes).hexdigest()
    
    def evaluate_model(
        self,
        X_test: np.ndarray,
        y_test: np.ndarray,
        batch_size: int = 32
    ) -> Dict[str, float]:
        """
        Evaluate model on test data
        
        Args:
            X_test: Test features
            y_test: Test labels
            batch_size: Batch size
            
        Returns:
            Evaluation metrics
        """
        logger.info(f"[Node {self.node_id}] Evaluating model on {len(X_test)} samples")
        
        results = self.model.evaluate(
            X_test, y_test,
            batch_size=batch_size,
            verbose=0,
            return_dict=True
        )
        
        logger.info(
            f"[Node {self.node_id}] Evaluation - "
            f"Loss: {results['loss']:.4f}, "
            f"Accuracy: {results.get('accuracy', 0):.4f}"
        )
        
        return results
    
    def save_checkpoint(self, round_number: int):
        """
        Save model checkpoint
        
        Args:
            round_number: Current FL round
        """
        checkpoint_path = self.checkpoint_dir / f"round_{round_number}.keras"
        self.model.save(checkpoint_path)
        
        # Save metrics
        metrics_path = self.checkpoint_dir / f"metrics_round_{round_number}.json"
        with open(metrics_path, 'w') as f:
            json.dump(self.round_metrics.get(round_number, {}), f, indent=2)
        
        logger.info(f"[Node {self.node_id}] Saved checkpoint for round {round_number}")
    
    def load_checkpoint(self, round_number: int):
        """
        Load model checkpoint
        
        Args:
            round_number: FL round to load
        """
        checkpoint_path = self.checkpoint_dir / f"round_{round_number}.keras"
        if checkpoint_path.exists():
            self.model = keras.models.load_model(checkpoint_path)
            logger.info(f"[Node {self.node_id}] Loaded checkpoint from round {round_number}")
        else:
            logger.warning(f"[Node {self.node_id}] No checkpoint found for round {round_number}")
    
    def get_training_summary(self) -> Dict[str, Any]:
        """
        Get summary of training history
        
        Returns:
            Training summary dictionary
        """
        return {
            "node_id": self.node_id,
            "total_rounds": len(self.round_metrics),
            "rounds": self.round_metrics
        }


class PrivacyMechanism:
    """Differential privacy mechanisms for FL"""
    
    @staticmethod
    def add_gaussian_noise(
        weights: List[np.ndarray],
        noise_scale: float = 0.001,
        clip_norm: float = 1.0
    ) -> List[np.ndarray]:
        """
        Add Gaussian noise to model weights for differential privacy
        
        Args:
            weights: Model weights
            noise_scale: Scale of Gaussian noise
            clip_norm: Gradient clipping norm
            
        Returns:
            Noisy weights
        """
        noisy_weights = []
        
        for w in weights:
            # Clip weights
            norm = np.linalg.norm(w)
            if norm > clip_norm:
                w = w * (clip_norm / norm)
            
            # Add Gaussian noise
            noise = np.random.normal(0, noise_scale, w.shape)
            noisy_w = w + noise
            noisy_weights.append(noisy_w)
        
        logger.debug(f"Added Gaussian noise (scale={noise_scale}) to {len(weights)} weight arrays")
        
        return noisy_weights
    
    @staticmethod
    def compute_privacy_loss(
        epsilon: float,
        delta: float,
        num_rounds: int
    ) -> float:
        """
        Compute cumulative privacy loss over FL rounds
        
        Args:
            epsilon: Privacy parameter
            delta: Privacy parameter
            num_rounds: Number of FL rounds
            
        Returns:
            Cumulative epsilon
        """
        # Simple composition (for demonstration)
        cumulative_epsilon = epsilon * np.sqrt(num_rounds)
        
        logger.info(
            f"Privacy loss after {num_rounds} rounds: "
            f"ε={cumulative_epsilon:.3f}, δ={delta}"
        )
        
        return cumulative_epsilon


class SecureAggregationPrep:
    """Prepare model updates for secure aggregation"""
    
    @staticmethod
    def encrypt_weights(
        weights: List[np.ndarray],
        encryption_key: Optional[bytes] = None
    ) -> bytes:
        """
        Encrypt model weights (simplified version)
        
        Args:
            weights: Model weights
            encryption_key: Encryption key (generates random if None)
            
        Returns:
            Encrypted weights as bytes
        """
        # Serialize weights
        weights_bytes = pickle.dumps(weights)
        
        # In production, use proper encryption like AES
        # This is a simplified XOR encryption for demonstration
        if encryption_key is None:
            encryption_key = np.random.bytes(32)
        
        encrypted = bytearray(weights_bytes)
        key_bytes = encryption_key * (len(encrypted) // len(encryption_key) + 1)
        
        for i in range(len(encrypted)):
            encrypted[i] ^= key_bytes[i]
        
        logger.debug(f"Encrypted {len(weights)} weight arrays")
        
        return bytes(encrypted)
    
    @staticmethod
    def decrypt_weights(
        encrypted_bytes: bytes,
        encryption_key: bytes
    ) -> List[np.ndarray]:
        """
        Decrypt model weights
        
        Args:
            encrypted_bytes: Encrypted weights
            encryption_key: Encryption key
            
        Returns:
            Decrypted weights
        """
        decrypted = bytearray(encrypted_bytes)
        key_bytes = encryption_key * (len(decrypted) // len(encryption_key) + 1)
        
        for i in range(len(decrypted)):
            decrypted[i] ^= key_bytes[i]
        
        weights = pickle.loads(bytes(decrypted))
        
        logger.debug(f"Decrypted {len(weights)} weight arrays")
        
        return weights
    
    @staticmethod
    def compute_weight_statistics(
        weights: List[np.ndarray]
    ) -> Dict[str, float]:
        """
        Compute statistics of model weights
        
        Args:
            weights: Model weights
            
        Returns:
            Statistics dictionary
        """
        all_weights = np.concatenate([w.flatten() for w in weights])
        
        return {
            "mean": float(np.mean(all_weights)),
            "std": float(np.std(all_weights)),
            "min": float(np.min(all_weights)),
            "max": float(np.max(all_weights)),
            "norm": float(np.linalg.norm(all_weights)),
            "num_parameters": int(len(all_weights))
        }
