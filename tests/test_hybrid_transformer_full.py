"""
Validation of the new Hybrid Conv-Transformer Architecture
Trains the improved model on the mixed 30GB dataset sample
"""

import sys
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import tensorflow as tf

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import (
    FeatureExtractor, split_data, TransformerModel, ModelTrainer
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HybridTransformerTest")

# Dataset Path
DATASET_ROOT = Path(r"C:\Users\HP\Desktop\Major Project\Main File-Code\data\CIC-DDoS2019 Dataset")

def validate_hybrid_model():
    logger.info("="*70)
    logger.info("🚀 TRAINING HYBRID CONV-TRANSFORMER MODEL")
    logger.info("Arch: Conv1D + SinePosEncoding + 3xTransformer + AttentionPooling")
    logger.info("="*70)
    
    if not DATASET_ROOT.exists():
        logger.error(f"❌ Path not found: {DATASET_ROOT}")
        return

    # 1. Load Data (Smart Sampling)
    csv_files = list(DATASET_ROOT.rglob("*.csv"))[:5] # Use first 5 files for quick validation
    logger.info(f"🔍 Loading data from {len(csv_files)} files (40k samples each)...")
    
    dfs = []
    for file in csv_files:
        try:
            df_chunk = pd.read_csv(file, nrows=40000, encoding='utf-8', low_memory=False)
            dfs.append(df_chunk)
        except Exception:
            pass

    full_df = pd.concat(dfs, ignore_index=True)
    logger.info(f"✅ Total Samples: {len(full_df)} records")
    
    # 2. Preprocess
    logger.info("🔄 Preprocessing...")
    extractor = FeatureExtractor()
    X, y = extractor.preprocess(full_df, fit=True)
    
    # Reshape (N, 10, 4)
    if X.shape[1] < 40:
        X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
    else:
        X = X[:, :40]
    X = X.reshape(-1, 10, 4)
    logger.info(f"✅ Input Shape: {X.shape}")

    # 3. Split
    X_train, X_test, _, y_train, y_test, _ = split_data(
        X, y, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15
    )
    
    # 4. Build Hybrid Model
    num_classes = len(np.unique(y))
    logger.info(f"🧠 Initializing New Architecture (Classes: {num_classes})...")
    
    # Using new architecture parameters
    mb = TransformerModel(
        input_shape=(10, 4),
        num_classes=num_classes,
        num_transformer_blocks=3, # Deeper
        head_size=64,
        dropout=0.2
    )
    
    trainer = ModelTrainer(mb)
    
    # 5. Train
    EPOCHS = 5
    logger.info(f"🏋️ Starting Training ({EPOCHS} Epochs)...")
    
    history = trainer.train(
        X_train, y_train, 
        X_val=X_test, y_val=y_test, 
        epochs=EPOCHS, 
        batch_size=128
    )
    
    # 6. Evaluate
    logger.info("\n📊 Final Evaluation:")
    results = trainer.evaluate(X_test, y_test)
    accuracy = results.get('accuracy', 0.0)
    
    logger.info(f"🎯 Hybrid Model Accuracy: {accuracy:.4f} ({accuracy*100:.2f}%)")
    
    # Verify Positional Encoding is active
    model = trainer.model.get_model()
    layers = [l.name for l in model.layers]
    if any("sine_position_encoding" in l for l in layers):
        logger.info("✅ Verified: SinePositionEncoding layer is active")
    
    return True

if __name__ == "__main__":
    validate_hybrid_model()
