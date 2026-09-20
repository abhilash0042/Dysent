"""
Quick test to verify MAML is working and diagnose the 0% accuracy issue
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
from projects.shared_libs import CNNBiLSTMModel
from projects.shared_libs.meta_learning import FederatedMAML, create_few_shot_task
from sklearn.model_selection import train_test_split

# Generate simple test data
np.random.seed(42)
X = np.random.randn(1000, 10, 4)
y = np.random.randint(0, 5, 1000)

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

def build_meta_model():
    return CNNBiLSTMModel(
        input_shape=(10, 4),
        num_classes=5,
        cnn_filters=(32, 16),
        lstm_units=(16, 8)
    ).model

print("="*70)
print("MAML DIAGNOSIS TEST")
print("="*70)

# Test 1: Untrained meta-model (current situation)
print("\nTest 1: Untrained Meta-Model (current implementation)")
print("-"*70)
maml_untrained = FederatedMAML(model_builder=build_meta_model, inner_lr=0.01, inner_steps=5)

task = create_few_shot_task(X_train, y_train, n_way=5, k_shot=10)
support_x, support_y = task['support']
query_x, query_y = task['query']

acc_untrained, loss_untrained = maml_untrained.few_shot_adapt(
    support_x, support_y, query_x, query_y, k_shot=10
)

print(f"Result: Accuracy={acc_untrained*100:.2f}%, Loss={loss_untrained:.4f}")
print(f"Expected: ~0-20% (random/poor performance)")

# Test 2: Pre-trained meta-model (what we should do)
print("\nTest 2: Pre-trained Meta-Model (proper implementation)")
print("-"*70)
maml_trained = FederatedMAML(model_builder=build_meta_model, inner_lr=0.01, inner_steps=10)

# Pre-train the meta-model on some data
print("Pre-training meta-model...")
maml_trained.meta_model.compile(
    optimizer='adam',
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)
maml_trained.meta_model.fit(
    X_train[:500], y_train[:500],
    epochs=5,
    batch_size=32,
    verbose=0
)

# Now do few-shot adaptation
acc_trained, loss_trained = maml_trained.few_shot_adapt(
    support_x, support_y, query_x, query_y, k_shot=10
)

print(f"Result: Accuracy={acc_trained*100:.2f}%, Loss={loss_trained:.4f}")
print(f"Expected: >50% (should be much better)")

print("\n" + "="*70)
print("DIAGNOSIS COMPLETE")
print("="*70)
print(f"\nConclusion:")
print(f"  Untrained MAML: {acc_untrained*100:.2f}%")
print(f"  Pre-trained MAML: {acc_trained*100:.2f}%")
print(f"  Improvement: +{(acc_trained-acc_untrained)*100:.2f}%")

if acc_untrained < 0.2 and acc_trained > 0.4:
    print("\n✓ DIAGNOSIS CONFIRMED: Meta-model needs pre-training!")
    print("  Solution: Add meta-training or pre-training step before few-shot adaptation")
else:
    print("\n✗ Unexpected results - needs further investigation")
