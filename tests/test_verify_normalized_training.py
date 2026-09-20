"""
Verification of Hybrid Model on STRICTLY BALANCED Dataset
Trains the Hybrid architecture on the normalized CSV (50/50 split)
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
logger = logging.getLogger("BalancedValidation")

DATASET_PATH = project_root / "ddosdfl" / "normalized_dataset.csv"

def verify_balanced_performance():
    logger.info("="*70)
    logger.info("⚖️ VALIDATING ON NORMALIZED (BALANCED) DATASET")
    logger.info("="*70)
    
    if not DATASET_PATH.exists():
        logger.error("Normalized dataset not found!")
        return

    # 1. Load Data
    logger.info(f"Loading {DATASET_PATH.name}...")
    df = pd.read_csv(DATASET_PATH)
    logger.info(f"Loaded {len(df)} samples")
    
    # 2. Check Balance
    label_col = [c for c in df.columns if "Label" in c][0]
    benign = df[df[label_col].str.upper().str.strip() == 'BENIGN']
    attack = df[df[label_col].str.upper().str.strip() != 'BENIGN']
    
    b_count = len(benign)
    a_count = len(attack)
    logger.info(f"\ndataset Composition:")
    logger.info(f"  Benign: {b_count} ({b_count/len(df)*100:.1f}%)")
    logger.info(f"  Attack: {a_count} ({a_count/len(df)*100:.1f}%)")
    
    if abs(b_count - a_count) > 1000:
        logger.warning("⚠️ Warning: Dataset still not perfectly balanced!")
    else:
        logger.info("✅ Dataset is STRICTLY BALANCED")

    # 3. Preprocess
    logger.info("🔄 Preprocessing (Forcing Binary Classification)...")
    extractor = FeatureExtractor()
    X, y = extractor.preprocess(df, fit=True)
    
    # FORCE BINARY: 0 = Benign, 1 = Attack
    # The preprocessor might have assigned 0 to Benign and 1..N to Attacks
    # We map >0 to 1
    y = (y > 0).astype(int)
    
    # Reshape
    if X.shape[1] < 40:
        X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
    else:
        X = X[:, :40]
    X = X.reshape(-1, 10, 4)
    
    # 4. Split
    X_train, X_test, _, y_train, y_test, _ = split_data(
        X, y, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15
    )
    
    # 5. Train Hybrid Model
    num_classes = 2 # Forced Binary
    logger.info(f"\n🧠 Training Hybrid Conv-Transformer (Binary Mode)...")
    
    mb = TransformerModel(
        input_shape=(10, 4),
        num_classes=num_classes,
        num_transformer_blocks=3,
        dropout=0.25
    )
    
    trainer = ModelTrainer(mb)
    
    history = trainer.train(
        X_train, y_train,
        X_val=X_test, y_val=y_test,
        epochs=5,
        batch_size=128
    )
    
    # 6. Evaluate
    logger.info("\n📊 Final Evaluation:")
    results = trainer.evaluate(X_test, y_test)
    acc = results['accuracy']
    
    logger.info(f"\n🎯 Balanced Accuracy: {acc:.4f} ({acc*100:.2f}%)")
    
    return True

if __name__ == "__main__":
    verify_balanced_performance()
