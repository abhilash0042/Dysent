#!/usr/bin/env python3

import argparse
import sys
import json
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
from projects.shared_libs.attack_suite import apply_weight_attack


DATA_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "cicddos2019_100k_reshaped_t10.npz"
)

RESULT_PATH = (
    PROJECT_ROOT
    / "results"
    / "real_byzantine_fl.json"
)

NUM_NODES = 5
NUM_ROUNDS = 5
LOCAL_EPOCHS = 1
BATCH_SIZE = 64

# With 5 clients: 0 / 1 / 2 / 3 malicious => 0% / 20% / 40% / 60%
MALICIOUS_COUNTS = [0, 1, 2, 3]

ATTACKS = [
    "sign_flip",
    "gaussian",
    "scale",
    "random",
]

AGGREGATORS = [
    "fedavg",
    "fedavg_clip",
    "krum",
    "multi_krum",
    "median",
    "trimmed_mean",
    "bulyan",
    "trust_weighted",
]

SEEDS = [0, 1]


def load_data():
    print("\nLoading CIC-DDoS2019...")

    data = np.load(DATA_PATH)

    X_train = data["X_train"].astype(np.float32)
    y_train = data["y_train"]

    X_val = data["X_val"].astype(np.float32)
    y_val = data["y_val"]

    X_test = data["X_test"].astype(np.float32)
    y_test = data["y_test"]

    # 0 = Benign
    # 1-17 = DDoS/attack classes
    y_train = (y_train != 0).astype(np.float32)
    y_val = (y_val != 0).astype(np.float32)
    y_test = (y_test != 0).astype(np.float32)

    print(f"   Train: {X_train.shape}")
    print(f"   Val:   {X_val.shape}")
    print(f"   Test:  {X_test.shape}")

    print(
        f"   Train: benign={(y_train == 0).sum():,}, "
        f"attack={(y_train == 1).sum():,}"
    )

    print(
        f"   Test:  benign={(y_test == 0).sum():,}, "
        f"attack={(y_test == 1).sum():,}"
    )

    return (
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test,
    )


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


def clone_weights(weights):
    return [
        np.array(weight, copy=True)
        for weight in weights
    ]


