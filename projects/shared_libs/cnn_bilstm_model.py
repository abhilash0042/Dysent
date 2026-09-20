"""
CNN-BiLSTM Deep Learning Model for DDoS Detection

Hybrid architecture combining:
- CNN layers for spatial/flow-level pattern extraction
- BiLSTM layers for temporal sequence learning
"""

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers, models
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint, ReduceLROnPlateau
import numpy as np
from typing import Tuple, Dict, Optional
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class CNNBiLSTMModel:
    """CNN-BiLSTM hybrid model for DDoS detection"""
    
    def __init__(
        self,
        input_shape: Tuple[int, int],  # (timesteps, features)
        num_classes: int,
        cnn_filters: Tuple[int, ...] = (64, 128),
        cnn_kernel_size: int = 3,
        lstm_units: Tuple[int, ...] = (64, 32),
        dropout_rate: float = 0.5,
        learning_rate: float = 0.001
    ):
        """
        Initialize CNN-BiLSTM model
        
        Args:
            input_shape: Input shape (timesteps, features)
            num_classes: Number of output classes
            cnn_filters: Number of filters for each CNN layer
            cnn_kernel_size: Kernel size for CNN layers
            lstm_units: Number of units for each BiLSTM layer
            dropout_rate: Dropout rate
            learning_rate: Learning rate for optimizer
        """
        self.input_shape = input_shape
        self.num_classes = num_classes
        self.cnn_filters = cnn_filters
        self.cnn_kernel_size = cnn_kernel_size
        self.lstm_units = lstm_units
        self.dropout_rate = dropout_rate
        self.learning_rate = learning_rate
        
        self.model = self._build_model()
        
    def _build_model(self) -> keras.Model:
        """Build CNN-BiLSTM architecture"""
        logger.info("Building CNN-BiLSTM model...")
        logger.info(f"Input shape: {self.input_shape}")
        logger.info(f"Output classes: {self.num_classes}")
        
        inputs = layers.Input(shape=self.input_shape, name='input')
        x = inputs
        
        # CNN Layers for spatial feature extraction
        for i, filters in enumerate(self.cnn_filters):
            x = layers.Conv1D(
                filters=filters,
                kernel_size=self.cnn_kernel_size,
                padding='same',
                activation='relu',
                name=f'conv1d_{i+1}'
            )(x)
            x = layers.BatchNormalization(name=f'bn_conv_{i+1}')(x)
            
        # Max pooling to reduce dimensionality
        x = layers.MaxPooling1D(pool_size=2, name='maxpool')(x)
        
        # Bidirectional LSTM layers for temporal learning
        for i, units in enumerate(self.lstm_units):
            return_sequences = (i < len(self.lstm_units) - 1)
            x = layers.Bidirectional(
                layers.LSTM(
                    units,
                    return_sequences=return_sequences,
                    dropout=self.dropout_rate * 0.5,  # Internal LSTM dropout
                    name=f'lstm_{i+1}'
                ),
                name=f'bilstm_{i+1}'
            )(x)
            x = layers.BatchNormalization(name=f'bn_lstm_{i+1}')(x)
        
        # Dropout for regularization
        x = layers.Dropout(self.dropout_rate, name='dropout')(x)
        
        # Output layer
        if self.num_classes == 2:
            # Binary classification
            outputs = layers.Dense(
                1, 
                activation='sigmoid',
                name='output'
            )(x)
            loss = 'binary_crossentropy'
            metrics = [
                'accuracy',
                keras.metrics.Precision(name='precision'),
                keras.metrics.Recall(name='recall'),
                keras.metrics.AUC(name='auc')
            ]
        else:
            # Multi-class classification
            outputs = layers.Dense(
                self.num_classes,
                activation='softmax',
                name='output'
            )(x)
            loss = 'sparse_categorical_crossentropy'
            metrics = [
                'accuracy',
                keras.metrics.SparseCategoricalAccuracy(name='sparse_acc')
            ]
        
        # Create model
        model = keras.Model(inputs=inputs, outputs=outputs, name='CNN_BiLSTM')
        
        # Compile model
        model.compile(
            optimizer=keras.optimizers.Adam(learning_rate=self.learning_rate),
            loss=loss,
            metrics=metrics
        )
        
        logger.info(f"Model built successfully")
        logger.info(f"Total parameters: {model.count_params():,}")
        
        return model
    
    def get_model(self) -> keras.Model:
        """Get the Keras model"""
        return self.model
    
    def summary(self):
        """Print model summary"""
        self.model.summary()
    
    def get_weights(self) -> list:
        """Get model weights (for federated learning)"""
        return self.model.get_weights()
    
    def set_weights(self, weights: list):
        """Set model weights (for federated learning)"""
        self.model.set_weights(weights)
    
    def save_model(self, filepath: str):
        """Save model to file"""
        self.model.save(filepath)
        logger.info(f"Model saved to {filepath}")
    
    def load_model(self, filepath: str):
        """Load model from file"""
        self.model = keras.models.load_model(filepath)
        logger.info(f"Model loaded from {filepath}")


