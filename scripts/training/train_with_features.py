"""
Train CNN-BiLSTM with Selected Features

Automatically loads selected features and trains model.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))


import sys
import numpy as np
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from projects.shared_libs import (
    CNNBiLSTMModel, ModelTrainer, ModelEvaluator
)
from scripts.data.load_cicddos import load_temporal_splits


def main():
    logger.info("="*70)
    logger.info("Training CNN-BiLSTM with Selected Features")
    logger.info("="*70)
    
    # The old selection file's ensemble indices include Unnamed: 0 and Class.
    # Training uses the 40 contract features as 10 real seconds instead.
    splits = load_temporal_splits()
    X_train_r = splits["X_train"]
    X_val_r = splits["X_val"]
    X_test_r = splits["X_test"]
    y_train = splits["y_train"]
    y_val = splits["y_val"]
    y_test = splits["y_test"]
    method = "temporal_40"
    y = np.concatenate([y_train, y_val, y_test])
    
    logger.info(f"Train: {X_train_r.shape}, Val: {X_val_r.shape}, Test: {X_test_r.shape}")
    
    # Create model
    logger.info("\nCreating CNN-BiLSTM model...")
    model = CNNBiLSTMModel(
        input_shape=X_train_r.shape[1:],
        num_classes=int(np.max(y)) + 1,
        cnn_filters=(64, 128),
        lstm_units=(64, 32),
        dropout_rate=0.5
    )
    
    model.summary()
    
    # Train
    save_dir = Path(f"./models/{method}_features")
    save_dir.mkdir(parents=True, exist_ok=True)
    
    trainer = ModelTrainer(model, model_dir=str(save_dir))
    
    # Compute class weights for imbalanced data
    class_weights = ModelEvaluator.compute_class_weights(y_train, int(np.max(y)) + 1)
    
    logger.info("\n" + "="*70)
    logger.info("Training Model")
    logger.info("="*70)
    
    history = trainer.train(
        X_train_r, y_train,
        X_val_r, y_val,
        epochs=30,
        batch_size=64,
        class_weights=class_weights
    )
    
    # Evaluate
    logger.info("\n" + "="*70)
    logger.info("Evaluating on Test Set")
    logger.info("="*70)
    
    test_metrics = trainer.evaluate(X_test_r, y_test)
    
    # Detailed metrics
    predictions = trainer.predict(X_test_r)
    detailed = ModelEvaluator.compute_metrics(
        y_test,
        predictions,
        int(np.max(y)) + 1
    )
    
    # Results
    logger.info("\n" + "="*70)
    logger.info("FINAL RESULTS")
    logger.info("="*70)
    logger.info(f"Selection Method: {method}")
    logger.info(f"Features Used: {X_train_r.shape[-1]} per second x {X_train_r.shape[1]} seconds")
    logger.info(f"\nTest Performance:")
    logger.info(f"  Accuracy:  {detailed['accuracy']:.4f}")
    logger.info(f"  Precision: {detailed['precision']:.4f}")
    logger.info(f"  Recall:    {detailed['recall']:.4f}")
    logger.info(f"  F1-Score:  {detailed['f1_score']:.4f}")
    
    logger.info(f"\nModel saved to: {save_dir}/best_model.keras")
    
    logger.info("\n" + "✅"*35)
    logger.info("TRAINING COMPLETE!")
    logger.info("✅"*35)
    
    logger.info("\nNext: Compare with baseline (all features)")
    logger.info("  1. Load baseline model trained on all 79 features")
    logger.info("  2. Compare accuracies")
    logger.info(f"  3. Calculate improvement: Feature reduction vs Accuracy drop")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
