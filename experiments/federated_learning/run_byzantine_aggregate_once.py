#!/usr/bin/env python3
"""Train CNN clients ONCE, then compare many aggregators on the SAME updates.

This is the fast path:
  1) local train all clients for one FL round (or a few rounds from a shared start)
  2) optionally poison malicious client deltas
  3) run FedAvg / Krum / Median / Multi-Krum / ... on identical updates
  4) evaluate each aggregated model

No re-training per aggregator.
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
from projects.shared_libs.byzantine_defense import AggregationUnsupported, aggregate_updates, update_l2

# Reuse model + helpers from the torch FL runner
from experiments.federated_learning.run_real_byzantine_fl_torch import (  # noqa: E402
    BATCH_SIZE,
    CNNBiLSTMTorch,
    DATA_PATH,
    LR,
    NUM_NODES,
    evaluate_model,
    get_device,
    load_data,
    numpy_to_state,
    partition_data,
    set_seed,
    state_to_numpy,
    train_local,
)

RESULT_PATH = PROJECT_ROOT / "results" / "real_byzantine_aggregate_once.json"

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
ATTACKS = ["none", "sign_flip", "gaussian", "scale", "random"]
MALICIOUS_COUNTS = [0, 1, 2, 3]
SEEDS = [0, 1]


def clone_arrays(arrays):
    return [np.array(a, copy=True) for a in arrays]


def collect_client_updates(global_weights, node_data, malicious_count, attack, seed, device):
    """One training pass for all clients. Returns list of update deltas."""
    updates = []
    for client_index, (node_X, node_y) in enumerate(node_data):
        local = CNNBiLSTMTorch().to(device)
        numpy_to_state(local, global_weights)
        train_local(
            local, node_X, node_y, device,
            epochs=1, batch_size=BATCH_SIZE, seed=seed + client_index + 1,
        )
        local_w = state_to_numpy(local)
        delta = [lw - gw for lw, gw in zip(local_w, global_weights)]
        if client_index < malicious_count and attack not in ("none", "honest"):
            kwargs = {}
            if attack == "gaussian":
                kwargs["std"] = 0.1
            if attack == "scale":
                kwargs["factor"] = 10.0
            delta = apply_weight_attack(delta, attack, seed=seed + client_index + 1000, **kwargs)
        updates.append(clone_arrays(delta))
        del local
        if device.type == "cuda":
            torch.cuda.empty_cache()
    return updates


def apply_and_eval(global_weights, updates, method, num_byzantine, clip_norm, X_test, y_test, device):
    trim = min(0.2, num_byzantine / max(NUM_NODES, 1))
    mixed = aggregate_updates(
        updates, method,
        num_byzantine=num_byzantine,
        trim_ratio=trim,
        clip_norm=clip_norm,
    )
    new_w = [gw + du for gw, du in zip(global_weights, mixed)]
    model = CNNBiLSTMTorch().to(device)
    numpy_to_state(model, new_w)
    metrics = evaluate_model(model, X_test, y_test, device)
    del model
    return metrics


def run_setting(malicious_count, attack, seed, device, aggregators):
    set_seed(seed)
    X_train, y_train, X_val, y_val, X_test, y_test = load_data()
    node_data = partition_data(X_train, y_train, seed)

    global_model = CNNBiLSTMTorch().to(device)
    set_seed(seed)
    global_model.apply(lambda m: m.reset_parameters() if hasattr(m, "reset_parameters") else None)
    set_seed(seed)
    global_weights = state_to_numpy(global_model)

    # Train clients ONCE
    updates = collect_client_updates(
        global_weights, node_data, malicious_count, attack, seed, device,
    )
    norms = [update_l2(u) for u in updates]
    clip_norm = max(1.0, float(np.median(norms)) * 3.0)

    rows = []
    for method in aggregators:
        try:
            metrics = apply_and_eval(
                global_weights, updates, method, malicious_count, clip_norm,
                X_test, y_test, device,
            )
            rows.append({
                "malicious_clients": malicious_count,
                "malicious_pct": malicious_count / NUM_NODES * 100,
                "attack": attack,
                "aggregator": method,
                "seed": seed,
                "status": "success",
                "mode": "train_once_aggregate_many",
                "clip_norm": clip_norm,
                "device": str(device),
                **metrics,
            })
            print(
                f"   {method:16s} F1={metrics['f1']:.4f} FPR={metrics['fpr']:.4f}"
            )
        except AggregationUnsupported as e:
            rows.append({
                "malicious_clients": malicious_count,
                "malicious_pct": malicious_count / NUM_NODES * 100,
                "attack": attack,
                "aggregator": method,
                "seed": seed,
                "status": "unsupported",
                "mode": "train_once_aggregate_many",
                "error": str(e),
                "device": str(device),
            })
            print(f"   {method:16s} UNSUPPORTED | {e}")
        except Exception as e:
            rows.append({
                "malicious_clients": malicious_count,
                "malicious_pct": malicious_count / NUM_NODES * 100,
                "attack": attack,
                "aggregator": method,
                "seed": seed,
                "status": "failed",
                "mode": "train_once_aggregate_many",
                "error": f"{type(e).__name__}: {e}",
                "device": str(device),
            })
            print(f"   {method:16s} FAILED | {type(e).__name__}: {e}")
    return rows


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--output", default=str(RESULT_PATH))
    args = parser.parse_args()

    device = get_device()
    print("=" * 70)
    print(" TRAIN ONCE -> AGGREGATE MANY (PyTorch GPU)")
    print("=" * 70)
    print(f"Device: {device}")
    if device.type == "cuda":
        print(f"GPU:    {torch.cuda.get_device_name(0)}")

    malicious_counts = MALICIOUS_COUNTS
    attacks = ATTACKS
    aggregators = AGGREGATORS
    seeds = SEEDS
    if args.smoke:
        malicious_counts = [0, 2]
        attacks = ["none", "sign_flip"]
        aggregators = ["fedavg", "median", "multi_krum", "trimmed_mean"]
        seeds = [0]

    all_rows = []
    settings = []
    for mc in malicious_counts:
        trial_attacks = ["none"] if mc == 0 else [a for a in attacks if a != "none"]
        for attack in trial_attacks:
            for seed in seeds:
                settings.append((mc, attack, seed))

    for i, (mc, attack, seed) in enumerate(settings, start=1):
        print(
            f"\n[{i}/{len(settings)}] TRAIN clients once | "
            f"malicious={mc}/{NUM_NODES} attack={attack} seed={seed}"
        )
        print(f"   then test {len(aggregators)} aggregators on the SAME updates")
        all_rows.extend(run_setting(mc, attack, seed, device, aggregators))

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(
            {
                "config": {
                    "mode": "train_once_aggregate_many",
                    "note": (
                        "Clients train once per (malicious, attack, seed). "
                        "All aggregators receive identical update tensors."
                    ),
                    "framework": "pytorch",
                    "device": str(device),
                    "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
                    "clients": NUM_NODES,
                    "local_epochs": 1,
                    "dataset": str(DATA_PATH),
                    "malicious_counts": malicious_counts,
                    "attacks": attacks,
                    "aggregators": aggregators,
                    "seeds": seeds,
                },
                "rows": all_rows,
            },
            f,
            indent=2,
        )
    print("\nCOMPLETE")
    print(f"Saved {out} ({len(all_rows)} rows)")


if __name__ == "__main__":
    main()
