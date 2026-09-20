"""
Train CNN-BiLSTM with Selected Features

Automatically loads selected features and trains model.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


import sys
import numpy as np
import pickle
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from projects.shared_libs import (
    CNNBiLSTMModel, ModelTrainer, ModelEvaluator, split_data
)
from load_dataset import reshape_for_cnn_bilstm


def main():
    logger.info("="*70)
    logger.info("Training CNN-BiLSTM with Selected Features")
    logger.info("="*70)
    
    # Load selection results
    possible_files = [
        Path("data/processed/cicddos2019_full_processed_feature_selection.pkl"),
        Path("data/processed/comprehensive_feature_selection.pkl"),
        Path("data/processed/advanced_feature_selection_25features.pkl")
    ]
    
    selection_file = None
    for file_path in possible_files:
        if file_path.exists():
            selection_file = file_path
            logger.info(f"Found: {selection_file}")
            break
    
    if not selection_file:
        logger.error("No feature selection results found!")
        logger.info("Please run: python run_multi_dataset_selection.py")
        return 1
    
    with open(selection_file, 'rb') as f:
        results = pickle.load(f)
    
    # Choose method
    print("\nWhich selection method to use?")
    for i, method in enumerate(results.keys(), 1):
        # Safely get number of features
        num_features = results[method].get('num_features', len(results[method].get('indices', [])))
        time_taken = results[method].get('time', 0)
        print(f"{i}. {method}: {num_features} features ({time_taken:.1f}s)")
    
    
    choice = int(input("\nEnter choice: ").strip()) - 1
    method = list(results.keys())[choice]
    selected_indices = results[method]['indices']
    
    logger.info(f"\nUsing {method}: {len(selected_indices)} features")
    
    # Load data
    data_file = Path('data/processed/cicddos2019_full_processed.npz')
    if not data_file.exists():
        logger.error(f"Processed data not found: {data_file}")
        logger.info("Please run: python load_dataset.py first")
        return 1
    
    data = np.load(data_file)
    X, y = data['X'], data['y']
    
    # Apply selection
    X_selected = X[:, selected_indices]
    logger.info(f"Reduced from {X.shape[1]} to {X_selected.shape[1]} features")
    
    # Split
    X_train, X_val, X_test, y_train, y_val, y_test = split_data(
        X_selected, y,
        train_ratio=0.7,
        val_ratio=0.15,
        test_ratio=0.15
    )
    
    logger.info(f"Train: {len(X_train):,}, Val: {len(X_val):,}, Test: {len(X_test):,}")
    
    # Reshape for CNN-BiLSTM
    timesteps = 10
    logger.info(f"\nReshaping for CNN-BiLSTM ({timesteps} timesteps)...")
    X_train_r = reshape_for_cnn_bilstm(X_train, timesteps)
    X_val_r = reshape_for_cnn_bilstm(X_val, timesteps)
    X_test_r = reshape_for_cnn_bilstm(X_test, timesteps)
    
    logger.info(f"Reshaped shape: {X_train_r.shape}")
    
    # Create model
    logger.info("\nCreating CNN-BiLSTM model...")
    model = CNNBiLSTMModel(
        input_shape=X_train_r.shape[1:],
        num_classes=len(np.unique(y)),
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
    class_weights = ModelEvaluator.compute_class_weights(y_train, len(np.unique(y)))
    
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
        len(np.unique(y))
    )
    
    # Results
    logger.info("\n" + "="*70)
    logger.info("FINAL RESULTS")
    logger.info("="*70)
    logger.info(f"Selection Method: {method}")
    logger.info(f"Features Used: {len(selected_indices)}/{X.shape[1]} ({len(selected_indices)/X.shape[1]*100:.1f}%)")
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
