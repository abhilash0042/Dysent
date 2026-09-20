
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
logger = logging.getLogger("TransformerValidation")

# Path provided by user
REAL_DATA_PATH = Path("C:/Users/HP/Desktop/Major Project/Main File-Code/data/CIC-DDoS2019 Dataset/cicddos2019_dataset.csv")

def validate_transformer():
    logger.info("="*70)
    logger.info("🚀 VALIDATING TRANSFORMER MODEL ON REAL DATA")
    logger.info("="*70)
    
    if not REAL_DATA_PATH.exists():
        logger.error(f"❌ File not found at: {REAL_DATA_PATH}")
        return False
        
    # Load 100k samples
    try:
        df = pd.read_csv(REAL_DATA_PATH, nrows=100000, encoding='utf-8', low_memory=False)
        logger.info(f"✅ Loaded {len(df)} records.")
    except Exception as e:
        logger.error(f"❌ Failed to load CSV: {e}")
        return False

    # Preprocess
    logger.info("🔄 Preprocessing...")
    extractor = FeatureExtractor()
    X, y = extractor.preprocess(df, fit=True)
    
    # Reshape for Sequence Models (Steps, Features)
    # 40 standard features -> 10 steps x 4 features
    if X.shape[1] < 40:
        X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
    else:
        X = X[:, :40]
    X_reshaped = X.reshape(-1, 10, 4)
    logger.info(f"✅ Reshaped to: {X_reshaped.shape}")

    # Split
    X_train, X_test, _, y_train, y_test, _ = split_data(
        X_reshaped, y, train_ratio=0.7, val_ratio=0.1, test_ratio=0.2
    )
    
    # Instantiate Transformer
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
    
    # Train
    # Note: ModelTrainer supports any object that provides get_model()
    trainer = ModelTrainer(transformer)
    
    logger.info("🏋️ Starting Training (2 Epochs)...")
    history = trainer.train(
        X_train, y_train, 
        X_val=X_test, y_val=y_test, 
        epochs=2, 
        batch_size=64
    )
    
    # Evaluate
    logger.info("\n📊 Evaluation Results:")
    results = trainer.evaluate(X_test, y_test)
    accuracy = results.get('accuracy', 0.0)
    
    logger.info(f"🎯 Transformer Accuracy: {accuracy:.4f}")
    
    if accuracy > 0.85:
        logger.info("\n✅ SUCCESS: Transformer works great!")
    else:
        logger.warning("\n⚠️ NOTE: Accuracy might need more epochs.")

    return True

if __name__ == "__main__":
    validate_transformer()
