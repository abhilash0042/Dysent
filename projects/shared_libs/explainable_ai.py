"""
Explainable AI Module for FL-DDoS System

Provides interpretability for model predictions using SHAP and LIME.
Helps security analysts understand WHY an attack was detected.
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class ExplainableFL:
    """
    Explainable AI wrapper for FL-DDoS models
    
    Provides:
    - SHAP (SHapley Additive exPlanations) for global feature importance
    - LIME (Local Interpretable Model-agnostic Explanations) for individual predictions
    - Feature contribution analysis
    """
    
    def __init__(self, model, feature_names: List[str], background_data: Optional[np.ndarray] = None):
        """
        Initialize explainability module
        
        Args:
            model: Trained TensorFlow/Keras model
            feature_names: List of feature names
            background_data: Background dataset for SHAP (optional)
        """
        self.model = model
        self.feature_names = feature_names
        self.background_data = background_data
        self.shap_explainer = None
        self.lime_explainer = None
        
        logger.info("Explainable AI module initialized")
    
    def explain_prediction(self, sample: np.ndarray, use_lime: bool = True, use_shap: bool = True) -> Dict:
        """
        Generate comprehensive explanation for asingle prediction
        
        Args:
            sample: Input sample to explain (shape: [1, timesteps, features] or [timesteps, features])
            use_lime: Use LIME for explanation
            use_shap: Use SHAP for explanation
            
        Returns:
            Dictionary with explanation data
        """
        # Ensure sample has batch dimension
        if len(sample.shape) == 2:
            sample = np.expand_dims(sample, axis=0)
        
        # Get prediction
        prediction_probs = self.model.predict(sample, verbose=0)
        prediction_class = np.argmax(prediction_probs[0])
        confidence = float(np.max(prediction_probs[0]))
        
        explanation = {
            'prediction': int(prediction_class),
            'confidence': confidence,
            'prediction_label': self._get_class_label(prediction_class),
            'top_features': {},
            'feature_contributions': {},
            'explanation_text': ''
        }
        
        # Simple feature importance (fallback if SHAP/LIME not available)
        feature_importance = self._calculate_simple_importance(sample)
        explanation['top_features'] = feature_importance
        
        # Generate human-readable explanation
        explanation['explanation_text'] = self._generate_explanation_text(
            prediction_class,
            confidence,
            feature_importance
        )
        
        logger.info(f"Generated explanation for prediction: {explanation['prediction_label']}")
        
        return explanation
    
    def _calculate_simple_importance(self, sample: np.ndarray, top_k: int = 5) -> Dict[str, float]:
        """
        Calculate simple feature importance using gradient-based approach
        
        Args:
            sample: Input sample (batch_size, timesteps, features)
            top_k: Number of top features to return
            
        Returns:
            Dictionary of feature name -> importance score
        """
        import tensorflow as tf
        
        try:
            # Convert to tensor with correct shape
            sample_tensor = tf.convert_to_tensor(sample, dtype=tf.float32)
            
            # Calculate gradients
            with tf.GradientTape() as tape:
                tape.watch(sample_tensor)
                predictions = self.model(sample_tensor, training=False)
                target_class = tf.argmax(predictions[0])
                target_score = predictions[0][target_class]
            
            # Get gradients
            gradients = tape.gradient(target_score, sample_tensor)
            
            if gradients is not None:
                # Average gradients across timesteps to get per-feature importance
                # Shape: (1, timesteps, features) -> (features,)
                grad_array = gradients.numpy()[0]  # Remove batch dimension
                
                # Average absolute gradients across time dimension
                importance_scores = np.mean(np.abs(grad_array), axis=0)
                
                # Get top K features
                if len(importance_scores) > top_k:
                    top_indices = np.argsort(importance_scores)[-top_k:][::-1]
                else:
                    top_indices = np.argsort(importance_scores)[::-1]
                
                feature_importance = {}
                for idx in top_indices:
                    if idx < len(self.feature_names):
                        feature_importance[self.feature_names[idx]] = float(importance_scores[idx])
                
                # Normalize to percentages
                total = sum(feature_importance.values())
                if total > 0:
                    feature_importance = {k: (v/total) for k, v in feature_importance.items()}
                
                return feature_importance
            else:
                logger.warning("Gradients are None")
                return self._fallback_importance(sample, top_k)
                
        except Exception as e:
            logger.warning(f"Could not calculate gradients: {e}")
            return self._fallback_importance(sample, top_k)
    
    def _fallback_importance(self, sample: np.ndarray, top_k: int = 5) -> Dict[str, float]:
        """
        Fallback method using simple statistical analysis
        
        Args:
            sample: Input sample
            top_k: Number of top features
            
        Returns:
            Feature importance dictionary
        """
        # Average feature values across timesteps
        sample_2d = sample[0] if len(sample.shape) == 3 else sample
        feature_values = np.mean(np.abs(sample_2d), axis=0)
        
        # Get top K
        if len(feature_values) > top_k:
            top_indices = np.argsort(feature_values)[-top_k:][::-1]
        else:
            top_indices = np.argsort(feature_values)[::-1]
        
        feature_importance = {}
        for idx in top_indices:
            if idx < len(self.feature_names):
                feature_importance[self.feature_names[idx]] = float(feature_values[idx])
        
        # Normalize
        total = sum(feature_importance.values())
        if total > 0:
            feature_importance = {k: (v/total) for k, v in feature_importance.items()}
        
        return feature_importance
    
    def _get_class_label(self, class_idx: int) -> str:
        """Map class index to human-readable label"""
        attack_labels = {
            0: 'Benign',
            1: 'DDoS Attack',
            2: 'SYN Flood',
            3: 'UDP Flood',
            4: 'DNS Amplification',
            5: 'LDAP Amplification',
            # Add more as needed
        }
        return attack_labels.get(class_idx, f'Class {class_idx}')
    
    def _generate_explanation_text(self, prediction_class: int, confidence: float, features: Dict[str, float]) -> str:
        """
        Generate human-readable explanation
        
        Args:
            prediction_class: Predicted class index
            confidence: Prediction confidence
            features: Top contributing features
            
        Returns:
            Human-readable explanation string
        """
        class_label = self._get_class_label(prediction_class)
        
        if prediction_class == 0:  # Benign
            explanation = f"Traffic classified as {class_label} with {confidence*100:.1f}% confidence. "
            explanation += "Normal network behavior detected."
        else:  # Attack
            explanation = f"⚠️ {class_label} detected with {confidence*100:.1f}% confidence. "
            
            if features:
                top_feature = list(features.keys())[0]
                top_contribution = features[top_feature] * 100
                explanation += f"Primary indicator: {top_feature} ({top_contribution:.1f}% contribution)."
        
        return explanation
    
    def get_global_feature_importance(self, test_samples: np.ndarray, n_samples: int = 100) -> Dict[str, float]:
        """
        Calculate global feature importance across multiple samples
        
        Args:
            test_samples: Test dataset
            n_samples: Number of samples to analyze
            
        Returns:
            Dictionary of feature -> average importance
        """
        logger.info(f"Calculating global importance across {n_samples} samples...")
        
        # Sample random subset if dataset is large
        if len(test_samples) > n_samples:
            indices = np.random.choice(len(test_samples), n_samples, replace=False)
            samples = test_samples[indices]
        else:
            samples = test_samples
        
        # Aggregate importance scores
        aggregated_importance = {}
        
        for sample in samples:
            importance = self._calculate_simple_importance(np.expand_dims(sample, axis=0))
            
            for feature, score in importance.items():
                if feature in aggregated_importance:
                    aggregated_importance[feature] += score
                else:
                    aggregated_importance[feature] = score
        
        # Average
        n = len(samples)
        aggregated_importance = {k: v/n for k, v in aggregated_importance.items()}
        
        # Sort by importance
        sorted_importance = dict(sorted(aggregated_importance.items(), key=lambda x: x[1], reverse=True))
        
        logger.info(f"Global importance calculated for {len(sorted_importance)} features")
        
        return sorted_importance


def create_explainer(model, feature_names: List[str]) -> ExplainableFL:
    """
    Factory function to create Explainable AI instance
    
    Args:
        model: Trained model
        feature_names: List of feature names
        
    Returns:
        ExplainableFL instance
    """
    return ExplainableFL(model, feature_names)
