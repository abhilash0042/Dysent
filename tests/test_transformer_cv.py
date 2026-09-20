
import sys
import logging
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import KFold

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import (
    FeatureExtractor, TransformerModel, ModelTrainer
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TransformerCV")

REAL_DATA_PATH = Path("C:/Users/HP/Desktop/Major Project/Main File-Code/data/CIC-DDoS2019 Dataset/cicddos2019_dataset.csv")

def run_cross_validation_transformer(n_splits=5):
    logger.info("="*70)
    logger.info(f"🚀 RUNNING {n_splits}-FOLD CROSS VALIDATION ON TRANSFORMER")
    logger.info("="*70)
    
    # 1. Load Data
    try:
        df = pd.read_csv(REAL_DATA_PATH, nrows=100000, encoding='utf-8', low_memory=False)
    except Exception as e:
        logger.error(f"❌ Failed to load CSV: {e}")
        return

    # 2. Preprocess
    logger.info("🔄 Preprocessing...")
    extractor = FeatureExtractor()
    X, y = extractor.preprocess(df, fit=True)
    
    # Reshape (N, 10, 4)
    if X.shape[1] < 40:
        X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
    else:
        X = X[:, :40]
    X = X.reshape(-1, 10, 4)
    
    # 3. K-Fold Loop
    kf = KFold(n_splits=n_splits, shuffle=True, random_state=42)
    accuracies = []
    
    fold = 1
    for train_index, test_index in kf.split(X):
        logger.info(f"\n📁 FOLD {fold}/{n_splits}")
        
        X_train, X_test = X[train_index], X[test_index]
        y_train, y_test = y[train_index], y[test_index]
        
        logger.info(f"   Train size: {len(X_train)} | Test size: {len(X_test)}")
        
        # Instantiate fresh model
        transformer = TransformerModel(
            input_shape=(10, 4),
            num_classes=len(np.unique(y)),
            head_size=64,
            num_heads=4,
            ff_dim=128,
            num_transformer_blocks=2,
            dropout=0.2
        )
        trainer = ModelTrainer(transformer)
        
        # Train (Silent)
        trainer.train(X_train, y_train, epochs=2, batch_size=64)
        
        # Evaluate
        results = trainer.evaluate(X_test, y_test)
        acc = results.get('accuracy', 0.0)
        accuracies.append(acc)
        logger.info(f"   ✅ Fold {fold} Accuracy: {acc:.4f}")
        
        fold += 1

    # 4. Results
    mean_acc = np.mean(accuracies)
    std_acc = np.std(accuracies)
    
    logger.info("\n" + "="*70)
    logger.info("📊 CROSS-VALIDATION RESULTS")
    logger.info("="*70)
    logger.info(f"Individual Scores: {[f'{x:.4f}' for x in accuracies]}")
    logger.info(f"🏆 MEAN ACCURACY: {mean_acc:.4f} (+/- {std_acc:.4f})")
    
    if mean_acc > 0.95:
        logger.info("🌟 RESULT: EXCELLENT STABILITY (Normalized > 95%)")
    
if __name__ == "__main__":
    run_cross_validation_transformer()
