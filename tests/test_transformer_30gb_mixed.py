
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
    FeatureExtractor, split_data, TransformerModel, ModelTrainer
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FullDataTransformer")

# Full Dataset Path
DATASET_ROOT = Path(r"D:\Cicddos Full Dataset\archive")

def validate_on_full_dataset():
    logger.info("="*70)
    logger.info("🚀 TRAINING TRANSFORMER ON 30GB DATASET (SAMPLED MIX)")
    logger.info("="*70)
    
    if not DATASET_ROOT.exists():
        logger.error(f"❌ Path not found: {DATASET_ROOT}")
        return

    # 1. Find all CSVs
    logger.info("🔍 Scanning for CSV files...")
    # Recursive search
    csv_files = list(DATASET_ROOT.rglob("*.csv"))
    logger.info(f"✅ Found {len(csv_files)} CSV files: {[f.name for f in csv_files]}")
    
    if not csv_files:
        logger.error("No CSV files found!")
        return

    # 2. Smart Sampling (Load chunks from each file)
    # Target: ~500k rows total.
    # If 12 files, load ~40k rows from each.
    SAMPLES_PER_FILE = 40000 
    
    dfs = []
    
    for file in csv_files:
        try:
            logger.info(f"📂 Reading {file.name} (Top {SAMPLES_PER_FILE} rows)...")
            # Load chunk
            df_chunk = pd.read_csv(file, nrows=SAMPLES_PER_FILE, encoding='utf-8', low_memory=False)
            
            # Add a column to track source if useful (optional)
            # df_chunk['source_file'] = file.name
            
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
    logger.info("🔄 Preprocessing (Feature Extraction & Normalization)...")
    extractor = FeatureExtractor()
    X, y = extractor.preprocess(full_df, fit=True)
    
    # Reshape (N, 10, 4)
    if X.shape[1] < 40:
        logger.info("Padding features to 40...")
        X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
    else:
        X = X[:, :40]
    X = X.reshape(-1, 10, 4)
    logger.info(f"✅ Reshaped Input: {X.shape}")

    # 4. Split
    X_train, X_test, _, y_train, y_test, _ = split_data(
        X, y, train_ratio=0.7, val_ratio=0.1, test_ratio=0.2
    )
    
    # 5. Build Transformer
    num_classes = len(np.unique(y))
    logger.info(f"🧠 Building Transformer (Classes: {num_classes})...")
    
    transformer = TransformerModel(
        input_shape=(10, 4),
        num_classes=num_classes,
        head_size=64,
        num_heads=4,
        ff_dim=128,
        num_transformer_blocks=2,
        dropout=0.2
    )
    
    trainer = ModelTrainer(transformer)
    
    # 6. Train
    # Increase epochs since data is larger and diverse
    EPOCHS = 5
    logger.info(f"🏋️ Starting Training ({EPOCHS} Epochs)...")
    
    history = trainer.train(
        X_train, y_train, 
        X_val=X_test, y_val=y_test, 
        epochs=EPOCHS, 
        batch_size=128 # Larger batch size for speed
    )
    
    # 7. Evaluate
    logger.info("\n📊 Evaluation Results:")
    results = trainer.evaluate(X_test, y_test)
    accuracy = results.get('accuracy', 0.0)
    
    logger.info(f"🎯 Transformer Accuracy (on 30GB Mix): {accuracy:.4f}")
    
    # Save Feature Extractor for future usage?
    # extractor.save("full_dataset_extractor.pkl")
    
    return True

if __name__ == "__main__":
    validate_on_full_dataset()
