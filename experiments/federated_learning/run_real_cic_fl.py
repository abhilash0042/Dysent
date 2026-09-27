#!/usr/bin/env python3

import sys
from pathlib import Path

import numpy as np
import tensorflow as tf
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    average_precision_score,
    confusion_matrix,
    matthews_corrcoef,
    balanced_accuracy_score,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from projects.shared_libs import CNNBiLSTMModel
from projects.shared_libs.byzantine_defense import ByzantineRobustAggregator


DATA_PATH = PROJECT_ROOT / "data" / "processed" / "cicddos2019_100k_reshaped_t10.npz"

NUM_NODES = 5
NUM_ROUNDS = 5
LOCAL_EPOCHS = 1
BATCH_SIZE = 64


def load_data():
    print("\n📊 Loading processed CIC-DDoS2019 sequence data...")
    print(f"   {DATA_PATH}")

    data = np.load(DATA_PATH)

    X_train = data["X_train"].astype(np.float32)
    y_train = data["y_train"]

    X_val = data["X_val"].astype(np.float32)
    y_val = data["y_val"]

    X_test = data["X_test"].astype(np.float32)
    y_test = data["y_test"]

    # ---------------------------------------------------------
    # Convert CIC-DDoS2019 multiclass labels to binary labels
    #
    # CIC-DDoS2019 encoding:
    # 0   = Benign
    # 1-17 = Attack classes
    #
    # Binary encoding:
    # 0 = Benign
    # 1 = Any attack
    # ---------------------------------------------------------

    y_train = (y_train != 0).astype(np.float32)
    y_val = (y_val != 0).astype(np.float32)
    y_test = (y_test != 0).astype(np.float32)

    print(f"   Train: {X_train.shape}")
    print(f"   Val:   {X_val.shape}")
    print(f"   Test:  {X_test.shape}")

    print(f"   Train benign: {(y_train == 0).sum():,}")
    print(f"   Train attack: {(y_train == 1).sum():,}")
    print(f"   Val benign:   {(y_val == 0).sum():,}")
    print(f"   Val attack:   {(y_val == 1).sum():,}")
    print(f"   Test benign:  {(y_test == 0).sum():,}")
    print(f"   Test attack:  {(y_test == 1).sum():,}")

    return X_train, y_train, X_val, y_val, X_test, y_test


def build_model():
    wrapper = CNNBiLSTMModel(
        input_shape=(10, 8),
        num_classes=2,
        cnn_filters=(64, 32),
        lstm_units=(64,),
    )

    model = wrapper.model

    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=[
            "accuracy",
            tf.keras.metrics.Precision(name="precision"),
            tf.keras.metrics.Recall(name="recall"),
            tf.keras.metrics.AUC(name="auc"),
        ],
    )

    return model


def evaluate_model(model, X, y):
    probabilities = model.predict(
        X,
        batch_size=512,
        verbose=0
    ).reshape(-1)

    predictions = (probabilities >= 0.5).astype(int)

    tn, fp, fn, tp = confusion_matrix(
        y,
        predictions,
        labels=[0, 1]
    ).ravel()

    metrics = {
        "accuracy": accuracy_score(y, predictions),
        "precision": precision_score(
            y,
            predictions,
            zero_division=0
        ),
        "recall": recall_score(
            y,
            predictions,
            zero_division=0
        ),
        "f1": f1_score(
            y,
            predictions,
            zero_division=0
        ),
        "pr_auc": average_precision_score(
            y,
            probabilities
        ),
        "fpr": fp / (fp + tn) if (fp + tn) else 0.0,
        "mcc": matthews_corrcoef(
            y,
            predictions
        ),
        "balanced_accuracy": balanced_accuracy_score(
            y,
            predictions
        ),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }

    return metrics


def partition_data(X, y):
    indices = np.arange(len(X))

    # Deterministic shuffle so clients don't simply receive
    # contiguous blocks from the original dataset.
    rng = np.random.default_rng(42)
    rng.shuffle(indices)

    X = X[indices]
    y = y[indices]

    splits = np.array_split(
        np.arange(len(X)),
        NUM_NODES
    )

    node_data = []

    for node_id, idx in enumerate(
        splits,
        start=1
    ):
        node_X = X[idx]
        node_y = y[idx]

        node_data.append(
            (node_X, node_y)
        )

        print(
            f"   Node {node_id}: "
            f"{len(node_X):,} samples "
            f"(benign={(node_y == 0).sum():,}, "
            f"attack={(node_y == 1).sum():,})"
        )

    return node_data


