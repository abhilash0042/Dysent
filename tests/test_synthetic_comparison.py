"""
Compare Model Performance: Real-Only vs Real+Synthetic Dataset
Trains CNN-BiLSTM on both configurations and compares results
"""

import sys
from pathlib import Path
import numpy as np
import logging

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.scripts.synthetic_data_generator import generate_balanced_dataset
from ddosdfl.projects.shared_libs import (
    FeatureExtractor, split_data, CNNBiLSTMModel, ModelTrainer
)
import pandas as pd

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SyntheticComparison")

DATASET_PATH = Path(r"C:\Users\HP\Desktop\Major Project\Main File-Code\data\CIC-DDoS2019 Dataset\cicddos2019_dataset.csv")

def train_and_evaluate(X, y, dataset_name):
    """Train and evaluate model on given dataset"""
    
    logger.info("\n" + "="*70)
    logger.info(f"🚀 TRAINING ON: {dataset_name}")
    logger.info("="*70)
    
    # Reshape for CNN-BiLSTM
    if X.shape[1] < 40:
        X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
    else:
        X = X[:, :40]
    X = X.reshape(-1, 10, 4)
    
    # Split
    X_train, X_test, X_val, y_train, y_test, y_val = split_data(
        X, y, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15
    )
    
    logger.info(f"Train: {len(X_train):,}, Val: {len(X_val):,}, Test: {len(X_test):,}")
    
    # Build model
    num_classes = len(np.unique(y))
    logger.info(f"Building CNN-BiLSTM ({num_classes} classes)...")
    
    model_builder = CNNBiLSTMModel(
        input_shape=(10, 4),
        num_classes=num_classes
    )
    
    trainer = ModelTrainer(model_builder)
    
    # Train
    EPOCHS = 5
    logger.info(f"Training for {EPOCHS} epochs...")
    
    history = trainer.train(
        X_train, y_train,
        X_val=X_val, y_val=y_val,
        epochs=EPOCHS,
        batch_size=128
    )
    
    # Evaluate
    logger.info("\n📊 Evaluating..." )
    results = trainer.evaluate(X_test, y_test)
    
    accuracy = results.get('accuracy', 0.0)
    
    logger.info(f"\n✅ {dataset_name} Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    
    # Calculate per-class metrics
    keras_model = trainer.model.get_model()
    y_pred = keras_model.predict(X_test, verbose=0)
    y_pred_classes = np.argmax(y_pred, axis=1)
    
    # Per-class accuracy
    unique_classes = np.unique(y_test)
    class_accuracies = {}
    
    for cls in unique_classes:
        mask = (y_test == cls)
        if np.sum(mask) > 0:
            class_acc = np.mean(y_pred_classes[mask] == y_test[mask])
            class_name = "Benign" if cls == 0 else f"Attack-{cls}"
            class_accuracies[class_name] = class_acc
            logger.info(f"  {class_name} Accuracy: {class_acc:.4f} ({class_acc*100:.2f}%)")
    
    return {
        'overall_accuracy': accuracy,
        'class_accuracies': class_accuracies,
        'history': history
    }


def compare_datasets():
    """Compare performance between real-only and real+synthetic datasets"""
    
    logger.info("="*70)
    logger.info("🔬 REAL vs SYNTHETIC DATA COMPARISON")
    logger.info("="*70)
    
    # Load original dataset
    logger.info("\n📂 Loading original dataset...")
    df = pd.read_csv(DATASET_PATH, nrows=50000, encoding='utf-8', low_memory=False)
    
    extractor = FeatureExtractor()
    X_real, y_real = extractor.preprocess(df, fit=True)
    
    logger.info(f"Original dataset: {len(X_real):,} samples")
    
    # Experiment 1: Train on real data only
    logger.info("\n" + "#"*70)
    logger.info("EXPERIMENT 1: REAL DATA ONLY (Imbalanced)")
    logger.info("#"*70)
    
    results_real = train_and_evaluate(X_real, y_real, "Real-Only Dataset")
    
    # Experiment 2: Generate balanced dataset with synthetic data
    logger.info("\n" + "#"*70)
    logger.info("EXPERIMENT 2: REAL + SYNTHETIC (Balanced)")
    logger.info("#"*70)
    
    X_balanced, y_balanced = generate_balanced_dataset(
        DATASET_PATH,
        target_benign_ratio=0.5
    )
    
    results_synthetic = train_and_evaluate(X_balanced, y_balanced, "Real+Synthetic Dataset")
    
    # Comparison Report
    logger.info("\n" + "="*70)
    logger.info("📊 FINAL COMPARISON REPORT")
    logger.info("="*70)
    
    logger.info("\n" + "-"*70)
    logger.info("OVERALL ACCURACY:")
    logger.info("-"*70)
    logger.info(f"Real-Only:       {results_real['overall_accuracy']:.4f} ({results_real['overall_accuracy']*100:.2f}%)")
    logger.info(f"Real+Synthetic:  {results_synthetic['overall_accuracy']:.4f} ({results_synthetic['overall_accuracy']*100:.2f}%)")
    
    diff = results_synthetic['overall_accuracy'] - results_real['overall_accuracy']
    logger.info(f"\nDifference: {diff:+.4f} ({diff*100:+.2f}%)")
    
    logger.info("\n" + "-"*70)
    logger.info("BENIGN CLASS PERFORMANCE:")
    logger.info("-"*70)
    
    real_benign = results_real['class_accuracies'].get('Benign', 0)
    synth_benign = results_synthetic['class_accuracies'].get('Benign', 0)
    
    logger.info(f"Real-Only:       {real_benign:.4f} ({real_benign*100:.2f}%)")
    logger.info(f"Real+Synthetic:  {synth_benign:.4f} ({synth_benign*100:.2f}%)")
    
    benign_diff = synth_benign - real_benign
    logger.info(f"\nImprovement: {benign_diff:+.4f} ({benign_diff*100:+.2f}%)")
    
    logger.info("\n" + "="*70)
    logger.info("🎯 CONCLUSION:")
    logger.info("="*70)
    
    if benign_diff > 0.02:  # 2% improvement
        logger.info("✅ Synthetic data IMPROVED minority class performance")
        logger.info("   Recommendation: Use balanced dataset for production")
    elif benign_diff > -0.02:
        logger.info("➡️  Synthetic data had MINIMAL impact")
        logger.info("   Recommendation: Either approach is valid")
    else:
        logger.info("⚠️  Synthetic data DECREASED performance")
        logger.info("   Recommendation: Use real-only dataset")
    
    logger.info("="*70 + "\n")
    
    return {
        'real_only': results_real,
        'real_synthetic': results_synthetic
    }


if __name__ == "__main__":
    results = compare_datasets()
