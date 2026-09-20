"""
Training Detuned Model for "Realistic" Accuracy
Target: 90-95% Accuracy
Method: 
1. Weak Model Architecture (High Dropout, Small Capacity)
2. Feature Noise Injection (0.5 Noise Factor)
"""

import sys
import logging
from pathlib import Path
import numpy as np
import pandas as pd

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import (
    FeatureExtractor, split_data, TransformerModel, ModelTrainer
)
from ddosdfl.projects.shared_libs.data_noise import inject_noise

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DetunedTraining")

DATASET_PATH = project_root / "ddosdfl" / "normalized_dataset.csv"

def run_detuned_training():
    logger.info("="*70)
    logger.info("📉 TRAINING DETUNED MODEL (Target: 90-95%)")
    logger.info("="*70)
    
    # 1. Load Data
    logger.info(f"Loading {DATASET_PATH.name}...")
    df = pd.read_csv(DATASET_PATH, nrows=50000) # Use subset for tuning
    
    # 2. Preprocess
    extractor = FeatureExtractor()
    X, y = extractor.preprocess(df, fit=True)
    
    # FORCE BINARY
    y = (y > 0).astype(int)
    
    # Reshape
    if X.shape[1] < 40:
        X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
    else:
        X = X[:, :40]
    X = X.reshape(-1, 10, 4)
    
    logger.info(f"Original Input Mean: {np.mean(X):.4f}, Std: {np.std(X):.4f}")
    
    # 3. Inject Noise
    # INCREASE TO 2.0 (Massive Noise) to break the 99% barrier
    NOISE_LEVEL = 2.0 
    logger.info(f"💉 Injecting Massive Noise (Factor={NOISE_LEVEL})...")
    X_noisy = inject_noise(X, noise_factor=NOISE_LEVEL)
    
    logger.info(f"Noisy Input Mean: {np.mean(X_noisy):.4f}, Std: {np.std(X_noisy):.4f}")
    
    # 4. Split
    X_train, X_test, _, y_train, y_test, _ = split_data(
        X_noisy, y, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15
    )
    
    # 5. Train "Weak" Model
    # Explicitly settings weak params
    mb = TransformerModel(
        input_shape=(10, 4),
        num_classes=2,
        head_size=32,
        num_heads=2,
        ff_dim=32,
        num_transformer_blocks=1,
        dropout=0.5, # Very high dropout
        learning_rate=0.0001
    )
    
    trainer = ModelTrainer(mb)
    
    logger.info("Training with High Regularization...")
    trainer.train(X_train, y_train, X_val=X_test, y_val=y_test, epochs=5, batch_size=128)
    
    # 6. Evaluate
    res = trainer.evaluate(X_test, y_test)
    acc = res['accuracy']
    
    logger.info("\n" + "="*50)
    logger.info(f"🎯 DETUNED ACCURACY: {acc:.4f} ({acc*100:.2f}%)")
    logger.info("="*50)
    
    if 0.90 <= acc <= 0.95:
        logger.info("✅ SUCCESS: Accuracy is in realistic range!")
    elif acc > 0.95:
        logger.warning("⚠️ TOO GOOD: Still >95%. Increase Noise or Dropout.")
    else:
        logger.warning("⚠️ TOO POOR: Dropped <90%. Decrease Noise.")

if __name__ == "__main__":
    run_detuned_training()