def main():

    print("=" * 70)
    print(" REAL CIC-DDOS2019 FEDERATED CNN-BILSTM EXPERIMENT")
    print("=" * 70)

    print(f"\nTensorFlow:  {tf.__version__}")
    print(f"Nodes:       {NUM_NODES}")
    print(f"Rounds:      {NUM_ROUNDS}")
    print(f"Local epochs:{LOCAL_EPOCHS}")

    # ---------------------------------------------------------
    # 1. Load real processed data
    # ---------------------------------------------------------

    X_train, y_train, X_val, y_val, X_test, y_test = load_data()

    # ---------------------------------------------------------
    # 2. Partition training data across FL nodes
    # ---------------------------------------------------------

    print("\n🌐 Partitioning training data across FL nodes...")
    node_data = partition_data(
        X_train,
        y_train
    )

    # ---------------------------------------------------------
    # 3. Build global model
    # ---------------------------------------------------------

    print("\n🧠 Building CNN-BiLSTM global model...")

    global_model = build_model()

    print(
        f"   Input shape:  "
        f"{global_model.input_shape}"
    )

    print(
        f"   Output shape: "
        f"{global_model.output_shape}"
    )

    print(
        f"   Parameters:   "
        f"{global_model.count_params():,}"
    )

    # ---------------------------------------------------------
    # 4. Federated training
    # ---------------------------------------------------------

    print("\n🔄 Starting Federated Learning...")
    print("=" * 70)

    best_f1 = -1.0
    best_weights = None

    for round_num in range(
        1,
        NUM_ROUNDS + 1
    ):

        print(
            f"\n📍 FL ROUND "
            f"{round_num}/{NUM_ROUNDS}"
        )

        print("-" * 70)

        global_weights = global_model.get_weights()
        local_weights = []

        # -----------------------------------------------------
        # Local training
        # -----------------------------------------------------

        for node_id, (
            node_X,
            node_y
        ) in enumerate(
            node_data,
            start=1
        ):

            local_model = build_model()

            local_model.set_weights(
                global_weights
            )

            history = local_model.fit(
                node_X,
                node_y,
                epochs=LOCAL_EPOCHS,
                batch_size=BATCH_SIZE,
                verbose=0,
            )

            local_weights.append(
                local_model.get_weights()
            )

            local_loss = (
                history.history["loss"][-1]
            )

            local_acc = (
                history.history["accuracy"][-1]
            )

            print(
                f"   Node {node_id}: "
                f"loss={local_loss:.4f}, "
                f"accuracy={local_acc:.4f}"
            )

            del local_model

        # -----------------------------------------------------
        # FedAvg aggregation
        # -----------------------------------------------------

        aggregated_weights = (
            ByzantineRobustAggregator.fedavg(
                local_weights
            )
        )

        global_model.set_weights(
            aggregated_weights
        )

        # -----------------------------------------------------
        # Validation
        # -----------------------------------------------------

        val_metrics = evaluate_model(
            global_model,
            X_val,
            y_val,
        )

        print("\n   Validation:")

        print(
            f"      Accuracy:          "
            f"{val_metrics['accuracy']:.4f}"
        )

        print(
            f"      Precision:         "
            f"{val_metrics['precision']:.4f}"
        )

        print(
            f"      Recall:            "
            f"{val_metrics['recall']:.4f}"
        )

        print(
            f"      F1:                "
            f"{val_metrics['f1']:.4f}"
        )

        print(
            f"      PR-AUC:            "
            f"{val_metrics['pr_auc']:.4f}"
        )

        print(
            f"      FPR:               "
            f"{val_metrics['fpr']:.4f}"
        )

        print(
            f"      MCC:               "
            f"{val_metrics['mcc']:.4f}"
        )

        print(
            f"      Balanced Accuracy: "
            f"{val_metrics['balanced_accuracy']:.4f}"
        )

        # -----------------------------------------------------
        # Save best validation model
        # -----------------------------------------------------

        if val_metrics["f1"] > best_f1:
            best_f1 = val_metrics["f1"]
            best_weights = global_model.get_weights()

    # ---------------------------------------------------------
    # 5. Restore best validation model
    # ---------------------------------------------------------

    if best_weights is not None:
        global_model.set_weights(
            best_weights
        )

    # ---------------------------------------------------------
    # 6. Final evaluation — untouched test set
    # ---------------------------------------------------------

    print(
        "\n" + "=" * 70
    )

    print(
        " FINAL HELD-OUT TEST EVALUATION"
    )

    print(
        "=" * 70
    )

    test_metrics = evaluate_model(
        global_model,
        X_test,
        y_test,
    )

    print(
        f"\nAccuracy:           "
        f"{test_metrics['accuracy']:.4f}"
    )

    print(
        f"Precision:          "
        f"{test_metrics['precision']:.4f}"
    )

    print(
        f"Recall:             "
        f"{test_metrics['recall']:.4f}"
    )

    print(
        f"F1:                 "
        f"{test_metrics['f1']:.4f}"
    )

    print(
        f"PR-AUC:             "
        f"{test_metrics['pr_auc']:.4f}"
    )

    print(
        f"FPR:                "
        f"{test_metrics['fpr']:.4f}"
    )

    print(
        f"MCC:                "
        f"{test_metrics['mcc']:.4f}"
    )

    print(
        f"Balanced Accuracy:  "
        f"{test_metrics['balanced_accuracy']:.4f}"
    )

    print("\nConfusion Matrix:")

    print(
        f"   TN={test_metrics['tn']}  "
        f"FP={test_metrics['fp']}"
    )

    print(
        f"   FN={test_metrics['fn']}  "
        f"TP={test_metrics['tp']}"
    )

    # ---------------------------------------------------------
    # 7. Save model
    # ---------------------------------------------------------

    model_dir = PROJECT_ROOT / "models"
    model_dir.mkdir(
        exist_ok=True
    )

    model_path = (
        model_dir /
        "real_cicddos_fl.keras"
    )

    global_model.save(
        model_path
    )

    print(
        f"\n💾 Model saved to:"
    )

    print(
        f"   {model_path}"
    )

    print(
        "\n" + "=" * 70
    )

    print(
        " ✅ REAL-DATA FEDERATED LEARNING COMPLETE"
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()