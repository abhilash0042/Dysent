"""
Test script for Explainable AI functionality
Demonstrates model interpretability on real predictions
"""

import sys
from pathlib import Path
import numpy as np
import logging

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import CNNBiLSTMModel, FeatureExtractor
from ddosdfl.projects.shared_libs.explainable_ai import create_explainer
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ExplainableAI_Demo")

def demo_explainable_ai():
    """Demonstrate Explainable AI on sample predictions"""
    
    logger.info("="*70)
    logger.info("🔍 EXPLAINABLE AI DEMONSTRATION")
    logger.info("="*70)
    
    # 1. Load or create a simple model
    logger.info("\n📊 Loading model...")
    model = CNNBiLSTMModel(input_shape=(10, 4), num_classes=2)
    
    # 2. Create sample data
    logger.info("📊 Creating sample data...")
    np.random.seed(42)
    
    # Benign traffic (low packet rate, normal flags)
    benign_sample = np.random.normal(0.3, 0.1, (10, 4))
    
    # Attack traffic (high packet rate, suspicious patterns)
    attack_sample = np.random.normal(0.8, 0.2, (10, 4))
    attack_sample[:, 0] = np.random.uniform(0.9, 1.0, 10)  # Very high packet rate
    
    # 3. Create explainer
    feature_names = [
        'packet_rate', 'packet_size_avg', 'syn_flag_ratio', 'unique_dst_ips'
    ]
    
    logger.info("\n🧠 Initializing Explainable AI...")
    explainer = create_explainer(model.get_model(), feature_names)
    
    # 4. Explain benign prediction
    logger.info("\n" + "="*70)
    logger.info("Example 1: Benign Traffic")
    logger.info("="*70)
    
    benign_explanation = explainer.explain_prediction(benign_sample)
    
    print(f"\n[Prediction]: {benign_explanation['prediction_label']}")
    print(f"[Confidence]: {benign_explanation['confidence']*100:.2f}%")
    print(f"\n[Explanation]: {benign_explanation['explanation_text']}")
    
    print(f"\n[Top Features]:")
    for i, (feature, contribution) in enumerate(benign_explanation['top_features'].items(), 1):
        print(f"   {i}. {feature}: {contribution*100:.1f}%")
    
    # 5. Explain attack prediction
    logger.info("\n" + "="*70)
    logger.info("Example 2: Suspicious Traffic")
    logger.info("="*70)
    
    attack_explanation = explainer.explain_prediction(attack_sample)
    
    print(f"\n[Prediction]: {attack_explanation['prediction_label']}")
    print(f"[Confidence]: {attack_explanation['confidence']*100:.2f}%")
    print(f"\n[Explanation]: {attack_explanation['explanation_text']}")
    
    print(f"\n[Top Features]:")
    for i, (feature, contribution) in enumerate(attack_explanation['top_features'].items(), 1):
        print(f"   {i}. {feature}: {contribution*100:.1f}%")
    
    # 6. Global feature importance
    logger.info("\n" + "="*70)
    logger.info("Global Feature Importance Analysis")
    logger.info("="*70)
    
    test_samples = np.random.normal(0.5, 0.3, (50, 10, 4))
    global_importance = explainer.get_global_feature_importance(test_samples, n_samples=50)
    
    print(f"\n[Global Importance]:")
    for i, (feature, importance) in enumerate(global_importance.items(), 1):
        bar_length = int(importance * 30)
        bar = "#" * bar_length
        print(f"   {i}. {feature:20s} {bar} {importance*100:.1f}%")
    
    logger.info("\n" + "="*70)
    logger.info("✅ EXPLAINABLE AI DEMO COMPLETE")
    logger.info("="*70)
    
    return True

if __name__ == "__main__":
    demo_explainable_ai()
