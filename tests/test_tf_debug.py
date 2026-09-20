"""
Minimal TensorFlow Debug Test
Find exact cause of SparseSoftmax error
"""

import numpy as np
import tensorflow as tf
from tensorflow import keras

print("="*70)
print("TENSORFLOW DEBUG TEST")
print("="*70)
print(f"TensorFlow version: {tf.__version__}")
print(f"NumPy version: {np.__version__}")

# Test 1: Minimal binary classification
print("\nTest 1: Minimal Binary Classification")
print("-"*70)

X = np.random.randn(100, 10, 4).astype(np.float32)
y = np.random.randint(0, 2, 100).astype(np.int64)

print(f"X shape: {X.shape}, dtype: {X.dtype}")
print(f"y shape: {y.shape}, dtype: {y.dtype}")
print(f"y unique: {np.unique(y)}")

model = keras.Sequential([
    keras.layers.Input(shape=(10, 4)),
    keras.layers.Conv1D(16, 3, activation='relu'),
    keras.layers.Flatten(),
    keras.layers.Dense(2)
])

model.compile(
    optimizer='adam',
    loss='sparse_categorical_crossentropy',
    metrics=['accuracy']
)

print("Model compiled successfully")

try:
    history = model.fit(X, y, epochs=1, batch_size=32, verbose=0)
    print(f"✓ Test 1 PASSED - Training worked!")
    print(f"  Accuracy: {history.history['accuracy'][0]*100:.2f}%")
except Exception as e:
    print(f"✗ Test 1 FAILED")
    print(f"  Error: {str(e)}")
    print(f"  Type: {type(e).__name__}")

# Test 2: With explicit int32 conversion
print("\nTest 2: Explicit int32 Labels")
print("-"*70)

y_int32 = y.astype(np.int32)
print(f"y dtype: {y_int32.dtype}")

try:
    history = model.fit(X, y_int32, epochs=1, batch_size=32, verbose=0)
    print(f"✓ Test 2 PASSED")
    print(f"  Accuracy: {history.history['accuracy'][0]*100:.2f}%")
except Exception as e:
    print(f"✗ Test 2 FAILED")
    print(f"  Error: {str(e)[:100]}")

# Test 3: With from_logits=True
print("\nTest 3: Using from_logits=True")
print("-"*70)

model3 = keras.Sequential([
    keras.layers.Input(shape=(10, 4)),
    keras.layers.Conv1D(16, 3, activation='relu'),
    keras.layers.Flatten(),
    keras.layers.Dense(2)  # No softmax activation
])

model3.compile(
    optimizer='adam',
    loss=keras.losses.SparseCategoricalCrossentropy(from_logits=True),
    metrics=['accuracy']
)

try:
    history = model3.fit(X, y, epochs=1, batch_size=32, verbose=0)
    print(f"✓ Test 3 PASSED")
    print(f"  Accuracy: {history.history['accuracy'][0]*100:.2f}%")
except Exception as e:
    print(f"✗ Test 3 FAILED")
    print(f"  Error: {str(e)[:100]}")

# Test 4: Check label format edge cases
print("\nTest 4: Label Format Checks")
print("-"*70)

# Check if labels have issues
print(f"Min label: {y.min()}")
print(f"Max label: {y.max()}")
print(f"Label range valid: {y.min() >= 0 and y.max() < 2}")
print(f"Has NaN: {np.isnan(y).any()}")
print(f"Has Inf: {np.isinf(y).any()}")

print("\n" + "="*70)
print("DIAGNOSIS COMPLETE")
print("="*70)
