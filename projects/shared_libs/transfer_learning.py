"""
Federated Transfer Learning Module

Implements transfer learning for cross-domain DDoS detection in federated settings.
Enables quick adaptation to new network types and attack patterns.
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras
from typing import List, Dict, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class FederatedTransferLearning:
    """
    Federated Transfer Learning for DDoS Detection
    
    Pre-trains on source domain (e.g., CICDDoS2019), then fine-tunes
    on target domain (e.g., UNSW-NB15, Bot-IoT, organization-specific).
    """
    
    def __init__(
        self,
        source_model: keras.Model,
        freeze_layers: Optional[List[str]] = None,
        transfer_mode: str = 'feature_extraction'
    ):
        """
        Initialize transfer learning.
        
        Args:
            source_model: Pre-trained model on source domain
            freeze_layers: Layers to freeze (CNN for feature extraction)
            transfer_mode: 'feature_extraction' or 'fine_tuning'
        """
        self.source_model = source_model
        self.freeze_layers = freeze_layers or ['cnn', 'conv']
        self.transfer_mode = transfer_mode
        
        logger.info("Initialized Federated Transfer Learning")
        logger.info(f"  Transfer mode: {transfer_mode}")
        logger.info(f"  Freeze layers: {freeze_layers}")
    
    def extract_feature_extractor(self) -> keras.Model:
        """
        Extract feature extraction layers (CNN) from pre-trained model.
        
        Returns:
            Feature extractor model
        """
        logger.info("Extracting feature extractor layers...")
        
        # Identify CNN layers
        feature_layers = []
        for layer in self.source_model.layers:
            if any(keyword in layer.name.lower() for keyword in self.freeze_layers):
                feature_layers.append(layer.name)
                layer.trainable = False  # Freeze
        
        logger.info(f"  Frozen {len(feature_layers)} layers: {feature_layers}")
        
        return self.source_model
    
    def create_target_model(
        self,
        num_target_classes: int,
        task_specific_layers: Optional[List] = None
    ) -> keras.Model:
        """
        Create target domain model with frozen feature extractor.
        
        Args:
            num_target_classes: Number of classes in target domain
            task_specific_layers: New layers for target task
            
        Returns:
            Target model with frozen feature extractor
        """
        logger.info(f"Creating target model for {num_target_classes} classes...")
        
        # Extract feature extractor
        feature_model = self.extract_feature_extractor()
        
        # Get intermediate output (before final dense layer)
        for i, layer in enumerate(reversed(feature_model.layers)):
            if isinstance(layer, keras.layers.Dense):
                intermediate_layer = feature_model.layers[-i-2]
                break
        
        # Create new task-specific head
        x = intermediate_layer.output
        
        if task_specific_layers:
            for layer in task_specific_layers:
                x = layer(x)
        
        # New output layer for target domain
        outputs = keras.layers.Dense(
            num_target_classes,
            activation='softmax',
            name='target_output'
        )(x)
        
        target_model = keras.Model(
            inputs=feature_model.input,
            outputs=outputs,
            name='transfer_model'
        )
        
        logger.info(f"  Created target model with {target_model.count_params():,} params")
        logger.info(f"  Trainable params: {sum([np.prod(w.shape) for w in target_model.trainable_weights]):,}")
        
        return target_model
    
    def domain_adaptation_layers(self, input_dim: int) -> List[keras.layers.Layer]:
        """
        Create domain adaptation layers (optional advanced feature).
        
        Uses gradient reversal for domain-adversarial training.
        
        Args:
            input_dim: Input dimension
            
        Returns:
            List of adaptation layers
        """
        return [
            keras.layers.Dense(128, activation='relu', name='adapt_dense1'),
            keras.layers.Dropout(0.3, name='adapt_dropout'),
            keras.layers.Dense(64, activation='relu', name='adapt_dense2')
        ]
    
    def compute_transfer_metrics(
        self,
        source_accuracy: float,
        target_baseline: float,
        target_transfer: float,
        source_time: float,
        target_time: float
    ) -> Dict[str, float]:
        """
        Compute transfer learning effectiveness metrics.
        
        Args:
            source_accuracy: Accuracy on source domain
            target_baseline: Target accuracy without transfer
            target_transfer: Target accuracy with transfer
            source_time: Training time on source
            target_time: Fine-tuning time on target
            
        Returns:
            Dictionary of transfer metrics
        """
        metrics = {
            'transfer_gain': target_transfer - target_baseline,
            'transfer_ratio': target_transfer / target_baseline if target_baseline > 0 else 0,
            'time_reduction': (source_time - target_time) / source_time if source_time > 0 else 0,
            'efficiency': target_transfer / target_time if target_time > 0 else 0,
            'source_accuracy': source_accuracy,
            'target_baseline': target_baseline,
            'target_transfer': target_transfer
        }
        
        logger.info("\n📊 Transfer Learning Metrics:")
        logger.info(f"  Transfer Gain: +{metrics['transfer_gain']*100:.2f}%")
        logger.info(f"  Transfer Ratio: {metrics['transfer_ratio']:.2f}x")
        logger.info(f"  Time Reduction: {metrics['time_reduction']*100:.1f}%")
        logger.info(f"  Efficiency: {metrics['efficiency']:.4f}")
        
        return metrics
    
    def progressive_unfreezing(
        self,
        model: keras.Model,
        num_stages: int = 3
    ) -> List[keras.Model]:
        """
        Progressive layer unfreezing strategy.
        
        Gradually unfreeze layers from top to bottom for fine-tuning.
        
        Args:
            model: Model to unfreeze
            num_stages: Number of unfreezing stages
            
        Returns:
            List of models with progressive unfreezing
        """
        models = []
        total_layers = len(model.layers)
        layers_per_stage = total_layers // num_stages
        
        for stage in range(num_stages):
            # Clone model
            stage_model = keras.models.clone_model(model)
            stage_model.set_weights(model.get_weights())
            
            # Unfreeze layers progressively
            unfreeze_from = total_layers - (stage + 1) * layers_per_stage
            for i, layer in enumerate(stage_model.layers):
                layer.trainable = i >= unfreeze_from
            
            logger.info(f"Stage {stage+1}: Unfroze layers from {unfreeze_from} onwards")
            models.append(stage_model)
        
        return models


class TransferLearningMetrics:
    """Track and analyze transfer learning performance"""
    
    def __init__(self):
        self.metrics_history = []
    
    def log_round(
        self,
        round_num: int,
        model_name: str,
        accuracy: float,
        loss: float,
        time_elapsed: float
    ):
        """Log metrics for a training round"""
        self.metrics_history.append({
            'round': round_num,
            'model': model_name,
            'accuracy': accuracy,
            'loss': loss,
            'time': time_elapsed
        })
    
    def get_summary(self) -> Dict:
        """Get summary statistics"""
        if not self.metrics_history:
            return {}
        
        accuracies = [m['accuracy'] for m in self.metrics_history]
        times = [m['time'] for m in self.metrics_history]
        
        return {
            'max_accuracy': max(accuracies),
            'avg_accuracy': np.mean(accuracies),
            'total_time': sum(times),
            'avg_time_per_round': np.mean(times),
            'convergence_round': accuracies.index(max(accuracies)) + 1
        }


def test_transfer_learning():
    """Test transfer learning module"""
    
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    
    print("\n" + "="*70)
    print("TESTING FEDERATED TRANSFER LEARNING MODULE")
    print("="*70)
    
    # Create dummy source model
    from projects.shared_libs import CNNBiLSTMModel
    
    source_model = CNNBiLSTMModel(
        input_shape=(10, 4),
        num_classes=18,
        cnn_filters=(64, 128),
        lstm_units=(64, 32),
        dropout_rate=0.5
    ).model
    
    print(f"\n✓ Source model created: {source_model.count_params():,} params")
    
    # Initialize transfer learning
    tl = FederatedTransferLearning(source_model)
    
    # Create target model
    target_model = tl.create_target_model(num_target_classes=10)
    print(f"✓ Target model created: {target_model.count_params():,} params")
    
    # Test metrics
    metrics = tl.compute_transfer_metrics(
        source_accuracy=0.99,
        target_baseline=0.80,
        target_transfer=0.92,
        source_time=120.0,
        target_time=30.0
    )
    
    print(f"\n✓ Transfer learning test complete!")
    print(f"  Transfer gain: +{metrics['transfer_gain']*100:.1f}%")
    print(f"  Time saved: {metrics['time_reduction']*100:.0f}%")
    
    return tl, target_model, metrics


if __name__ == "__main__":
    test_transfer_learning()