def evaluate_model(model, X, y):
    probabilities = model.predict(
        X,
        batch_size=512,
        verbose=0,
    ).reshape(-1)

    predictions = (
        probabilities >= 0.5
    ).astype(int)

    tn, fp, fn, tp = confusion_matrix(
        y,
        predictions,
        labels=[0, 1],
    ).ravel()

    return {
        "accuracy": float(
            accuracy_score(y, predictions)
        ),
        "precision": float(
            precision_score(
                y,
                predictions,
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                y,
                predictions,
                zero_division=0,
            )
        ),
        "f1": float(
            f1_score(
                y,
                predictions,
                zero_division=0,
            )
        ),
        "pr_auc": float(
            average_precision_score(
                y,
                probabilities,
            )
        ),
        "fpr": float(
            fp / (fp + tn)
            if (fp + tn)
            else 0.0
        ),
        "mcc": float(
            matthews_corrcoef(
                y,
                predictions,
            )
        ),
        "balanced_accuracy": float(
            balanced_accuracy_score(
                y,
                predictions,
            )
        ),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def partition_data(X, y, seed):
    """
    Deterministically partition training data among clients.
    """

    rng = np.random.default_rng(seed)

    indices = np.arange(len(X))
    rng.shuffle(indices)

    splits = np.array_split(
        indices,
        NUM_NODES,
    )

    return [
        (
            X[idx],
            y[idx],
        )
        for idx in splits
    ]


CLIP_NORM = 1.0


def aggregate(
    updates,
    method,
    num_byzantine,
):
    """Aggregate update deltas. FedAvg stays unclipped; every other method clips first."""
    from projects.shared_libs.byzantine_defense import aggregate_updates

    trim_ratio = min(0.2, num_byzantine / max(NUM_NODES, 1))
    return aggregate_updates(
        updates,
        method,
        num_byzantine=num_byzantine,
        trim_ratio=trim_ratio,
        clip_norm=CLIP_NORM,
    )


def generate_client_updates(
    global_weights,
    node_data,
    malicious_count,
    attack,
    seed,
):
    """
    Train clients from the SAME global model and create
    model-update deltas.

    update = local_weights - global_weights

    Byzantine attacks are applied to the update delta,
    not to the complete model weights.
    """

    client_updates = []

    for client_index, (
        node_X,
        node_y,
    ) in enumerate(node_data):

        # Deterministic client-local training seed.
        client_seed = (
            seed
            + client_index
            + 1
        )

        tf.keras.utils.set_random_seed(
            client_seed
        )

        local_model = build_model()

        local_model.set_weights(
            clone_weights(global_weights)
        )

        local_model.fit(
            node_X,
            node_y,
            epochs=LOCAL_EPOCHS,
            batch_size=BATCH_SIZE,
            verbose=0,
            shuffle=True,
        )

        local_weights = local_model.get_weights()

        # Convert local model into an update delta.
        update = [
            local_weight - global_weight
            for local_weight, global_weight
            in zip(
                local_weights,
                global_weights,
            )
        ]

        # First N clients are Byzantine.
        if client_index < malicious_count and attack != "none":
            kwargs = {}
            if attack == "gaussian":
                kwargs["std"] = 0.1
            if attack == "scale":
                kwargs["factor"] = 10.0
            update = apply_weight_attack(
                update,
                attack,
                seed=seed + client_index + 1000,
                **kwargs,
            )

        client_updates.append(
            clone_weights(update)
        )

        del local_model

    return client_updates


def run_experiment(
    malicious_count,
    attack,
    aggregator,
    seed,
):
    """
    Run one deterministic FL trajectory.

    All aggregators start from exactly the same initial
    global model and use exactly the same client partition,
    malicious-client assignment and random-seed scheme.

    After each aggregation, the resulting global model
    naturally differs between aggregation algorithms.
    """

    # Reproducibility.
    tf.keras.backend.clear_session()
    np.random.seed(seed)
    tf.keras.utils.set_random_seed(seed)

    (
        X_train,
        y_train,
        X_val,
        y_val,
        X_test,
        y_test,
    ) = load_data()

    node_data = partition_data(
        X_train,
        y_train,
        seed,
    )

    # Common initial global model.
    tf.keras.utils.set_random_seed(seed)

    global_model = build_model()

    best_val_f1 = -1.0
    best_weights = None

    for round_num in range(
        1,
        NUM_ROUNDS + 1,
    ):

        global_weights = (
            global_model.get_weights()
        )

        # Generate deterministic client updates from
        # this round's global model.
        client_updates = generate_client_updates(
            global_weights=global_weights,
            node_data=node_data,
            malicious_count=malicious_count,
            attack=attack,
            seed=(
                seed
                + round_num * 10000
            ),
        )

        # Aggregate UPDATE DELTAS.
        aggregated_update = aggregate(
            client_updates,
            aggregator,
            malicious_count,
        )

        # Apply the aggregated update.
        new_global_weights = [
            global_weight + aggregated_update_layer
            for global_weight, aggregated_update_layer
            in zip(
                global_weights,
                aggregated_update,
            )
        ]

        global_model.set_weights(
            new_global_weights
        )

        val_metrics = evaluate_model(
            global_model,
            X_val,
            y_val,
        )

        print(
            f"         Round {round_num}: "
            f"F1={val_metrics['f1']:.4f}"
        )

        if (
            val_metrics["f1"]
            > best_val_f1
        ):
            best_val_f1 = (
                val_metrics["f1"]
            )

            best_weights = clone_weights(
                global_model.get_weights()
            )

    if best_weights is not None:
        global_model.set_weights(
            best_weights
        )

    return evaluate_model(
        global_model,
        X_test,
        y_test,
    )


def iter_experiments(malicious_counts, attacks, aggregators, seeds):
    for malicious_count in malicious_counts:
        malicious_pct = malicious_count / NUM_NODES * 100
        trial_attacks = ["none"] if malicious_count == 0 else attacks
        for attack in trial_attacks:
            for aggregator in aggregators:
                for seed in seeds:
                    yield malicious_count, malicious_pct, attack, aggregator, seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="One quick CNN run")
    parser.add_argument("--output", default=str(RESULT_PATH))
    args = parser.parse_args()

    malicious_counts = MALICIOUS_COUNTS
    attacks = ATTACKS
    aggregators = AGGREGATORS
    seeds = SEEDS
    if args.smoke:
        malicious_counts = [2]
        attacks = ["sign_flip"]
        aggregators = ["fedavg", "median", "multi_krum"]
        seeds = [0]

    print("=" * 70)
    print(" REAL CIC-DDOS2019 BYZANTINE FEDERATED LEARNING (CNN)")
    print("=" * 70)
    print(f"TensorFlow: {tf.__version__}")
    print(f"Clients:    {NUM_NODES}")
    print(f"Rounds:     {NUM_ROUNDS}")
    print(f"Model:      CNN-BiLSTM on {DATA_PATH.name}")

    jobs = list(iter_experiments(malicious_counts, attacks, aggregators, seeds))
    all_results = []

    for experiment_number, (malicious_count, malicious_pct, attack, aggregator, seed) in enumerate(jobs, start=1):

        print(
            f"\n[{experiment_number}/{len(jobs)}] "
            f"malicious={malicious_count}/{NUM_NODES} ({malicious_pct:.0f}%) | "
            f"attack={attack} | aggregation={aggregator} | seed={seed}"
        )

        from projects.shared_libs.byzantine_defense import AggregationUnsupported

        try:
            metrics = run_experiment(
                malicious_count=malicious_count,
                attack=attack,
                aggregator=aggregator,
                seed=seed,
            )
            row = {
                "malicious_clients": malicious_count,
                "malicious_pct": malicious_pct,
                "attack": attack,
                "aggregator": aggregator,
                "seed": seed,
                "status": "success",
                "model": "cnn_bilstm",
                **metrics,
            }
            all_results.append(row)
            print(
                f"   FINAL | F1={metrics['f1']:.4f} | Recall={metrics['recall']:.4f} | "
                f"FPR={metrics['fpr']:.4f} | MCC={metrics['mcc']:.4f}"
            )
        except AggregationUnsupported as e:
            all_results.append({
                "malicious_clients": malicious_count,
                "malicious_pct": malicious_pct,
                "attack": attack,
                "aggregator": aggregator,
                "seed": seed,
                "status": "unsupported",
                "model": "cnn_bilstm",
                "error": str(e),
            })
            print(f"   UNSUPPORTED | {e}")
        except Exception as e:
            all_results.append({
                "malicious_clients": malicious_count,
                "malicious_pct": malicious_pct,
                "attack": attack,
                "aggregator": aggregator,
                "seed": seed,
                "status": "failed",
                "model": "cnn_bilstm",
                "error": f"{type(e).__name__}: {e}",
            })
            print(f"   FAILED | {type(e).__name__}: {e}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(
            {
                "config": {
                    "clients": NUM_NODES,
                    "rounds": NUM_ROUNDS,
                    "local_epochs": LOCAL_EPOCHS,
                    "batch_size": BATCH_SIZE,
                    "clip_norm": CLIP_NORM,
                    "model": "CNN-BiLSTM",
                    "dataset": str(DATA_PATH),
                    "malicious_counts": malicious_counts,
                    "attacks": attacks,
                    "aggregators": aggregators,
                    "seeds": seeds,
                    "attack_definition": (
                        "Weight attacks poison client update deltas after local CNN training."
                    ),
                },
                "rows": all_results,
            },
            f,
            indent=2,
        )

    print("\n" + "=" * 70)
    print("CNN BYZANTINE FL EXPERIMENT COMPLETE")
    print("=" * 70)
    print(f"\nResults saved to:\n{out}")


if __name__ == "__main__":
    main()
