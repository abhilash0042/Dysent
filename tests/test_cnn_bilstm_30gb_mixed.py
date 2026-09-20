
import sys
import logging
from pathlib import Path
import numpy as np
import pandas as pd
import glob
import os

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import (
    FeatureExtractor, split_data, CNNBiLSTMModel, ModelTrainer
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FullDataCNNBilstm")

# Full Dataset Path
DATASET_ROOT = Path(r"D:\Cicddos Full Dataset\archive")

def validate_cnn_bilstm_full_dataset():
    logger.info("="*70)
    logger.info("🚀 TRAINING CNN-BiLSTM ON 30GB DATASET (SAMPLED MIX)")
    logger.info("="*70)
    
    if not DATASET_ROOT.exists():
        logger.error(f"❌ Path not found: {DATASET_ROOT}")
        return

    # 1. Find all CSVs
    logger.info("🔍 Scanning for CSV files...")
    csv_files = list(DATASET_ROOT.rglob("*.csv"))
    logger.info(f"✅ Found {len(csv_files)} CSV files")
    
    if not csv_files:
        logger.error("No CSV files found!")
        return

    # 2. Smart Sampling
    SAMPLES_PER_FILE = 40000 
    dfs = []
    
    for file in csv_files:
        try:
            logger.info(f"📂 Reading {file.name} (Top {SAMPLES_PER_FILE} rows)...")
            df_chunk = pd.read_csv(file, nrows=SAMPLES_PER_FILE, encoding='utf-8', low_memory=False)
            dfs.append(df_chunk)
        except Exception as e:
            logger.warning(f"⚠️ Failed to read {file.name}: {e}")

    if not dfs:
        logger.error("❌ Could not load any data.")
        return

    # Combine
    full_df = pd.concat(dfs, ignore_index=True)
    logger.info(f"✅ Combined Dataset Size: {len(full_df)} records")
    
    # 3. Preprocess
    logger.info("🔄 Preprocessing...")
    extractor = FeatureExtractor()
    X, y = extractor.preprocess(full_df, fit=True)
    
    # Reshape (N, 10, 4)
    if X.shape[1] < 40:
        X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
    else:
        X = X[:, :40]
    X = X.reshape(-1, 10, 4)
    logger.info(f"✅ Reshaped Input: {X.shape}")

    # 4. Split
    X_train, X_test, _, y_train, y_test, _ = split_data(
        X, y, train_ratio=0.7, val_ratio=0.1, test_ratio=0.2
    )
    
    # 5. Build CNN-BiLSTM
    num_classes = len(np.unique(y))
    logger.info(f"🧠 Building CNN-BiLSTM (Classes: {num_classes})...")
    
    # Using default architecture parameters
    mb = CNNBiLSTMModel(
        input_shape=(10, 4),
        num_classes=num_classes
    )
    
    trainer = ModelTrainer(mb)
    
    # 6. Train
    EPOCHS = 5
    logger.info(f"🏋️ Starting Training ({EPOCHS} Epochs)...")
    
    history = trainer.train(
        X_train, y_train, 
        X_val=X_test, y_val=y_test, 
        epochs=EPOCHS, 
        batch_size=128
    )
    
    # 7. Evaluate
    logger.info("\n📊 Evaluation Results:")
    results = trainer.evaluate(X_test, y_test)
    accuracy = results.get('accuracy', 0.0)
    
    logger.info(f"🎯 CNN-BiLSTM Accuracy (on 30GB Mix): {accuracy:.4f}")
    
    return True

if __name__ == "__main__":
    validate_cnn_bilstm_full_dataset()
