"""
Deep Diagnostic: Find exact root cause of MAML 0% accuracy
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from projects.shared_libs import CNNBiLSTMModel
from projects.shared_libs.meta_learning import FederatedMAML, create_few_shot_task
from sklearn.model_selection import train_test_split

print("="*70)
print("DEEP MAML DIAGNOSTIC - ROOT CAUSE ANALYSIS")
print("="*70)

# Generate test data
np.random.seed(42)
X = np.random.randn(1000, 10, 4)
y = np.random.randint(0, 10, 1000)  # 10 classes

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

print(f"\nOriginal Data:")
print(f"  Train shape: {X_train.shape}")
print(f"  Train labels: {np.unique(y_train)} ({len(np.unique(y_train))} classes)")

# Create few-shot task
print(f"\nCreating few-shot task (5-way, 10-shot)...")
task = create_few_shot_task(X_train, y_train, n_way=5, k_shot=10)
support_x, support_y = task['support']
query_x, query_y = task['query']

print(f"\nTask Details:")
print(f"  Support X: {support_x.shape}")
print(f"  Support y: {np.unique(support_y)} (min={support_y.min()}, max={support_y.max()})")
print(f"  Query X: {query_x.shape}")
print(f"  Query y: {np.unique(query_y)} (min={query_y.min()}, max={query_y.max()})")

# CRITICAL: Check label space
print(f"\n⚠️  CRITICAL FINDING:")
print(f"  Original dataset has {len(np.unique(y_train))} classes: {np.unique(y_train)}")
print(f"  Few-shot task has {len(np.unique(support_y))} classes: {np.unique(support_y)}")
print(f"  LABELS ARE REMAPPED TO 0-{len(np.unique(support_y))-1}")

# Build model
def build_model():
    return CNNBiLSTMModel(
        input_shape=(10, 4),
        num_classes=10,  # Original 10 classes
        cnn_filters=(32, 16),
        lstm_units=(16, 8)
    ).model

print(f"\n Testing with model expecting {10} classes...")

# Test 1: Model trained on 10 classes, tested on 5-class task
print(f"\n" + "="*70)
print("TEST 1: Model with 10 output classes, task with 0-4 labels")
print("="*70)

maml1 = FederatedMAML(model_builder=build_model, inner_lr=0.01, inner_steps=20)
maml1.meta_model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])
maml1.meta_model.fit(X_train[:500], y_train[:500], epochs=3, batch_size=32, verbose=0)

print(f"  Model output classes: {maml1.meta_model.output_shape[-1]}")
print(f"  Task labels range: 0-{support_y.max()}")
print(f"  ⚠️  This SHOULD work since 0-4 is within 0-9")

acc1, loss1 = maml1.few_shot_adapt(support_x, support_y, query_x, query_y, k_shot=10)
print(f"  Result: {acc1*100:.2f}% accuracy")

if acc1 == 0:
    print(f"  ❌ STILL 0%! Let's investigate predictions...")
    
    # Adapt model
    adapted = maml1.inner_loop(maml1.meta_model, support_x, support_y, steps=20)
    
    # Get predictions
    preds = adapted.predict(query_x[:10], verbose=0)
    pred_classes = np.argmax(preds, axis=1)
    
    print(f"\n  Sample predictions:")
    print(f"    Predicted classes: {pred_classes}")
    print(f"    True classes: {query_y[:10]}")
    print(f"    Prediction probabilities shape: {preds.shape}")
    print(f"    Max probability: {preds.max():.4f}")
    print(f"    Predictions are in range: {pred_classes.min()}-{pred_classes.max()}")

# Test 2: Correct solution - build model with matching classes
print(f"\n" + "="*70)
print("TEST 2: Model with 5 output classes (MATCHING task)")
print("="*70)

def build_model_5class():
    return CNNBiLSTMModel(
        input_shape=(10, 4),
        num_classes=5,  # Match few-shot task!
        cnn_filters=(32, 16),
        lstm_units=(16, 8)
    ).model

maml2 = FederatedMAML(model_builder=build_model_5class, inner_lr=0.01, inner_steps=20)
maml2.meta_model.compile(optimizer='adam', loss='sparse_categorical_crossentropy', metrics=['accuracy'])

# Pre-train on remapped labels
# Create training data with 5 classes
train_mask = np.isin(y_train, np.unique(support_y))
X_train_5class = X_train[train_mask]
y_train_5class = np.array([np.where(np.unique(support_y) == label)[0][0] for label in y_train[train_mask]])

print(f"  Training model with 5 classes on remapped data...")
print(f"  Training labels: {np.unique(y_train_5class)}")

maml2.meta_model.fit(X_train_5class[:200], y_train_5class[:200], epochs=3, batch_size=32, verbose=0)

acc2, loss2 = maml2.few_shot_adapt(support_x, support_y, query_x, query_y, k_shot=10)
print(f"  Result: {acc2*100:.2f}% accuracy")

print(f"\n" + "="*70)
print("ROOT CAUSE DIAGNOSIS")
print("="*70)

print(f"\nTest 1 (10 classes): {acc1*100:.2f}%")
print(f"Test 2 (5 classes):  {acc2*100:.2f}%")

if acc2 > acc1:
    print(f"\n✓ ROOT CAUSE FOUND:")
    print(f"  The model's output layer must MATCH the few-shot task's label space!")
    print(f"  Few-shot task remaps labels to 0-4, so model needs 5 output classes.")
    print(f"\n  SOLUTION: Build meta-model with n_way classes, not original dataset classes")
else:
    print(f"\n⚠️  Both tests failed - deeper issue exists")
    print(f"  Possible causes:")
    print(f"    - Insufficient adaptation steps")
    print(f"    - Poor pre-training")
    print(f"    - Data quality issues")
