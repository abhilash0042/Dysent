"""
Dataset already processed - Quick load and train script

Use this script if you've already run load_dataset.py successfully.
It loads the preprocessed data and trains a CNN-BiLSTM model.
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

from projects.shared_libs import CNNBiLSTMModel, ModelTrainer, ModelEvaluator
from scripts.data.load_cicddos import load_temporal_splits

# Check for processed data
PROCESSED_DIR = Path("./data/processed")

def list_available_datasets():
    """List processed datasets"""
    logger.info("="*70)
    logger.info("Available Processed Datasets")
    logger.info("="*70)
    
    processed_files = list(PROCESSED_DIR.glob("*_reshaped_*.npz"))
    
    if not processed_files:
        logger.error("No reshaped datasets found!")
        logger.info("\nPlease run: python load_dataset.py")
        logger.info("And complete the reshaping step.")
        return None
    
    for i, file in enumerate(processed_files, 1):
        logger.info(f"{i}. {file.name}")
    
    return processed_files


def load_and_train(dataset_file=None):
    """Load real 1-second windows and train the model."""
    logger.info("="*70)
    logger.info("Loading leak-free temporal windows")
    logger.info("="*70)
    
    data = load_temporal_splits()
    X_train = data['X_train']
    y_train = data['y_train']
    X_val = data['X_val']
    y_val = data['y_val']
    X_test = data['X_test']
    y_test = data['y_test']
    
    logger.info(f"Train: {X_train.shape}, Val: {X_val.shape}, Test: {X_test.shape}")
    logger.info(f"Input shape: {X_train.shape[1:]}")
    logger.info(f"Number of classes: {len(np.unique(y_train))}")
    
    # Create model
    logger.info("\n" + "="*70)
    logger.info("Creating CNN-BiLSTM Model")
    logger.info("="*70)
    
    model = CNNBiLSTMModel(
        input_shape=X_train.shape[1:],  # (timesteps, features)
        num_classes=int(np.max(y_train)) + 1,
        cnn_filters=(64, 128),
        lstm_units=(64, 32),
        dropout_rate=0.5
    )
    
    model.summary()
    
    # Train
    logger.info("\n" + "="*70)
    logger.info("Training Model")
    logger.info("="*70)
    
    trainer = ModelTrainer(model, model_dir="./models")
    
    # Compute class weights for imbalanced data
    class_weights = ModelEvaluator.compute_class_weights(
        y_train,
        int(np.max(y_train)) + 1
    )
    
    history = trainer.train(
        X_train, y_train,
        X_val, y_val,
        epochs=30,
        batch_size=64,
        class_weights=class_weights
    )
    
    # Evaluate
    logger.info("\n" + "="*70)
    logger.info("Evaluating Model")
    logger.info("="*70)
    
    test_metrics = trainer.evaluate(X_test, y_test)
    
    # Detailed metrics
    predictions = trainer.predict(X_test)
    detailed = ModelEvaluator.compute_metrics(
        y_test,
        predictions,
        int(np.max(y_train)) + 1
    )
    
    logger.info("\n" + "="*70)
    logger.info("FINAL RESULTS")
    logger.info("="*70)
    logger.info(f"Accuracy: {detailed['accuracy']:.4f}")
    logger.info(f"Precision: {detailed['precision']:.4f}")
    logger.info(f"Recall: {detailed['recall']:.4f}")
    logger.info(f"F1-Score: {detailed['f1_score']:.4f}")
    
    return model, history, detailed


def main():
    logger.info("\n" + "🎯"*35)
    logger.info("Quick Train - DDoS Detection Model")
    logger.info("🎯"*35 + "\n")
    
    model, history, metrics = load_and_train()
    
    logger.info("\n" + "✅"*35)
    logger.info("TRAINING COMPLETE!")
    logger.info("✅"*35)
    logger.info("\nModel saved to: ./models/best_model.keras")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
