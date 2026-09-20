"""
Extreme Imbalance Stress Test
Trains CNN-BiLSTM on:
1. 50/50 Balanced Dataset
2. 75/25 Inverted Imbalance Dataset (Majority Benign)
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
    FeatureExtractor, split_data, CNNBiLSTMModel, ModelTrainer
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("StressTest")

def run_stress_test():
    logger.info("="*70)
    logger.info("🔥 EXTREME IMBALANCE STRESS TEST")
    logger.info("Comparing Model Performance on 50/50 vs 75/25 Splits")
    logger.info("="*70)
    
    datasets = [
        ("dataset_50_50.csv", "50% Benign / 50% Attack"),
        ("dataset_75_25.csv", "75% Benign / 25% Attack")
    ]
    
    results = {}
    
    for filename, label in datasets:
        path = project_root / "ddosdfl" / filename
        
        logger.info("\n" + "-"*60)
        logger.info(f"🧪 Experiment: {label}")
        logger.info("-" * 60)
        
        if not path.exists():
            logger.error(f"❌ Dataset {filename} not found! (Wait for generator)")
            continue
            
        # 1. Load
        logger.info(f"Loading {filename}...")
        df = pd.read_csv(path)
        logger.info(f"Loaded {len(df):,} records")
        
        # Verify Split
        # Use last column usually for label
        # But we should find 'Label' column
        cols = [c for c in df.columns if "Label" in c]
        if cols:
            label_col = cols[0]
            benign_count = (df[label_col].astype(str).str.upper().str.strip() == 'BENIGN').sum()
            attack_count = len(df) - benign_count
            actual_ratio = benign_count / len(df)
            logger.info(f"Actual Split: {benign_count:,} Benign ({actual_ratio*100:.1f}%) / {attack_count:,} Attack")
        
        # 2. Preprocess
        extractor = FeatureExtractor()
        X, y = extractor.preprocess(df, fit=True)
        
        # FORCE BINARY: 0 = Benign, 1 = Attack
        # Solves "Classes with too few members" error for rare attack types
        y = (y > 0).astype(int)
        
        # Reshape for CNN-BiLSTM (sample, 10, 4)
        if X.shape[1] < 40:
            X = np.pad(X, ((0,0), (0, 40-X.shape[1])))
        else:
            X = X[:, :40]
        X = X.reshape(-1, 10, 4)
        
        # 3. Split
        X_train, X_test, _, y_train, y_test, _ = split_data(
            X, y, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15
        )
        
        # 4. Train
        num_classes = 2 # Binary
        logger.info(f"Training CNN-BiLSTM (Binary Mode)...")
        
        model = CNNBiLSTMModel(input_shape=(10, 4), num_classes=num_classes)
        trainer = ModelTrainer(model)
        
        # Train 3 epochs for speed, typically converges fast
        trainer.train(X_train, y_train, X_val=X_test, y_val=y_test, epochs=3, batch_size=128)
        
        # 5. Evaluate
        eval_res = trainer.evaluate(X_test, y_test)
        acc = eval_res['accuracy']
        results[label] = acc
        
        logger.info(f"✅ {label} Accuracy: {acc:.4f}")

    # Final Report
    logger.info("\n" + "="*70)
    logger.info("🏆 FINAL STRESS TEST RESULTS")
    logger.info("="*70)
    for lbl, score in results.items():
        logger.info(f"{lbl:<30} : {score:.4f} ({score*100:.2f}%)")
    logger.info("="*70)

if __name__ == "__main__":
    run_stress_test()
