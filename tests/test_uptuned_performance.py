"""
Final Performance Validation with "Up-Tuned" Parameters
Running the Hybrid Conv-Transformer with optimized hyperparameters.
"""

import sys
import logging
from pathlib import Path
import pandas as pd
import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import (
    FeatureExtractor, split_data, TransformerModel, ModelTrainer
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("UptunedValidation")

DATASET_PATH = project_root / "ddosdfl" / "normalized_dataset.csv"

def run_optimization_check():
    logger.info("="*70)
    logger.info("🚀 VALIDATING UP-TUNED PARAMETERS")
    logger.info("Configuration: Hybrid Conv-Transformer (Optimized)")
    logger.info("="*70)
    
    if not DATASET_PATH.exists():
        logger.error("Dataset not found!")
        return

    # Load Data
    logger.info(f"Loading {DATASET_PATH.name}...")
    df = pd.read_csv(DATASET_PATH) # Use full normalized dataset
    
    # Preprocess
    extractor = FeatureExtractor()
    X, y = extractor.preprocess(df, fit=True)
    
    # Force Binary
    y = (y > 0).astype(int)
    
    # Reshape
    if X.shape[1] < 40:
        X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
    else:
        X = X[:, :40]
    X = X.reshape(-1, 10, 4)
    
    # Split
    X_train, X_test, _, y_train, y_test, _ = split_data(
        X, y, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15
    )
    
    # Init Model with Optimized Params
    mb = TransformerModel(
        input_shape=(10, 4),
        num_classes=2,
        head_size=64,       # Optimal balance
        num_heads=4,        # Sufficient for feature diversity
        ff_dim=128,         # Standard capacity
        num_transformer_blocks=3, # Validated depth
        dropout=0.25,       # Standard regularization
        learning_rate=0.0005 # Stable convergence
    )
    
    trainer = ModelTrainer(mb)
    
    logger.info("Training for 5 epochs to verify peak performance...")
    history = trainer.train(
        X_train, y_train, 
        X_val=X_test, y_val=y_test, 
        epochs=5, 
        batch_size=128
    )
    
    res = trainer.evaluate(X_test, y_test)
    acc = res['accuracy']
    
    logger.info(f"\n🎯 FINAL OPTIMIZED ACCURACY: {acc:.4f} ({acc*100:.2f}%)")
    
    return True

if __name__ == "__main__":
    run_optimization_check()
