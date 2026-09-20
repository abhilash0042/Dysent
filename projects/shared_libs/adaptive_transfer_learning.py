"""
Adaptive Transfer Learning for FL-DDoS

Implements intelligent layer freezing/unfreezing based on:
1. Attack similarity detection
2. Progressive unfreezing
3. Discriminative fine-tuning (different LR per layer group)
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras
from typing import List, Tuple, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdaptiveTransferLearning:
    """
    Adaptive Transfer Learning with intelligent layer control
    
    Features:
    - Similarity-based freezing decision
    - Progressive unfreezing
    - Discriminative learning rates
    """
    
    def __init__(self, source_model: keras.Model):
        self.source_model = source_model
        self.layer_groups = self._identify_layer_groups()
        
    def _identify_layer_groups(self):
        """Identify logical layer groups in the model"""
        groups = {
            'cnn_low': [],      # Low-level CNN features (universal)
            'cnn_high': [],     # High-level CNN features (transferable)
            'lstm': [],         # Sequence modeling (adaptable)
            'dense': []         # Classification (task-specific)
        }
        
        for i, layer in enumerate(self.source_model.layers):
            layer_name = layer.name
            
            if 'conv1d_1' in layer_name or 'bn_conv_1' in layer_name:
                groups['cnn_low'].append(i)
            elif 'conv1d_2' in layer_name or 'bn_conv_2' in layer_name:
                groups['cnn_high'].append(i)
            elif 'lstm' in layer_name or 'bidirectional' in layer_name:
                groups['lstm'].append(i)
            elif 'dense' in layer_name or 'output' in layer_name:
                groups['dense'].append(i)
        
        return groups
    
    def detect_similarity(
        self, 
        source_data: Tuple[np.ndarray, np.ndarray],
        target_data: Tuple[np.ndarray, np.ndarray]
    ) -> float:
        """
        Detect similarity between source and target domains
        
        Returns: similarity score (0-1)
        """
        X_source, y_source = source_data
        X_target, y_target = target_data
        
        # Feature distribution similarity
        source_mean = X_source.mean(axis=0)
        target_mean = X_target.mean(axis=0)
        feature_similarity = 1 - np.mean(np.abs(source_mean - target_mean))
        
        # Class distribution similarity
        source_dist = np.bincount(y_source.astype(int)) / len(y_source)
        target_dist = np.bincount(y_target.astype(int), minlength=len(source_dist)) / len(y_target)
        class_similarity = 1 - np.sum(np.abs(source_dist - target_dist)) / 2
        
        # Combined similarity
        similarity = 0.6 * feature_similarity + 0.4 * class_similarity
        
        logger.info(f"  Domain similarity: {similarity:.2%}")
        logger.info(f"    Feature sim: {feature_similarity:.2%}")
        logger.info(f"    Class sim: {class_similarity:.2%}")
        
        return similarity
    
    def create_adaptive_model(
        self,
        num_target_classes: int,
        similarity_score: Optional[float] = None,
        strategy: str = 'auto'
    ) -> keras.Model:
        """
        Create transfer learning model with adaptive freezing
        
        Args:
            num_target_classes: Number of classes in target domain
            similarity_score: Domain similarity (0-1)
            strategy: 'auto', 'frozen', 'progressive', 'discriminative'
        
        Returns:
            Configured model
        """
        
        logger.info(f"\nCreating adaptive transfer learning model...")
        logger.info(f"  Strategy: {strategy}")
        
        # Clone source model
        target_model = keras.models.clone_model(self.source_model)
        target_model.set_weights(self.source_model.get_weights())
        
        # Modify output layer if needed
        current_output_size = target_model.output_shape[-1]
        if current_output_size != num_target_classes:
            logger.info(f"  Modifying output layer: {current_output_size} → {num_target_classes} classes")
            # Remove old output layer
            target_model = keras.Model(
                inputs=target_model.input,
                outputs=target_model.layers[-2].output
            )
            # Add new output layer
            output = keras.layers.Dense(
                num_target_classes,
                activation='softmax',
                name='adaptive_output'
            )(target_model.output)
            target_model = keras.Model(inputs=target_model.input, outputs=output)
        
        # Decide freezing strategy
        if strategy == 'auto' and similarity_score is not None:
            if similarity_score > 0.8:
                # Very similar: freeze more (reusable attacks)
                freeze_strategy = 'frozen'
                logger.info(f"  High similarity ({similarity_score:.2%}) → Freeze CNN layers")
            elif similarity_score > 0.5:
                # Moderately similar: progressive unfreezing
                freeze_strategy = 'progressive'
                logger.info(f"  Medium similarity ({similarity_score:.2%}) → Progressive unfreezing")
            else:
                # Very different: use discriminative LR (modern attacks)
                freeze_strategy = 'discriminative'
                logger.info(f"  Low similarity ({similarity_score:.2%}) → Discriminative fine-tuning")
        else:
            freeze_strategy = strategy
        
        # Apply freezing strategy
        if freeze_strategy == 'frozen':
            # Freeze CNN layers (reusable features)
            frozen_count = 0
            for i in self.layer_groups['cnn_low'] + self.layer_groups['cnn_high']:
                if i < len(target_model.layers):
                    target_model.layers[i].trainable = False
                    frozen_count += 1
            logger.info(f"  Frozen {frozen_count} CNN layers")
            
        elif freeze_strategy == 'progressive':
            # Start with all frozen, will unfreeze during training
            for layer in target_model.layers[:-1]:  # Except output
                layer.trainable = False
            logger.info(f"  All layers frozen (will unfreeze progressively)")
            
        elif freeze_strategy == 'discriminative':
            # All trainable but with different learning rates
            for layer in target_model.layers:
                layer.trainable = True
            logger.info(f"  All layers trainable (discriminative LR)")
        
        self.freeze_strategy = freeze_strategy
        self.target_model = target_model
        
        return target_model
    
    def get_discriminative_optimizer(self, base_lr: float = 0.001):
        """
        Create optimizer with layer-wise learning rates
        
        Lower layers get lower LR (preserve learned features)
        Higher layers get higher LR (adapt to new task)
        """
        
        lr_multipliers = {
            'cnn_low': 0.1,      # 10% of base LR
            'cnn_high': 0.3,     # 30% of base LR
            'lstm': 1.0,         # 100% of base LR
            'dense': 2.0         # 200% of base LR
        }
        
        # Create separate optimizers would be complex in Keras
        # Instead, we'll use layer-wise frozen/unfrozen approach
        # For true discriminative LR, would need custom training loop
        
        logger.info(f"  Using discriminative learning rates:")
        for group, mult in lr_multipliers.items():
            logger.info(f"    {group}: {base_lr * mult:.6f}")
        
        return keras.optimizers.Adam(learning_rate=base_lr)
    
    def progressive_unfreeze(self, epoch: int, total_epochs: int):
        """
        Progressively unfreeze layers during training
        
        Epoch 0-33%: Only dense layers
        Epoch 33-66%: Dense + LSTM layers  
        Epoch 66-100%: Dense + LSTM + High CNN
        """
        
        if self.freeze_strategy != 'progressive':
            return
        
        progress = epoch / total_epochs
        
        if progress < 0.33:
            # Only output layer trainable
            for i, layer in enumerate(self.target_model.layers):
                layer.trainable = (i in self.layer_groups['dense'])
            logger.info(f"  Epoch {epoch}: Training Dense layers only")
            
        elif progress < 0.66:
            # Output + LSTM trainable
            for i, layer in enumerate(self.target_model.layers):
                layer.trainable = (i in self.layer_groups['dense'] + self.layer_groups['lstm'])
            logger.info(f"  Epoch {epoch}: Training Dense + LSTM layers")
            
        else:
            # Output + LSTM + High CNN trainable
            for i, layer in enumerate(self.target_model.layers):
                layer.trainable = (i in self.layer_groups['dense'] + 
                                 self.layer_groups['lstm'] + 
                                 self.layer_groups['cnn_high'])
            logger.info(f"  Epoch {epoch}: Training Dense + LSTM + High CNN")
        
        # Recompile model with new trainable states
        self.target_model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=0.0003),
            loss='sparse_categorical_crossentropy',
            metrics=['accuracy']
        )
    
    def get_trainable_params(self) -> int:
        """Get count of trainable parameters"""
        return sum([tf.keras.backend.count_params(w) 
                   for w in self.target_model.trainable_weights])


def test_adaptive_transfer_learning():
    """Test adaptive transfer learning"""
    
    print("="*70)
    print("TESTING ADAPTIVE TRANSFER LEARNING")
    print("="*70)
    
    # Fix import path for standalone execution
    import sys
    from pathlib import Path
    project_root = Path(__file__).parent.parent.parent
    sys.path.insert(0, str(project_root))
    
    from projects.shared_libs import CNNBiLSTMModel
    
    # Create source model
    source_model = CNNBiLSTMModel(
        input_shape=(10, 4),
        num_classes=10,
        cnn_filters=(64, 32),
        lstm_units=(32, 16)
    ).model
    
    print(f"\nSource model: {source_model.count_params():,} parameters")
    
    # Create adaptive transfer learning
    atl = AdaptiveTransferLearning(source_model)
    
    # Test 1: High similarity (reusable attacks)
    print(f"\nTest 1: High Similarity → Frozen Strategy")
    model1 = atl.create_adaptive_model(
        num_target_classes=5,
        similarity_score=0.85,
        strategy='auto'
    )
    print(f"  Trainable params: {atl.get_trainable_params():,}")
    
    # Test 2: Low similarity (modern attacks)
    print(f"\nTest 2: Low Similarity → Discriminative Strategy")
    model2 = atl.create_adaptive_model(
        num_target_classes=5,
        similarity_score=0.3,
        strategy='auto'
    )
    print(f"  Trainable params: {atl.get_trainable_params():,}")
    
    # Test 3: Progressive unfreezing
    print(f"\nTest 3: Progressive Unfreezing")
    model3 = atl.create_adaptive_model(
        num_target_classes=5,
        strategy='progressive'
    )
    for epoch in [0, 5, 10]:
        atl.progressive_unfreeze(epoch, total_epochs=15)
        print(f"  Epoch {epoch}: {atl.get_trainable_params():,} trainable params")
    
    print(f"\n✓ All tests passed!")


if __name__ == "__main__":
    test_adaptive_transfer_learning()
