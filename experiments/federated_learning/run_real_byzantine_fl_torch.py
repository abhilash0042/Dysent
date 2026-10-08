#!/usr/bin/env python3
"""Byzantine FL on real CIC-DDoS2019 using PyTorch + CUDA (RTX GPU).

Same attack suite and aggregators as the Keras runner; training runs on GPU.
Fastest path on Windows where TensorFlow cannot use the GPU.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    matthews_corrcoef,
    precision_score,
    recall_score,
)
from torch.utils.data import DataLoader, TensorDataset

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

from projects.shared_libs.attack_suite import apply_weight_attack
from projects.shared_libs.byzantine_defense import (
    AggregationUnsupported,
    aggregate_updates,
    update_l2,
)

DATA_PATH = PROJECT_ROOT / "data" / "processed" / "cicddos2019_100k_reshaped_t10.npz"
RESULT_PATH = PROJECT_ROOT / "results" / "real_byzantine_fl_torch.json"

NUM_NODES = 5
NUM_ROUNDS = 5
LOCAL_EPOCHS = 1
BATCH_SIZE = 64
CLIP_NORM = 1.0
LR = 1e-3

MALICIOUS_COUNTS = [0, 1, 2, 3]
ATTACKS = ["sign_flip", "gaussian", "scale", "random"]
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


class CNNBiLSTMTorch(nn.Module):
    """Matches projects/shared_libs/cnn_bilstm_model.py (binary CNN-BiLSTM)."""

    def __init__(
        self,
        timesteps: int = 10,
        features: int = 8,
        cnn_filters=(64, 32),
        kernel_size: int = 3,
        lstm_units=(64,),
        dropout: float = 0.3,
    ):
        super().__init__()
        convs = []
        in_ch = features
        for filters in cnn_filters:
            convs.append(nn.Conv1d(in_ch, filters, kernel_size, padding=kernel_size // 2))
            convs.append(nn.BatchNorm1d(filters))
            convs.append(nn.ReLU())
            in_ch = filters
        self.cnn = nn.Sequential(*convs)
        self.pool = nn.MaxPool1d(2)
        self.lstm = nn.LSTM(
            input_size=in_ch,
            hidden_size=lstm_units[0],
            num_layers=1,
            batch_first=True,
            bidirectional=True,
            dropout=0.0,
        )
        self.bn_lstm = nn.BatchNorm1d(lstm_units[0] * 2)
        self.dropout = nn.Dropout(dropout)
        self.fc = nn.Linear(lstm_units[0] * 2, 1)

    def forward(self, x):
        # x: (B, T, F) -> Conv1d wants (B, F, T)
        x = x.transpose(1, 2)
        x = self.cnn(x)
        x = self.pool(x)
        x = x.transpose(1, 2)
        out, _ = self.lstm(x)
        h = out[:, -1, :]
        h = self.bn_lstm(h)
        h = self.dropout(h)
        return torch.sigmoid(self.fc(h)).squeeze(-1)


def get_device() -> torch.device:
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def set_seed(seed: int):
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_data():
    print(f"\nLoading CIC-DDoS2019 from {DATA_PATH}")
    data = np.load(DATA_PATH)
    X_train = data["X_train"].astype(np.float32)
    y_train = (data["y_train"] != 0).astype(np.float32)
    X_val = data["X_val"].astype(np.float32)
    y_val = (data["y_val"] != 0).astype(np.float32)
    X_test = data["X_test"].astype(np.float32)
    y_test = (data["y_test"] != 0).astype(np.float32)
    print(f"  Train {X_train.shape}  Val {X_val.shape}  Test {X_test.shape}")
    return X_train, y_train, X_val, y_val, X_test, y_test


def partition_data(X, y, seed):
    rng = np.random.default_rng(seed)
    indices = np.arange(len(X))
    rng.shuffle(indices)
    return [(X[idx], y[idx]) for idx in np.array_split(indices, NUM_NODES)]


def state_to_numpy(model: nn.Module):
    return [t.detach().cpu().numpy().copy() for t in model.state_dict().values()]


def numpy_to_state(model: nn.Module, arrays):
    state = model.state_dict()
    keys = list(state.keys())
    if len(keys) != len(arrays):
        raise ValueError(f"weight count mismatch {len(keys)} vs {len(arrays)}")
    new_state = {
        key: torch.tensor(arr, dtype=state[key].dtype)
        for key, arr in zip(keys, arrays)
    }
    model.load_state_dict(new_state)


def clone_arrays(arrays):
    return [np.array(a, copy=True) for a in arrays]


def train_local(model, X, y, device, epochs, batch_size, seed):
    set_seed(seed)
    model.train()
    ds = TensorDataset(torch.from_numpy(X), torch.from_numpy(y))
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True, drop_last=False)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    loss_fn = nn.BCELoss()
    for _ in range(epochs):
        for xb, yb in loader:
            xb = xb.to(device)
            yb = yb.to(device)
            opt.zero_grad(set_to_none=True)
            pred = model(xb)
            loss = loss_fn(pred, yb)
            loss.backward()
            opt.step()


@torch.no_grad()
def evaluate_model(model, X, y, device):
    model.eval()
    loader = DataLoader(
        TensorDataset(torch.from_numpy(X), torch.from_numpy(y)),
        batch_size=512,
        shuffle=False,
    )
    probs = []
    for xb, _ in loader:
        probs.append(model(xb.to(device)).cpu().numpy())
    probabilities = np.concatenate(probs).reshape(-1)
    predictions = (probabilities >= 0.5).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, predictions, labels=[0, 1]).ravel()
    return {
        "accuracy": float(accuracy_score(y, predictions)),
        "precision": float(precision_score(y, predictions, zero_division=0)),
        "recall": float(recall_score(y, predictions, zero_division=0)),
        "f1": float(f1_score(y, predictions, zero_division=0)),
        "pr_auc": float(average_precision_score(y, probabilities)),
        "fpr": float(fp / (fp + tn) if (fp + tn) else 0.0),
        "mcc": float(matthews_corrcoef(y, predictions)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predictions)),
        "tn": int(tn),
        "fp": int(fp),
        "fn": int(fn),
        "tp": int(tp),
    }


def aggregate(updates, method, num_byzantine, clip_norm):
    trim_ratio = min(0.2, num_byzantine / max(NUM_NODES, 1))
    return aggregate_updates(
        updates,
        method,
        num_byzantine=num_byzantine,
        trim_ratio=trim_ratio,
        clip_norm=clip_norm,
    )


def estimate_clip_norm(global_weights, node_data, device, seed):
    """Probe one short local step to pick a clip bound that fits real CNN deltas."""
    norms = []
    for client_index, (node_X, node_y) in enumerate(node_data[: min(3, len(node_data))]):
        local = CNNBiLSTMTorch().to(device)
        numpy_to_state(local, global_weights)
        # small subset for speed
        take = min(512, len(node_X))
        train_local(
            local,
            node_X[:take],
            node_y[:take],
            device,
            epochs=1,
            batch_size=BATCH_SIZE,
            seed=seed + client_index,
        )
        delta = [lw - gw for lw, gw in zip(state_to_numpy(local), global_weights)]
        norms.append(update_l2(delta))
        del local
    if not norms:
        return CLIP_NORM
    return max(CLIP_NORM, float(np.median(norms)) * 3.0)


def generate_client_updates(global_weights, node_data, malicious_count, attack, seed, device):
    client_updates = []
    for client_index, (node_X, node_y) in enumerate(node_data):
        local = CNNBiLSTMTorch().to(device)
        numpy_to_state(local, global_weights)
        train_local(
            local,
            node_X,
            node_y,
            device,
            LOCAL_EPOCHS,
            BATCH_SIZE,
            seed + client_index + 1,
        )
        local_weights = state_to_numpy(local)
        update = [lw - gw for lw, gw in zip(local_weights, global_weights)]
        if client_index < malicious_count and attack != "none":
            kwargs = {}
            if attack == "gaussian":
                kwargs["std"] = 0.1
            if attack == "scale":
                kwargs["factor"] = 10.0
            update = apply_weight_attack(
                update, attack, seed=seed + client_index + 1000, **kwargs
            )
        client_updates.append(clone_arrays(update))
        del local
        if device.type == "cuda":
            torch.cuda.empty_cache()
    return client_updates


def run_experiment(malicious_count, attack, aggregator, seed, device):
    set_seed(seed)
    X_train, y_train, X_val, y_val, X_test, y_test = load_data()
    node_data = partition_data(X_train, y_train, seed)

    global_model = CNNBiLSTMTorch().to(device)
    set_seed(seed)
    # re-init so all aggregators share the same starting point for this seed
    global_model.apply(
        lambda m: m.reset_parameters() if hasattr(m, "reset_parameters") else None
    )
    set_seed(seed)

    best_val_f1 = -1.0
    best_weights = None
    clip_norm = estimate_clip_norm(state_to_numpy(global_model), node_data, device, seed)
    print(f"         clip_norm={clip_norm:.4f} device={device}")

    for round_num in range(1, NUM_ROUNDS + 1):
        global_weights = state_to_numpy(global_model)
        client_updates = generate_client_updates(
            global_weights,
            node_data,
            malicious_count,
            attack,
            seed + round_num * 10000,
            device,
        )
        aggregated = aggregate(client_updates, aggregator, malicious_count, clip_norm)
        new_weights = [gw + du for gw, du in zip(global_weights, aggregated)]
        numpy_to_state(global_model, new_weights)

        val_metrics = evaluate_model(global_model, X_val, y_val, device)
        print(f"         Round {round_num}: F1={val_metrics['f1']:.4f}")
        if val_metrics["f1"] > best_val_f1:
            best_val_f1 = val_metrics["f1"]
            best_weights = clone_arrays(state_to_numpy(global_model))

    if best_weights is not None:
        numpy_to_state(global_model, best_weights)
    return evaluate_model(global_model, X_test, y_test, device)


def iter_jobs(malicious_counts, attacks, aggregators, seeds):
    for malicious_count in malicious_counts:
        pct = malicious_count / NUM_NODES * 100
        trial_attacks = ["none"] if malicious_count == 0 else attacks
        for attack in trial_attacks:
            for aggregator in aggregators:
                for seed in seeds:
                    yield malicious_count, pct, attack, aggregator, seed


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true", help="Fast GPU check: 3 aggregators, 1 seed")
    parser.add_argument("--output", default=str(RESULT_PATH))
    args = parser.parse_args()

    device = get_device()
    print("=" * 70)
    print(" REAL CIC-DDOS2019 BYZANTINE FL (PyTorch GPU)")
    print("=" * 70)
    print(f"Torch:   {torch.__version__}")
    print(f"CUDA:    {torch.cuda.is_available()} ({torch.version.cuda})")
    print(f"Device:  {device}")
    if device.type == "cuda":
        print(f"GPU:     {torch.cuda.get_device_name(0)}")
    print(f"Clients: {NUM_NODES}  Rounds: {NUM_ROUNDS}")

    malicious_counts = MALICIOUS_COUNTS
    attacks = ATTACKS
    aggregators = AGGREGATORS
    seeds = SEEDS
    if args.smoke:
        malicious_counts = [2]
        attacks = ["sign_flip"]
        aggregators = ["fedavg", "median", "multi_krum"]
        seeds = [0]

    jobs = list(iter_jobs(malicious_counts, attacks, aggregators, seeds))
    rows = []

    for i, (mc, pct, attack, aggregator, seed) in enumerate(jobs, start=1):
        print(
            f"\n[{i}/{len(jobs)}] malicious={mc}/{NUM_NODES} ({pct:.0f}%) | "
            f"attack={attack} | aggregation={aggregator} | seed={seed}"
        )
        try:
            metrics = run_experiment(mc, attack, aggregator, seed, device)
            row = {
                "malicious_clients": mc,
                "malicious_pct": pct,
                "attack": attack,
                "aggregator": aggregator,
                "seed": seed,
                "status": "success",
                "model": "cnn_bilstm_torch",
                "device": str(device),
                **metrics,
            }
            rows.append(row)
            print(
                f"   FINAL | F1={metrics['f1']:.4f} | Recall={metrics['recall']:.4f} | "
                f"FPR={metrics['fpr']:.4f} | MCC={metrics['mcc']:.4f}"
            )
        except AggregationUnsupported as e:
            rows.append({
                "malicious_clients": mc,
                "malicious_pct": pct,
                "attack": attack,
                "aggregator": aggregator,
                "seed": seed,
                "status": "unsupported",
                "model": "cnn_bilstm_torch",
                "device": str(device),
                "error": str(e),
            })
            print(f"   UNSUPPORTED | {e}")
        except Exception as e:
            rows.append({
                "malicious_clients": mc,
                "malicious_pct": pct,
                "attack": attack,
                "aggregator": aggregator,
                "seed": seed,
                "status": "failed",
                "model": "cnn_bilstm_torch",
                "device": str(device),
                "error": f"{type(e).__name__}: {e}",
            })
            print(f"   FAILED | {type(e).__name__}: {e}")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(
            {
                "config": {
                    "framework": "pytorch",
                    "device": str(device),
                    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                    "clients": NUM_NODES,
                    "rounds": NUM_ROUNDS,
                    "local_epochs": LOCAL_EPOCHS,
                    "batch_size": BATCH_SIZE,
                    "clip_norm": CLIP_NORM,
                    "dataset": str(DATA_PATH),
                    "malicious_counts": malicious_counts,
                    "attacks": attacks,
                    "aggregators": aggregators,
                    "seeds": seeds,
                },
                "rows": rows,
            },
            f,
            indent=2,
        )
    print("\n" + "=" * 70)
    print("CNN BYZANTINE FL (PyTorch) COMPLETE")
    print("=" * 70)
    print(f"\nResults saved to:\n{out}")


if __name__ == "__main__":
    main()
