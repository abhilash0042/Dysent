"""
Comprehensive Comparison: 3 Adaptive Transfer Learning Strategies
Tests on Modern 2026 Attack Data
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import time
import tensorflow as tf
from sklearn.model_selection import train_test_split

from projects.shared_libs import CNNBiLSTMModel
from projects.shared_libs.adaptive_transfer_learning import AdaptiveTransferLearning
from scripts.data.generate_modern_2026_attacks import Modern2026AttackGenerator
from scripts.data.load_cicddos import reshape_for_cnn_bilstm

print("="*70)
print("ADAPTIVE TRANSFER LEARNING: 3-STRATEGY COMPARISON")
print("Modern 2026 Attack Data")
print("="*70)

# Set seeds for reproducibility
np.random.seed(42)
tf.random.set_seed(42)

# Generate modern 2026 data
print("\n📊 Generating Modern 2026 Attack Data...")
generator = Modern2026AttackGenerator(seed=42)
X_raw, y_raw = generator.generate_modern_dataset(num_samples=15000, num_features=40)

# Reshape and split
timesteps = 10
X = reshape_for_cnn_bilstm(X_raw, timesteps)
X_train, X_test, y_train, y_test = train_test_split(X, y_raw, test_size=0.2, random_state=42, stratify=y_raw)

print(f"  Train: {X_train.shape}, Test: {X_test.shape}")
print(f"  Classes: {len(np.unique(y_raw))}")

# Create and train source model (historical attacks)
print("\n🏗️  Training Source Model (Historical Attacks)...")
source_model = CNNBiLSTMModel(
    input_shape=X_train.shape[1:],
    num_classes=len(np.unique(y_raw)),
    cnn_filters=(64, 32),
    lstm_units=(32, 16)
).model

source_model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
source_model.fit(X_train[:6000], y_train[:6000], epochs=5, batch_size=128, verbose=0)

print(f"  Source model trained: {source_model.count_params():,} params")

# Create adaptive transfer learner
atl = AdaptiveTransferLearning(source_model)

# Detect similarity
print("\n🔍 Detecting Domain Similarity...")
similarity = atl.detect_similarity(
    (X_train[:2000], y_train[:2000]),
    (X_train[6000:8000], y_train[6000:8000])
)

results = {}

# ============================================================================
# STRATEGY 1: FROZEN (Reusable Attacks)
# ============================================================================
print("\n" + "="*70)
print("STRATEGY 1: FROZEN (Reusable Attacks)")
print("="*70)

start_time = time.time()

# Create frozen model
frozen_model = atl.create_adaptive_model(
    num_target_classes=len(np.unique(y_raw)),
    similarity_score=0.85,  # Force frozen strategy
    strategy='frozen'
)

frozen_model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.0005),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# Train
frozen_model.fit(
    X_train[6000:], y_train[6000:],
    epochs=8,
    batch_size=64,
    validation_split=0.2,
    verbose=0
)

# Evaluate
frozen_results = frozen_model.evaluate(X_test, y_test, verbose=0)
frozen_time = time.time() - start_time

results['frozen'] = {
    'accuracy': frozen_results[1],
    'loss': frozen_results[0],
    'time': frozen_time,
    'trainable_params': atl.get_trainable_params()
}

print(f"✅ Accuracy: {frozen_results[1]*100:.2f}%")
print(f"⏱️  Time: {frozen_time:.2f}s")
print(f"🔧 Trainable Params: {results['frozen']['trainable_params']:,}")

# ============================================================================
# STRATEGY 2: PROGRESSIVE (Evolved Attacks)
# ============================================================================
print("\n" + "="*70)
print("STRATEGY 2: PROGRESSIVE UNFREEZING (Evolved Attacks)")
print("="*70)

start_time = time.time()

# Recreate ATL instance
atl2 = AdaptiveTransferLearning(source_model)

# Create progressive model
progressive_model = atl2.create_adaptive_model(
    num_target_classes=len(np.unique(y_raw)),
    similarity_score=0.65,  # Force progressive strategy
    strategy='progressive'
)

progressive_model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.0003),
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# Train with progressive unfreezing
total_epochs = 12
for epoch in range(total_epochs):
    # Unfreeze layers progressively
    atl2.progressive_unfreeze(epoch, total_epochs)
    
    # Train for 1 epoch
    progressive_model.fit(
        X_train[6000:], y_train[6000:],
        epochs=1,
        batch_size=64,
        validation_split=0.2,
        verbose=0
    )

# Evaluate
progressive_results = progressive_model.evaluate(X_test, y_test, verbose=0)
progressive_time = time.time() - start_time

results['progressive'] = {
    'accuracy': progressive_results[1],
    'loss': progressive_results[0],
    'time': progressive_time,
    'trainable_params': atl2.get_trainable_params()
}

print(f"✅ Accuracy: {progressive_results[1]*100:.2f}%")
print(f"⏱️  Time: {progressive_time:.2f}s")
print(f"🔧 Trainable Params: {results['progressive']['trainable_params']:,}")

# ============================================================================
# STRATEGY 3: DISCRIMINATIVE (Novel Modern Attacks)
# ============================================================================
print("\n" + "="*70)
print("STRATEGY 3: DISCRIMINATIVE (Novel Modern Attacks)")
print("="*70)

start_time = time.time()

# Recreate ATL instance
atl3 = AdaptiveTransferLearning(source_model)

# Create discriminative model
discriminative_model = atl3.create_adaptive_model(
    num_target_classes=len(np.unique(y_raw)),
    similarity_score=0.35,  # Force discriminative strategy
    strategy='discriminative'
)

discriminative_model.compile(
    optimizer=tf.keras.optimizers.Adam(learning_rate=0.0001),  # Lower LR for all layers
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# Train with callbacks
early_stop = tf.keras.callbacks.EarlyStopping(
    monitor='val_accuracy',
    patience=4,
    restore_best_weights=True
)

discriminative_model.fit(
    X_train[6000:], y_train[6000:],
    epochs=15,
    batch_size=64,
    validation_split=0.2,
    callbacks=[early_stop],
    verbose=0
)

# Evaluate
discriminative_results = discriminative_model.evaluate(X_test, y_test, verbose=0)
discriminative_time = time.time() - start_time

results['discriminative'] = {
    'accuracy': discriminative_results[1],
    'loss': discriminative_results[0],
    'time': discriminative_time,
    'trainable_params': atl3.get_trainable_params()
}

print(f"✅ Accuracy: {discriminative_results[1]*100:.2f}%")
print(f"⏱️  Time: {discriminative_time:.2f}s")
print(f"🔧 Trainable Params: {results['discriminative']['trainable_params']:,}")

# ============================================================================
# COMPARISON SUMMARY
# ============================================================================
print("\n" + "="*70)
print("📊 COMPARISON SUMMARY")
print("="*70)

print(f"\n{'Strategy':<20} {'Accuracy':<12} {'Time (s)':<12} {'Trainable Params':<20}")
print("-"*70)

for strategy, metrics in results.items():
    print(f"{strategy.upper():<20} {metrics['accuracy']*100:>6.2f}%     {metrics['time']:>8.2f}s    {metrics['trainable_params']:>15,}")

# Find best strategy
best_acc = max(results.items(), key=lambda x: x[1]['accuracy'])
best_time = min(results.items(), key=lambda x: x[1]['time'])

print("\n" + "="*70)
print("🏆 WINNERS")
print("="*70)
print(f"Best Accuracy: {best_acc[0].upper()} ({best_acc[1]['accuracy']*100:.2f}%)")
print(f"Fastest: {best_time[0].upper()} ({best_time[1]['time']:.2f}s)")

# Recommendation
if results['discriminative']['accuracy'] > 0.85:
    recommendation = "DISCRIMINATIVE"
    reason = "Highest accuracy for novel modern attacks"
elif results['progressive']['accuracy'] > 0.82:
    recommendation = "PROGRESSIVE"
    reason = "Best balance of accuracy and speed"
else:
    recommendation = "FROZEN"
    reason = "Fast and efficient for similar attacks"

print(f"\n💡 RECOMMENDATION: {recommendation}")
print(f"   Reason: {reason}")

print("\n" + "="*70)
print("✅ COMPARISON COMPLETE!")
print("="*70)
