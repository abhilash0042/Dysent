"""
Train FL-DDoS Model on 50K Samples from Each CIC-DDoS2019 File
Comprehensive coverage: 18 files × 50K = 900K total samples
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd
import logging
from tensorflow import keras
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from projects.shared_libs import CNNBiLSTMModel

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class ComprehensiveDataLoader:
    """Load 50K samples from each of the 18 CIC-DDoS2019 files"""
    
    def __init__(self, dataset_root=r"D:\Cicddos Full Dataset\archive"):
        self.dataset_root = Path(dataset_root)
        self.samples_per_file = 50000
        
    def load_all_files(self):
        """Load 50K from each CSV file"""
        
        logger.info("="*70)
        logger.info("COMPREHENSIVE CIC-DDoS2019 TRAINING")
        logger.info("="*70)
        logger.info(f"Dataset: {self.dataset_root}")
        logger.info(f"Strategy: 50,000 samples from EACH file")
        logger.info("")
        
        # Find all CSV files
        csv_files = list(self.dataset_root.rglob("*.csv"))
        logger.info(f"Found {len(csv_files)} CSV files")
        
        all_X = []
        all_y = []
        
        for i, csv_file in enumerate(csv_files, 1):
            logger.info(f"\n[{i}/{len(csv_files)}] Processing {csv_file.name}...")
            
            try:
                # Read 50K rows from this file
                df = pd.read_csv(csv_file, nrows=self.samples_per_file, low_memory=False)
                
                logger.info(f"  Loaded {len(df)} rows")
                
                # Identify label column
                label_col = None
                for col in ['Label', 'label', ' Label']:
                    if col in df.columns:
                        label_col = col
                        break
                
                if label_col is None:
                    logger.warning(f"  No label column found, skipping...")
                    continue
                
                # Extract features and labels
                X = df.drop(columns=[label_col])
                y = df[label_col]
                
                # Select only numeric features
                numeric_cols = X.select_dtypes(include=[np.number]).columns
                X = X[numeric_cols]
                
                # Handle infinities and NaN
                X = X.replace([np.inf, -np.inf], np.nan)
                X = X.fillna(0)
                
                # Binary labels (0=benign, 1=attack)
                y_binary = (y != 'BENIGN').astype(int)
                
                # Standardize to exactly 82 features (max common dimension)
                X_values = X.values
                if X_values.shape[1] < 82:
                    # Pad with zeros
                    pad_size = 82 - X_values.shape[1]
                    X_values = np.pad(X_values, ((0, 0), (0, pad_size)), mode='constant')
                elif X_values.shape[1] > 82:
                    # Truncate
                    X_values = X_values[:, :82]
                
                logger.info(f"  Features: {len(numeric_cols)} → standardized to 82")
                logger.info(f"  Benign: {(y_binary == 0).sum()}, Attack: {(y_binary == 1).sum()}")
                
                all_X.append(X_values)
                all_y.append(y_binary.values)
                
            except Exception as e:
                logger.error(f"  Error processing {csv_file.name}: {e}")
                continue
        
        # Combine all data
        logger.info("\n" + "="*70)
        logger.info("COMBINING ALL DATA")
        logger.info("="*70)
        
        X_combined = np.vstack(all_X)
        y_combined = np.hstack(all_y)
        
        logger.info(f"Total samples: {len(X_combined):,}")
        logger.info(f"Total features: {X_combined.shape[1]}")
        logger.info(f"Benign: {(y_combined == 0).sum():,}")
        logger.info(f"Attack: {(y_combined == 1).sum():,}")
        
        return X_combined, y_combined


def prepare_for_cnn_bilstm(X, y, num_features=40, timesteps=10):
    """Prepare data for CNN-BiLSTM model"""
    
    logger.info("\nPreparing data for CNN-BiLSTM...")
    
    # Ensure exactly num_features
    if X.shape[1] < num_features:
        pad_size = num_features - X.shape[1]
        X = np.pad(X, ((0, 0), (0, pad_size)), mode='constant')
    elif X.shape[1] > num_features:
        X = X[:, :num_features]
    
    logger.info(f"Features adjusted to: {num_features}")
    
    # Reshape to (samples, timesteps, features_per_timestep)
    # For CNN-BiLSTM with (10, 40) input, repeat features across timesteps
    num_samples = len(X)
    X_single = X.reshape(num_samples, 1, num_features)
    X_reshaped = np.repeat(X_single, timesteps, axis=1)
    
    logger.info(f"Reshaped to: {X_reshaped.shape}")
    
    return X_reshaped.astype(np.float32), y


def train_model(X_train, y_train, X_test, y_test):
    """Train CNN-BiLSTM model"""
    
    logger.info("\n" + "="*70)
    logger.info("MODEL TRAINING")
    logger.info("="*70)
    
    # Create model
    model_wrapper = CNNBiLSTMModel(
        input_shape=(10, 40),
        num_classes=2,
        cnn_filters=(64, 32),
        lstm_units=(64,)
    )
    model = model_wrapper.get_model()
    
    logger.info(f"Model created: {model.count_params():,} parameters")
    
    # Compile (using binary_crossentropy for binary classification)
    model.compile(
        optimizer='adam',
        loss='binary_crossentropy',
        metrics=['accuracy']
    )
    
    # Early stopping
    early_stop = keras.callbacks.EarlyStopping(
        monitor='val_accuracy',
        patience=3,
        restore_best_weights=True
    )
    
    # Model checkpoint
    checkpoint = keras.callbacks.ModelCheckpoint(
        'models/cicdos_50k_per_file_best.h5',
        monitor='val_accuracy',
        save_best_only=True,
        verbose=1
    )
    
    # Train
    logger.info("\nTraining started...")
    logger.info(f"Training samples: {len(X_train):,}")
    logger.info(f"Validation samples: {len(X_test):,}")
    
    history = model.fit(
        X_train, y_train,
        validation_data=(X_test, y_test),
        epochs=20,
        batch_size=128,
        callbacks=[early_stop, checkpoint],
        verbose=1
    )
    
    return model, history


def main():
    """Main training pipeline"""
    
    # Step 1: Load data from all 18 files
    loader = ComprehensiveDataLoader()
    X_raw, y_raw = loader.load_all_files()
    
    # Step 2: Prepare for model
    X, y = prepare_for_cnn_bilstm(X_raw, y_raw)
    
    # Step 3: Train/test split
    logger.info("\nSplitting data...")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    logger.info(f"Train: {len(X_train):,} samples")
    logger.info(f"Test: {len(X_test):,} samples")
    
    # Step 4: Train model
    model, history = train_model(X_train, y_train, X_test, y_test)
    
    # Step 5: Final evaluation
    logger.info("\n" + "="*70)
    logger.info("FINAL EVALUATION")
    logger.info("="*70)
    
    test_loss, test_acc = model.evaluate(X_test, y_test, verbose=0)
    
    logger.info(f"Test Loss: {test_loss:.4f}")
    logger.info(f"Test Accuracy: {test_acc:.4f} ({test_acc*100:.2f}%)")
    
    # Save final model
    model.save('models/cicdos_50k_per_file_final.h5')
    logger.info("\nModel saved: models/cicdos_50k_per_file_final.h5")
    
    logger.info("\n" + "="*70)
    logger.info("✅ TRAINING COMPLETE!")
    logger.info("="*70)
    logger.info(f"Final Accuracy: {test_acc*100:.2f}%")
    logger.info(f"Total samples trained: {len(X_raw):,}")
    logger.info(f"Files processed: 18")
    logger.info(f"Samples per file: 50,000")
    logger.info("="*70)


if __name__ == "__main__":
    main()
