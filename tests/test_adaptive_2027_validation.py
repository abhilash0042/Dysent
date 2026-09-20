"""
Validation Test: Smart-Adaptive 2027 Attacks
Tests the system's ability to adapt to next-gen adversarial threats.
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import tensorflow as tf
import time
import json
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

from scripts.data.generate_adaptive_2027_attacks import Adaptive2027AttackGenerator
from scripts.data.generate_modern_2026_attacks import Modern2026AttackGenerator
from scripts.data.load_cicddos import reshape_for_cnn_bilstm
from projects.shared_libs import CNNBiLSTMModel
from projects.shared_libs.adaptive_transfer_learning import AdaptiveTransferLearning

# Numpy encoder for JSON serialization
class NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super(NumpyEncoder, self).default(obj)

def main():
    print("="*70)
    print("SMART-ADAPTIVE 2027 ATTACK VALIDATION")
    print("="*70)
    
    # 1. Generate Data
    print("\n1. Generating Datasets...")
    
    # Historical Data (for source model training)
    print("  Generating Historical Data (2026)...")
    gen_hist = Modern2026AttackGenerator(seed=42)
    X_hist_raw, y_hist = gen_hist.generate_modern_dataset(10000, 40)
    X_hist = reshape_for_cnn_bilstm(X_hist_raw, 10)
    
    # New Smart-Adaptive Data (2027)
    print("  Generating Smart-Adaptive Data (2027)...")
    gen_2027 = Adaptive2027AttackGenerator(seed=99) # Different seed
    X_2027_raw, y_2027 = gen_2027.generate_adaptive_dataset(15000, 40)
    X_2027 = reshape_for_cnn_bilstm(X_2027_raw, 10)
    
    # Split 2027 data
    X_train_2027, X_test_2027, y_train_2027, y_test_2027 = train_test_split(
        X_2027, y_2027, test_size=0.2, random_state=42, stratify=y_2027
    )
    
    print(f"  Historical samples: {len(X_hist)}")
    print(f"  2027 Training samples: {len(X_train_2027)}")
    print(f"  2027 Test samples: {len(X_test_2027)}")
    
    # 2. Train Source Model
    print("\n2. Training Source Model (Historical)...")
    num_classes_hist = len(np.unique(y_hist))
    
    source_model = CNNBiLSTMModel(
        input_shape=X_hist.shape[1:],
        num_classes=num_classes_hist,
        cnn_filters=(64, 32),
        lstm_units=(32, 16)
    ).model
    
    source_model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
    source_model.fit(X_hist, y_hist, epochs=5, batch_size=128, verbose=0)
    print("  Source model trained.")
    
    # 3. Adaptive Transfer Learning
    print("\n3. Adapting to Smart-Adaptive 2027 Attacks...")
    atl = AdaptiveTransferLearning(source_model)
    
    # Detect similarity
    print("  Detecting Similarity...")
    similarity = atl.detect_similarity(
        (X_hist[:2000], y_hist[:2000]),
        (X_train_2027[:2000], y_train_2027[:2000])
    )
    print(f"  Similarity Score: {similarity:.2%}")
    
    # Create adaptive model
    num_classes_2027 = len(np.unique(y_2027))
    target_model = atl.create_adaptive_model(
        num_target_classes=num_classes_2027,
        similarity_score=similarity,
        strategy='auto' # Should pick Discriminative
    )
    
    # Compile
    target_model.compile(
        optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001),
        loss='sparse_categorical_crossentropy',
        metrics=['accuracy']
    )
    
    # Train
    print("  Training Adaptive Model...")
    start_time = time.time()
    
    early_stop = tf.keras.callbacks.EarlyStopping(
        monitor='val_accuracy', 
        patience=5, 
        restore_best_weights=True
    )
    
    history = target_model.fit(
        X_train_2027, y_train_2027,
        epochs=15,
        batch_size=64,
        validation_split=0.2,
        callbacks=[early_stop],
        verbose=0
    )
    
    train_time = time.time() - start_time
    print(f"  Training complete in {train_time:.2f}s")
    
    # 4. Evaluation
    print("\n4. Final Evaluation...")
    loss, accuracy = target_model.evaluate(X_test_2027, y_test_2027, verbose=0)
    
    print(f"  Test Loss: {loss:.4f}")
    print(f"  Test Accuracy: {accuracy*100:.2f}%")
    
    # Detailed report
    y_pred = target_model.predict(X_test_2027, verbose=0)
    y_pred_classes = np.argmax(y_pred, axis=1)
    
    target_names = gen_2027.attack_types
    print("\nClassification Report:")
    print(classification_report(y_test_2027, y_pred_classes, target_names=target_names))
    
    # Save results
    results = {
        'timestamp': datetime.now().isoformat(),
        'dataset': 'Smart-Adaptive 2027',
        'accuracy': accuracy,
        'loss': loss,
        'similarity': similarity,
        'training_time': train_time,
        'strategy_used': atl.freeze_strategy if hasattr(atl, 'freeze_strategy') else 'Auto'
    }
    
    filename = f"results/modern_2026_validation/adaptive_2027_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(results, f, indent=2, cls=NumpyEncoder)
        
    print(f"\nResults saved to {filename}")

if __name__ == "__main__":
    main()
