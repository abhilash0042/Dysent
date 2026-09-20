# Models Directory

Trained model files and checkpoints.

## Structure

```
models/
├── best_model.keras          # Final trained model
├── pretrained/
│   ├── source_cicddos.keras  # Pre-trained source model
│   └── meta_model.keras      # Meta-learned model
└── README.md
```

## Loading Models

```python
from tensorflow import keras

# Load best model
model = keras.models.load_model('models/best_model.keras')

# Make predictions
predictions = model.predict(X_test)
```

## Model Performance

| Model             | Accuracy | Dataset          |
| ----------------- | -------- | ---------------- |
| CNN-BiLSTM        | 97.79%   | 30GB CICDDoS2019 |
| Transformer       | 98.07%   | 30GB CICDDoS2019 |
| Transfer Learning | 99.63%   | NSL-KDD          |

## Training Your Own Models

```bash
# Train CNN-BiLSTM on 30GB dataset
python tests/test_cnn_bilstm_30gb_mixed.py

# Train Transformer
python tests/test_transformer_30gb_mixed.py
```

Models are automatically saved to this directory after training.
