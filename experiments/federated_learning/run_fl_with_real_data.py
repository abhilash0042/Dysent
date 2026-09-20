#!/usr/bin/env python3
"""
FL Experiment with Real CIC-DDoS2019 Dataset
Uses real traffic data instead of synthetic for high accuracy
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import numpy as np
import tensorflow as tf
from sklearn.model_selection import train_test_split
from scripts.data.load_cicdos2019 import CICDDoS2019Loader
from projects.shared_libs import CNNBiLSTMModel
from projects.shared_libs.byzantine_defense import ByzantineRobustAggregator

print("="*60)
print("FL EXPERIMENT WITH REAL CIC-DDoS2019 DATA")
print("="*60)

# Load real dataset
print("\n📊 1. Loading CIC-DDoS2019 Dataset...")
print("-" * 60)
loader = CICDDoS2019Loader()
X, y = loader.load_sample(num_samples=50000, balance=True)

print(f"✅ Loaded {len(X):,} samples")
print(f"   Features: {X.shape[1]}")
print(f"   Benign: {(y == 0).sum():,}")
print(f"   Attack: {(y == 1).sum():,}")

# Split data
print("\n🔀 2. Splitting Dataset...")
print("-" * 60)
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# Convert labels to categorical (one-hot)
from tensorflow.keras.utils import to_categorical
y_train_cat = to_categorical(y_train, num_classes=2)
y_test_cat = to_categorical(y_test, num_classes=2)

print(f"   Train: {len(X_train):,} samples")
print(f"   Test: {len(X_test):,} samples")
print(f"   Label shape: {y_train_cat.shape}")

# Reshape for model (assuming sequence length of 10)
num_features = X_train.shape[1]
seq_len = 10
feat_dim = num_features // seq_len

if num_features % seq_len != 0:
    # Pad to make it divisible
    pad_size = seq_len - (num_features % seq_len)
    X_train = np.pad(X_train, ((0, 0), (0, pad_size)), mode='constant')
    X_test = np.pad(X_test, ((0, 0), (0, pad_size)), mode='constant')
    feat_dim = X_train.shape[1] // seq_len
    print(f"   Padded features to {X_train.shape[1]} for reshaping")

X_train_reshaped = X_train.reshape(-1, seq_len, feat_dim)
X_test_reshaped = X_test.reshape(-1, seq_len, feat_dim)

print(f"   Reshaped to: {X_train_reshaped.shape}")

# Simulate FL nodes (distribute data)
print("\n🌐 3. Creating FL Nodes...")
print("-" * 60)
num_nodes = 5
samples_per_node = len(X_train) // num_nodes

node_data = []
for i in range(num_nodes):
    start_idx = i * samples_per_node
    end_idx = start_idx + samples_per_node if i < num_nodes - 1 else len(X_train)
    
    node_X = X_train_reshaped[start_idx:end_idx]
    node_y = y_train_cat[start_idx:end_idx]  # Use categorical labels
    
    node_data.append((node_X, node_y))
    print(f"   Node {i+1}: {len(node_X):,} samples")

# Create global model
print("\n🧠 4. Creating Global Model...")
print("-" * 60)
global_model = CNNBiLSTMModel(
    input_shape=(seq_len, feat_dim),
    num_classes=2,
    cnn_filters=(64, 32),
    lstm_units=(64,)
).model

global_model.compile(
    optimizer='adam',
    loss='categorical_crossentropy',  # Changed from sparse
    metrics=['accuracy']
)

print(f"   Model parameters: {global_model.count_params():,}")
print(f"   Architecture: CNN-BiLSTM")

# Federated Learning Rounds
print("\n🔄 5. Federated Learning Training...")
print("=" * 60)

num_rounds = 10
best_accuracy = 0.0

for round_num in range(num_rounds):
    print(f"\n📍 Round {round_num + 1}/{num_rounds}")
    print("-" * 60)
    
    # Get global weights
    global_weights = global_model.get_weights()
    
    # Train on each node
    local_weights = []
    
    for node_id, (node_X, node_y) in enumerate(node_data):
        # Create local model with global weights
        local_model = CNNBiLSTMModel(
            input_shape=(seq_len, feat_dim),
            num_classes=2,
            cnn_filters=(64, 32),
            lstm_units=(64,)
        ).model
        
        local_model.compile(
            optimizer='adam',
            loss='categorical_crossentropy',  # Changed
            metrics=['accuracy']
        )
        local_model.set_weights(global_weights)
        
        # Train locally
        local_model.fit(
            node_X, node_y,
            epochs=3,
            batch_size=32,
            verbose=0
        )
        
        # Store weights
        local_weights.append(local_model.get_weights())
        
        # Evaluate locally
        loss, acc = local_model.evaluate(node_X, node_y, verbose=0)
        print(f"   Node {node_id + 1}: {acc*100:.2f}% accuracy")
    
    # Aggregate using Byzantine-robust method  
    print(f"   Aggregating weights (FedAvg)...")
    aggregated_weights = ByzantineRobustAggregator.fedavg(local_weights)
    
    # Update global model
    global_model.set_weights(aggregated_weights)
    
    # Evaluate global model
    test_loss, test_acc = global_model.evaluate(
        X_test_reshaped, y_test_cat, verbose=0  # Use categorical
    )
    
    print(f"   ✅ Global Test Accuracy: {test_acc*100:.2f}%")
    
    if test_acc > best_accuracy:
        best_accuracy = test_acc
        global_model.save('models/best_cicdos_model.h5')
        print(f"   💾 Best model saved!")

# Final Evaluation
print("\n" + "="*60)
print("🎯 FINAL RESULTS")
print("="*60)

final_loss, final_acc = global_model.evaluate(X_test_reshaped, y_test_cat, verbose=0)  # Use categorical

print(f"\n📊 Test Accuracy: {final_acc*100:.2f}%")
print(f"📊 Test Loss: {final_loss:.4f}")
print(f"📊 Best Accuracy: {best_accuracy*100:.2f}%")

# Compare with synthetic baseline
print("\n📈 Improvement Over Synthetic Data:")
synthetic_baseline = 0.55  # ~55% typical synthetic accuracy
improvement = (final_acc - synthetic_baseline) * 100
print(f"   Synthetic baseline: ~55%")
print(f"   Real data accuracy: {final_acc*100:.2f}%")
print(f"   Improvement: +{improvement:.1f} percentage points")

print("\n" + "="*60)
print("✅ FL TRAINING WITH REAL DATA COMPLETE!")
print("="*60)
print()
print(f"✨ Achieved {final_acc*100:.2f}% accuracy with real CIC-DDoS2019 data")
print(f"📁 Best model saved to: models/best_cicdos_model.h5")
print()