class ModelTrainer:
    """Training utilities for CNN-BiLSTM model"""
    
    def __init__(self, model: CNNBiLSTMModel, model_dir: str = "./models"):
        """
        Initialize trainer
        
        Args:
            model: CNNBiLSTMModel instance
            model_dir: Directory to save models
        """
        self.model = model
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.history = None
        
    def prepare_data_for_training(
        self, 
        X: np.ndarray, 
        y: np.ndarray,
        timesteps: int = 10
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Reshape flat features into sequences for LSTM
        
        Args:
            X: Features (num_samples, num_features)
            y: Labels (num_samples,)
            timesteps: Number of timesteps for sequences
            
        Returns:
            Reshaped X and y
        """
        num_samples, num_features = X.shape
        
        # Calculate number of features per timestep
        features_per_timestep = num_features // timesteps
        
        if features_per_timestep * timesteps != num_features:
            # Pad features to make it divisible
            pad_size = (features_per_timestep * timesteps) - num_features
            if pad_size > 0:
                X = np.pad(X, ((0, 0), (0, pad_size)), mode='constant')
                num_features = X.shape[1]
                features_per_timestep = num_features // timesteps
        
        # Reshape to (num_samples, timesteps, features_per_timestep)
        X_reshaped = X.reshape(num_samples, timesteps, features_per_timestep)
        
        logger.info(f"Reshaped data: {X.shape} -> {X_reshaped.shape}")
        
        return X_reshaped, y
    
    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 50,
        batch_size: int = 32,
        class_weights: Optional[Dict[int, float]] = None,
        callbacks: Optional[list] = None
    ) -> keras.callbacks.History:
        """
        Train the model
        
        Args:
            X_train: Training features
            y_train: Training labels
            X_val: Validation features
            y_val: Validation labels
            epochs: Number of epochs
            batch_size: Batch size
            class_weights: Class weights for imbalanced datasets
            callbacks: Additional callbacks
            
        Returns:
            Training history
        """
        logger.info(f"Training model for {epochs} epochs...")
        
        # Default callbacks
        if callbacks is None:
            callbacks = []
        
        # Add early stopping
        callbacks.append(EarlyStopping(
            monitor='val_loss' if X_val is not None else 'loss',
            patience=10,
            restore_best_weights=True,
            verbose=1
        ))
        
        # Add model checkpoint
        checkpoint_path = self.model_dir / "best_model.keras"
        callbacks.append(ModelCheckpoint(
            filepath=str(checkpoint_path),
            monitor='val_loss' if X_val is not None else 'loss',
            save_best_only=True,
            verbose=1
        ))
        
        # Add learning rate reduction
        callbacks.append(ReduceLROnPlateau(
            monitor='val_loss' if X_val is not None else 'loss',
            factor=0.5,
            patience=5,
            min_lr=1e-7,
            verbose=1
        ))
        
        # Prepare validation data
        validation_data = None
        if X_val is not None and y_val is not None:
            validation_data = (X_val, y_val)
        
        # Train model
        self.history = self.model.get_model().fit(
            X_train, y_train,
            validation_data=validation_data,
            epochs=epochs,
            batch_size=batch_size,
            class_weight=class_weights,
            callbacks=callbacks,
            verbose=1
        )
        
        logger.info("Training completed")
        
        return self.history
    
    def evaluate(
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
            Dictionary of metrics
        """
        logger.info("Evaluating model...")
        
        results = self.model.get_model().evaluate(
            X_test, y_test,
            batch_size=batch_size,
            verbose=1,
            return_dict=True
        )
        
        logger.info("Evaluation results:")
        for metric, value in results.items():
            logger.info(f"  {metric}: {value:.4f}")
        
        return results
    
    def predict(
        self,
        X: np.ndarray,
        batch_size: int = 32
    ) -> np.ndarray:
        """
        Make predictions
        
        Args:
            X: Input features
            batch_size: Batch size
            
        Returns:
            Predictions
        """
        predictions = self.model.get_model().predict(
            X,
            batch_size=batch_size,
            verbose=0
        )
        
        return predictions


class ModelEvaluator:
    """Evaluation metrics and utilities"""
    
    @staticmethod
    def compute_metrics(
        y_true: np.ndarray,
        y_pred: np.ndarray,
        num_classes: int
    ) -> Dict[str, float]:
        """
        Compute comprehensive evaluation metrics
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            num_classes: Number of classes
            
        Returns:
            Dictionary of metrics
        """
        from sklearn.metrics import (
            accuracy_score, precision_score, recall_score,
            f1_score, confusion_matrix, classification_report
        )
        
        # Convert predictions if necessary
        if len(y_pred.shape) > 1:
            if num_classes == 2:
                y_pred = (y_pred > 0.5).astype(int).flatten()
            else:
                y_pred = np.argmax(y_pred, axis=1)
        
        # Compute metrics
        accuracy = accuracy_score(y_true, y_pred)
        
        avg_method = 'binary' if num_classes == 2 else 'weighted'
        precision = precision_score(y_true, y_pred, average=avg_method, zero_division=0)
        recall = recall_score(y_true, y_pred, average=avg_method, zero_division=0)
        f1 = f1_score(y_true, y_pred, average=avg_method, zero_division=0)
        
        conf_matrix = confusion_matrix(y_true, y_pred)
        
        logger.info("=" * 60)
        logger.info("EVALUATION METRICS")
        logger.info("=" * 60)
        logger.info(f"Accuracy:  {accuracy:.4f}")
        logger.info(f"Precision: {precision:.4f}")
        logger.info(f"Recall:    {recall:.4f}")
        logger.info(f"F1-Score:  {f1:.4f}")
        logger.info("\nConfusion Matrix:")
        logger.info(f"\n{conf_matrix}")
        logger.info("\nClassification Report:")
        logger.info(f"\n{classification_report(y_true, y_pred, zero_division=0)}")
        logger.info("=" * 60)
        
        return {
            'accuracy': accuracy,
            'precision': precision,
            'recall': recall,
            'f1_score': f1,
            'confusion_matrix': conf_matrix.tolist()
        }
    
    @staticmethod
    def compute_class_weights(y: np.ndarray, num_classes: int) -> Dict[int, float]:
        """
        Compute class weights for imbalanced datasets
        
        Args:
            y: Labels
            num_classes: Number of classes
            
        Returns:
            Dictionary of class weights
        """
        from sklearn.utils.class_weight import compute_class_weight
        
        classes = np.unique(y)
        weights = compute_class_weight(
            class_weight='balanced',
            classes=classes,
            y=y
        )
        
        class_weights = {i: weights[i] for i in range(len(classes))}
        
        logger.info("Class weights:")
        for cls, weight in class_weights.items():
            count = np.sum(y == cls)
            logger.info(f"  Class {cls}: {weight:.4f} (n={count})")
        
        return class_weights
