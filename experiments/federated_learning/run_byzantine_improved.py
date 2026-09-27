#!/usr/bin/env python3
"""Byzantine FL improvement study.

Phases covered:
  1. Honest 0% baseline, L2 update clipping, Krum refusal instead of client-0 fallback.
  2. FedAvg vs FedAvg+clip, Multi-Krum, Bulyan, trust-weighted average, wrong-f sweep.
  3. Label flip, backdoor, non-IID partitions, adaptive (near-honest) attack.
  4. F1 and FPR plots plus a failure table.

The CIC-DDoS2019 npz is not in this checkout, so the measured matrix trains a
linear detector with the same attack suite and aggregators. The CNN runner
calls the same aggregate_updates path when that dataset is present.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from projects.shared_libs.attack_suite import (  # noqa: E402
    adaptive_update,
    apply_weight_attack,
    label_flip,
)
from projects.shared_libs.byzantine_defense import (  # noqa: E402
    AggregationUnsupported,
    aggregate_updates,
    update_l2,
)
from projects.shared_libs.metrics_harness import binary_metrics  # noqa: E402

logging.getLogger("projects.shared_libs.byzantine_defense").setLevel(logging.WARNING)

METHODS = [
    "fedavg",
    "fedavg_clip",
    "krum",
    "multi_krum",
    "median",
    "trimmed_mean",
    "bulyan",
    "trust_weighted",
]
ATTACKS = [
    "sign_flip",
    "scale",
    "gaussian",
    "random",
    "label_flip",
    "backdoor",
    "adaptive",
]
KRUM_FAMILY = {"krum", "multi_krum", "bulyan"}
WEIGHT_ATTACKS = {"sign_flip", "scale", "gaussian", "random"}


def make_dataset(n_train: int, n_test: int, dim: int, seed: int):
    rng = np.random.default_rng(seed)
    true_w = rng.normal(size=dim)
    true_w = true_w / np.linalg.norm(true_w)

    def draw(n, rng_local):
        x = rng_local.normal(size=(n, dim))
        logits = x @ true_w * 2.5
        prob = 1.0 / (1.0 + np.exp(-logits))
        y = (rng_local.random(n) < prob).astype(np.float64)
        return x, y

    x_train, y_train = draw(n_train, rng)
    x_test, y_test = draw(n_test, np.random.default_rng(seed + 10_000))
    return x_train, y_train, x_test, y_test


def partition(x, y, n_clients: int, seed: int, non_iid: bool):
    rng = np.random.default_rng(seed)
    if not non_iid:
        order = rng.permutation(len(x))
        return [(x[idx], y[idx]) for idx in np.array_split(order, n_clients)]

    buckets = [[] for _ in range(n_clients)]
    for label in (0.0, 1.0):
        idx = np.where(y == label)[0]
        rng.shuffle(idx)
        props = rng.dirichlet([0.3] * n_clients)
        cuts = np.cumsum((props * len(idx)).astype(int))
        cuts[-1] = len(idx)
        prev = 0
        for client, cut in enumerate(cuts):
            buckets[client].extend(idx[prev:cut].tolist())
            prev = int(cut)
    parts = []
    for bucket in buckets:
        if len(bucket) < 4:
            extra = rng.choice(len(x), size=8, replace=False)
            bucket = list(bucket) + extra.tolist()
        chosen = np.array(bucket, dtype=int)
        parts.append((x[chosen], y[chosen]))
    return parts


def local_delta(w, b, x, y, steps: int, lr: float, batch: int, rng):
    w = np.array(w, dtype=np.float64, copy=True)
    b = float(b)
    start_w, start_b = w.copy(), b
    if len(x) < 2:
        return [np.zeros_like(start_w), np.zeros(1)]
    for _ in range(steps):
        take = min(batch, len(x))
        sel = rng.choice(len(x), size=take, replace=False)
        xb, yb = x[sel], y[sel]
        scores = np.clip(xb @ w + b, -30, 30)
        prob = 1.0 / (1.0 + np.exp(-scores))
        error = prob - yb
        w -= lr * (xb.T @ error) / take
        b -= lr * float(np.mean(error))
    return [w - start_w, np.array([b - start_b])]


def predict_scores(w, b, x):
    return 1.0 / (1.0 + np.exp(-np.clip(x @ w + b, -30, 30)))


def apply_backdoor(x, y, ratio: float, seed: int):
    rng = np.random.default_rng(seed)
    x2, y2 = np.array(x, copy=True), np.array(y, copy=True)
    count = max(1, int(len(y2) * ratio))
    idx = rng.choice(len(y2), size=min(count, len(y2)), replace=False)
    x2[idx, 0] = 5.0
    y2[idx] = 0.0
    return x2, y2


def backdoor_success(w, b, x_test, y_test) -> float:
    attack = np.where(y_test == 1)[0]
    if len(attack) == 0:
        return 0.0
    triggered = np.array(x_test[attack], copy=True)
    triggered[:, 0] = 5.0
    predicted = (predict_scores(w, b, triggered) >= 0.5).astype(int)
    return float(np.mean(predicted == 0))


def _client_update(w, b, x, y, client_index, malicious_count, attack, seed, steps, lr, batch):
    rng = np.random.default_rng(seed + client_index * 17)
    local_x, local_y = x, y
    malicious = client_index < malicious_count
    if malicious and attack == "label_flip":
        local_y = label_flip(local_y, seed=seed + client_index, ratio=1.0)
    if malicious and attack == "backdoor":
        local_x, local_y = apply_backdoor(local_x, local_y, ratio=0.4, seed=seed + client_index)
    delta = local_delta(w, b, local_x, local_y, steps, lr, batch, rng)
    if malicious and attack in WEIGHT_ATTACKS:
        kwargs = {}
        if attack == "gaussian":
            kwargs["std"] = 1.0
        if attack == "scale":
            kwargs["factor"] = 30.0
        delta = apply_weight_attack(delta, attack, seed=seed + client_index, **kwargs)
    return delta, malicious


def run_trial(
    malicious_pct: float,
    attack: str,
    method: str,
    seed: int,
    clients: int = 20,
    rounds: int = 6,
    assumed_f: int | None = None,
    non_iid: bool = False,
    dim: int = 12,
    steps: int = 6,
    lr: float = 0.2,
    batch: int = 32,
    n_train: int = 4000,
    n_test: int = 1200,
) -> dict:
    true_f = int(round(clients * malicious_pct / 100.0))
    f_used = true_f if assumed_f is None else int(assumed_f)
    x_train, y_train, x_test, y_test = make_dataset(n_train, n_test, dim, seed)
    parts = partition(x_train, y_train, clients, seed, non_iid)
    w = np.zeros(dim, dtype=np.float64)
    b = 0.0

    probe = [
        local_delta(w, b, px, py, steps=2, lr=lr, batch=batch, rng=np.random.default_rng(seed + i))
        for i, (px, py) in enumerate(parts)
    ]
    clip_norm = max(0.05, float(np.median([update_l2(delta) for delta in probe])) * 3.0)
    trim_ratio = 0.0 if true_f == 0 else min(0.45, true_f / clients)

    for round_id in range(rounds):
        updates = []
        honest = []
        round_seed = seed + 1000 * (round_id + 1)
        for client_index, (px, py) in enumerate(parts):
            delta, malicious = _client_update(
                w, b, px, py, client_index, true_f, attack, round_seed, steps, lr, batch,
            )
            updates.append(delta)
            if not malicious:
                honest.append(delta)
        if attack == "adaptive" and true_f > 0 and honest:
            nudged = adaptive_update(honest, bias=3.0)
            for client_index in range(true_f):
                updates[client_index] = nudged
        try:
            mixed = aggregate_updates(
                updates,
                method,
                num_byzantine=f_used,
                trim_ratio=trim_ratio,
                clip_norm=clip_norm,
            )
        except AggregationUnsupported as exc:
            return _row(
                malicious_pct, attack, method, seed, true_f, f_used, non_iid, clip_norm,
                status="unsupported", error=str(exc),
            )
        w = w + mixed[0]
        b = float(b + mixed[1][0])
        if not np.isfinite(w).all() or not np.isfinite(b):
            return _row(
                malicious_pct, attack, method, seed, true_f, f_used, non_iid, clip_norm,
                status="failed", error="non-finite weights",
            )

    scores = predict_scores(w, b, x_test)
    predicted = (scores >= 0.5).astype(int)
    metrics = binary_metrics(y_test, predicted, scores)
    metrics["backdoor_asr"] = backdoor_success(w, b, x_test, y_test)
    return _row(
        malicious_pct, attack, method, seed, true_f, f_used, non_iid, clip_norm,
        status="success", metrics=metrics,
    )


def _row(pct, attack, method, seed, true_f, assumed_f, non_iid, clip_norm, status, error="", metrics=None):
    row = {
        "malicious_pct": pct,
        "malicious_clients": true_f,
        "attack": attack,
        "aggregator": method,
        "seed": seed,
        "assumed_f": assumed_f,
        "non_iid": non_iid,
        "clip_norm": clip_norm,
        "status": status,
    }
    if error:
        row["error"] = error
    if metrics:
        row.update(metrics)
    return row


def iter_jobs(profile: str):
    if profile == "smoke":
        for method in ("fedavg", "fedavg_clip", "median", "krum"):
            for pct, attack in ((0, "none"), (40, "sign_flip"), (40, "gaussian")):
                yield dict(malicious_pct=pct, attack=attack, method=method, seed=0,
                           clients=10, rounds=3, non_iid=False)
        yield dict(malicious_pct=40, attack="sign_flip", method="bulyan", seed=0,
                   clients=10, rounds=2, non_iid=False)
        return

    seeds = [0, 1, 2]
    clients, rounds = 20, 6
    for pct in (0, 10, 20, 30, 40):
        attacks = ["none"] if pct == 0 else ATTACKS
        for attack in attacks:
            for method in METHODS:
                for seed in seeds:
                    yield dict(
                        malicious_pct=pct, attack=attack, method=method, seed=seed,
                        clients=clients, rounds=rounds, non_iid=False,
                    )
    for pct in (20, 40):
        true_f = int(round(clients * pct / 100.0))
        for assumed in (0, true_f, min(clients - 3, true_f + 4)):
            for attack in ("sign_flip", "scale"):
                for method in ("krum", "multi_krum"):
                    for seed in seeds:
                        yield dict(
                            malicious_pct=pct, attack=attack, method=method, seed=seed,
                            clients=clients, rounds=rounds, assumed_f=assumed, non_iid=False,
                        )
    for pct in (0, 20, 40):
        attacks = ["none"] if pct == 0 else ("sign_flip", "label_flip", "adaptive")
        for attack in attacks:
            for method in ("fedavg", "fedavg_clip", "median", "multi_krum", "trimmed_mean"):
                for seed in seeds:
                    yield dict(
                        malicious_pct=pct, attack=attack, method=method, seed=seed,
                        clients=clients, rounds=rounds, non_iid=True,
                    )


def summarize(rows):
    groups = {}
    for row in rows:
        if row.get("non_iid"):
            continue
        if row["aggregator"] in KRUM_FAMILY and row["assumed_f"] != row["malicious_clients"]:
            continue
        key = (row["malicious_pct"], row["attack"], row["aggregator"])
        groups.setdefault(key, []).append(row)
    lines = []
    for key in sorted(groups):
        bucket = groups[key]
        ok = [r for r in bucket if r["status"] == "success"]
        failed = sum(r["status"] == "failed" for r in bucket)
        unsupported = sum(r["status"] == "unsupported" for r in bucket)
        if ok:
            f1 = sum(r["f1"] for r in ok) / len(ok)
            fpr = sum(r["fpr"] for r in ok) / len(ok)
            lines.append({
                "malicious_pct": key[0], "attack": key[1], "aggregator": key[2],
                "f1": f1, "fpr": fpr, "n": len(ok),
                "failed": failed, "unsupported": unsupported,
            })
        else:
            lines.append({
                "malicious_pct": key[0], "attack": key[1], "aggregator": key[2],
                "f1": None, "fpr": None, "n": 0,
                "failed": failed, "unsupported": unsupported,
            })
    return lines


def write_plots(rows, out_dir: Path):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    summary = [
        item for item in summarize(rows)
        if item["attack"] == "sign_flip" and item["f1"] is not None
    ]
    written = []
    for metric, filename, ylabel in (
        ("f1", "byzantine_improved_f1.png", "Mean F1"),
        ("fpr", "byzantine_improved_fpr.png", "Mean false positive rate"),
    ):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        methods = []
        for item in summary:
            if item["aggregator"] not in methods:
                methods.append(item["aggregator"])
        for method in methods:
            pts = [item for item in summary if item["aggregator"] == method]
            pts.sort(key=lambda item: item["malicious_pct"])
            ax.plot(
                [item["malicious_pct"] for item in pts],
                [item[metric] for item in pts],
                marker="o",
                label=method,
            )
        ax.set_xlabel("Malicious clients (%)")
        ax.set_ylabel(ylabel)
        ax.set_title(f"Sign-flip attack — {ylabel}")
        ax.legend(fontsize=8, ncol=2)
        ax.grid(True, alpha=0.3)
        path = out_dir / filename
        fig.tight_layout()
        fig.savefig(path, dpi=120)
        plt.close(fig)
        written.append(str(path))
    return written


def write_report(rows, path: Path, config: dict):
    summary = summarize(rows)
    failures = [r for r in rows if r["status"] != "success"]
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1

    def cell(pct, attack, method, field):
        for item in summary:
            if item["malicious_pct"] == pct and item["attack"] == attack and item["aggregator"] == method:
                value = item[field]
                return "—" if value is None else f"{value:.4f}"
        return "—"

    lines = [
        "# Byzantine aggregation improvement results",
        "",
        "Measured with a linear detector because `data/processed/cicddos2019_100k_reshaped_t10.npz` is not in this checkout.",
        "Aggregation, clipping, and the attack suite are the same code the CNN runner now calls.",
        "",
        f"Config: {json.dumps(config)}",
        "",
        f"Runs: {len(rows)} ({counts}).",
        "",
        "## Sign-flip F1 (mean over seeds, correct f, IID)",
        "",
        "| Malicious | FedAvg | FedAvg+clip | Median | Multi-Krum | Trimmed mean |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for pct in (0, 10, 20, 30, 40):
        attack = "none" if pct == 0 else "sign_flip"
        lines.append(
            f"| {pct}% | {cell(pct, attack, 'fedavg', 'f1')} | {cell(pct, attack, 'fedavg_clip', 'f1')} | "
            f"{cell(pct, attack, 'median', 'f1')} | {cell(pct, attack, 'multi_krum', 'f1')} | "
            f"{cell(pct, attack, 'trimmed_mean', 'f1')} |"
        )
    lines += [
        "",
        "## Sign-flip FPR",
        "",
        "| Malicious | FedAvg | FedAvg+clip | Median |",
        "|---|---:|---:|---:|",
    ]
    for pct in (0, 10, 20, 30, 40):
        attack = "none" if pct == 0 else "sign_flip"
        lines.append(
            f"| {pct}% | {cell(pct, attack, 'fedavg', 'fpr')} | {cell(pct, attack, 'fedavg_clip', 'fpr')} | "
            f"{cell(pct, attack, 'median', 'fpr')} |"
        )
    lines += ["", "## Runs that did not score", ""]
    if not failures:
        lines.append("Every scheduled run produced a finite model.")
    else:
        lines.append("| Setting | Status | Count |")
        lines.append("|---|---|---:|")
        bucket = {}
        for row in failures:
            key = (row["malicious_pct"], row["attack"], row["aggregator"], row["status"], row.get("non_iid"))
            bucket[key] = bucket.get(key, 0) + 1
        for key, count in sorted(bucket.items()):
            lines.append(
                f"| {key[0]}% {key[1]} {key[2]} non_iid={key[4]} | {key[3]} | {count} |"
            )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", choices=("paper", "smoke"), default="paper")
    parser.add_argument("--output", default="results/byzantine_improved.json")
    args = parser.parse_args()
    jobs = list(iter_jobs(args.profile))
    rows = []
    for index, job in enumerate(jobs, start=1):
        row = run_trial(**job)
        rows.append(row)
        if index % 25 == 0 or index == len(jobs):
            print(f"[{index}/{len(jobs)}] {row['status']} {row['aggregator']} {row['attack']} {row['malicious_pct']}%", flush=True)
    payload = {
        "config": {
            "profile": args.profile,
            "command": "python experiments/federated_learning/run_byzantine_improved.py --profile paper",
            "clients": 10 if args.profile == "smoke" else 20,
            "note": "Linear stand-in. CNN path uses aggregate_updates in run_real_byzantine_fl.py.",
        },
        "rows": rows,
        "summary": summarize(rows),
    }
    out = ROOT / args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    plots = write_plots(rows, out.parent)
    report = ROOT / "reports" / "BYZANTINE_IMPROVEMENT_RESULTS.md"
    write_report(rows, report, payload["config"])
    print(f"Saved {out}")
    print(f"Report {report}")
    for plot in plots:
        print(f"Plot {plot}")


if __name__ == "__main__":
    main()
