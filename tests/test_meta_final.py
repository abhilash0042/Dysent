"""
Meta-Learning test with few-shot adaptation
Target: 70%+ accuracy on binary classification
"""
import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from projects.shared_libs import CNNBiLSTMModel
from scripts.data.generate_modern_2026_attacks import Modern2026AttackGenerator
from scripts.data.load_cicddos import reshape_for_cnn_bilstm
from sklearn.model_selection import train_test_split

print("\n" + "="*60)
print("Meta-Learning Layer Test")
print("="*60)

# Generate synthetic data
generator = Modern2026AttackGenerator(seed=42)
X, y = generator.generate_modern_dataset(num_samples=15000, num_features=40)

# Reshape for CNN-BiLSTM
timesteps = 10
X_reshaped = reshape_for_cnn_bilstm(X, timesteps)

X_train, X_test, y_train, y_test = train_test_split(
    X_reshaped, y, test_size=0.2, random_state=42, stratify=y
)

# Convert to binary (benign vs attack)
y_train_bin = np.where(y_train == 0, 0, 1).astype(np.int64)
y_test_bin = np.where(y_test == 0, 0, 1).astype(np.int64)

print(f"\nDataset: Train {X_train.shape}, Test {X_test.shape}")
print(f"Classes: {np.sum(y_train_bin == 0):,} benign, {np.sum(y_train_bin == 1):,} attack")

# Build model
print("\nBuilding CNN-BiLSTM...")
model = CNNBiLSTMModel(
    input_shape=X_train.shape[1:],
    num_classes=2,
    cnn_filters=(32, 16),
    lstm_units=(16, 8)
).model

model.compile(
    optimizer='adam',
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

# Base training
print("Training base model (5 epochs)...")
history = model.fit(
    X_train[:6000], y_train_bin[:6000],
    epochs=5,
    batch_size=128,
    validation_data=(X_test, y_test_bin),
    verbose=1
)

train_acc = history.history['accuracy'][-1]
val_acc = history.history['val_accuracy'][-1]

# Few-shot adaptation (40 samples total)
print("\nFew-shot fine-tuning (20 benign + 20 attack)...")
benign_idx = np.where(y_train_bin == 0)[0][:20]
attack_idx = np.where(y_train_bin == 1)[0][:20]
few_shot_idx = np.concatenate([benign_idx, attack_idx])

model.fit(
    X_train[few_shot_idx], 
    y_train_bin[few_shot_idx], 
    epochs=10, 
    batch_size=40, 
    verbose=0
)

# Evaluate
final_loss, final_acc = model.evaluate(X_test, y_test_bin, verbose=0)

print(f"\n{'='*60}")
print("Results")
print(f"{'='*60}")
print(f"Base training:    {train_acc*100:.2f}%")
print(f"Base validation:  {val_acc*100:.2f}%")
print(f"Few-shot adapted: {final_acc*100:.2f}%")
print(f"Loss: {final_loss:.4f}")

if final_acc >= 0.7:
    print(f"\n✓ Target achieved: {final_acc*100:.2f}% (>= 70%)")
else:
    print(f"\n⚠ Below target: {final_acc*100:.2f}% (target: 70%)")

# TODO: save model if accuracy is good enough
print(f"\nFinal accuracy for analysis: {final_acc*100:.2f}%")
