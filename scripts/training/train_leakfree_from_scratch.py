"""
Train CNN-BiLSTM from scratch on every leak-free CIC-DDoS2019 flow.

The 431,371-row matrix is the full processed set on this machine.
Timestamp and source IP were removed before it was saved, so each row is
one flow, not one second in a 10-step window. The input shape is (1, 40).
Repeating a row to look like 10 timesteps is the bug this script refuses.
"""

from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from projects.shared_libs.cnn_bilstm_model import CNNBiLSTMModel, ModelEvaluator, ModelTrainer

DATA_PATH = PROJECT_ROOT / "data" / "processed" / "cicddos2019_leakfree_processed.npz"
EXTRACTOR_PATH = PROJECT_ROOT / "data" / "processed" / "cicddos2019_leakfree_feature_extractor.pkl"
SELECTION_PATH = PROJECT_ROOT / "data" / "processed" / "cicddos2019_leakfree_feature_selection.pkl"
MODEL_DIR = PROJECT_ROOT / "models" / "cnn_bilstm_leakfree_from_scratch"
REPORT_PATH = PROJECT_ROOT / "results" / "leakfree_from_scratch_metrics.json"


def load_flows():
    stored = np.load(DATA_PATH)
    X = stored["X"].astype(np.float32)
    y = stored["y"].astype(np.int64)
    with open(EXTRACTOR_PATH, "rb") as handle:
        extractor = pickle.load(handle)
    with open(SELECTION_PATH, "rb") as handle:
        selection = pickle.load(handle)

    names = list(extractor["feature_names"])
    banned = {"unnamed: 0", "class", "label", "inbound"}
    leaked = [name for name in names if name.strip().lower() in banned]
    if leaked:
        raise RuntimeError(f"Leak columns are still in the matrix: {leaked}")

    # The npz was standardized on all 431,371 rows. Undo that, then fit a
    # new scaler on the training split only.
    original = extractor["scaler"].inverse_transform(X).astype(np.float32)
    indices = np.asarray(selection["ensemble"]["indices"], dtype=int)
    selected_names = [names[i] for i in indices]
    return original[:, indices], y, selected_names


def main():
    X, y, feature_names = load_flows()
    print(f"Flows: {len(y):,}  features: {X.shape[1]}  classes: {len(np.unique(y))}")

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, random_state=42, stratify=y
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, random_state=42, stratify=y_temp
    )

    scaler = StandardScaler()
    X_train = scaler.fit_transform(X_train).astype(np.float32)
    X_val = scaler.transform(X_val).astype(np.float32)
    X_test = scaler.transform(X_test).astype(np.float32)

    # One real flow per sample. The time axis is 1 because these rows have no clock.
    X_train = X_train.reshape(-1, 1, X_train.shape[1])
    X_val = X_val.reshape(-1, 1, X_val.shape[1])
    X_test = X_test.reshape(-1, 1, X_test.shape[1])
    print(f"Train {X_train.shape}  Val {X_val.shape}  Test {X_test.shape}")

    model = CNNBiLSTMModel(
        input_shape=X_train.shape[1:],
        num_classes=int(y.max()) + 1,
        cnn_filters=(64, 128),
        lstm_units=(64, 32),
        dropout_rate=0.5,
    )
    trainer = ModelTrainer(model, model_dir=str(MODEL_DIR))
    class_weights = ModelEvaluator.compute_class_weights(y_train, int(y.max()) + 1)
    trainer.train(
        X_train,
        y_train,
        X_val,
        y_val,
        epochs=12,
        batch_size=512,
        class_weights=class_weights,
    )

    probabilities = trainer.predict(X_test, batch_size=512)
    metrics = ModelEvaluator.compute_metrics(y_test, probabilities, int(y.max()) + 1)
    clean_metrics = {}
    for key, value in metrics.items():
        clean_metrics[key] = value if isinstance(value, list) else float(value)
    report = {
        "flows": int(len(y)),
        "train": int(len(y_train)),
        "val": int(len(y_val)),
        "test": int(len(y_test)),
        "input_shape": list(X_train.shape[1:]),
        "features": feature_names,
        "note": "Each sample is one flow. Timestamp was not in the npz, so no 10-step window was invented.",
        "metrics": clean_metrics,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["metrics"], indent=2))
    print(f"Saved model under {MODEL_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
