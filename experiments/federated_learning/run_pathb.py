"""
Path-B federated training on 1-second CIC windows.

Input:  data/processed/cicddos2019_temporal_windows.npz  shape (N, 10, 40)
Output: models/fl_global_model_pathb.keras
        models/fl_global_model_pathb_central.keras
        models/sdn_model_contract.json
        results/pathb/metrics.json

Federated setup (simulated FedAvg, same machine, 3 orgs):
  node_tcp  : Syn + TFTP          (exploitation / TCP-ish)
  node_dns  : DrDoS_DNS + NTP + LDAP
  node_udp  : DrDoS_UDP + UDP-lag + MSSQL + NetBIOS
  Benign    : split across all 3 by Source IP hash (every org sees normal traffic)

This is Non-IID: each org mostly sees one attack family, which is the
realistic FL story. Weights are averaged with FedAvg, weighted by local n.

Usage:
  python experiments/federated_learning/run_pathb.py
  python experiments/federated_learning/run_pathb.py --skip-central
  python experiments/federated_learning/run_pathb.py --rounds 12 --epochs 3
"""

from __future__ import annotations

import argparse
import json
import logging
import pickle
import sys
from collections import Counter
from pathlib import Path

import numpy as np

project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

from projects.shared_libs import CNNBiLSTMModel  # noqa: E402
from projects.fl.aggregation_server import SimpleFLServer  # noqa: E402
from projects.fl.fl_node_client import FLNode  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

DATA_FILE = project_root / 'data' / 'processed' / 'cicddos2019_temporal_windows.npz'
EXTRACTOR = project_root / 'data' / 'processed' / 'cicddos2019_leakfree_feature_extractor.pkl'
SELECTION = project_root / 'data' / 'processed' / 'cicddos2019_leakfree_feature_selection.pkl'
OUT_FL = project_root / 'models' / 'fl_global_model_pathb.keras'
OUT_CENTRAL = project_root / 'models' / 'fl_global_model_pathb_central.keras'
OUT_CONTRACT = project_root / 'models' / 'sdn_model_contract.json'
OUT_METRICS = project_root / 'results' / 'pathb' / 'metrics.json'

# CIC class index -> FL node (Non-IID attack families)
NODE_BY_CLASS = {
    12: 0, 13: 0,          # Syn, TFTP
    1: 1, 4: 1, 2: 1,      # DNS, NTP, LDAP
    7: 2, 15: 2, 3: 2, 5: 2,  # UDP, UDP-lag, MSSQL, NetBIOS
}
NODE_NAMES = ('node_tcp', 'node_dns', 'node_udp')


def load_windows():
    z = np.load(DATA_FILE, allow_pickle=True)
    X, y = z['X'], z['y']
    class_names = [str(c) for c in z['class_names']]
    feature_names = [str(c) for c in z['feature_names']]
    if 'source_ip' in z.files:
        src = z['source_ip'].astype(str)
    else:
        logger.warning('source_ip missing; falling back to sequential groups of 8')
        src = np.array([f'g{i // 8}' for i in range(len(y))])
    logger.info(f'Loaded {X.shape} from {DATA_FILE.name}')
    return X, y, src, class_names, feature_names


def hybrid_split(y: np.ndarray, src: np.ndarray, seed: int = 42, train=0.70, val=0.15):
    """
    Attack IPs are few (often one botnet address). A pure IP hold-out then
    puts every attack in train and leaves val/test 100% benign.

    Rule:
      - IPs that send attacks: chronological 70/15/15 of that IP's windows
        (can we detect the rest of the same flood?)
      - Benign-only IPs: hold out whole IPs (false-positive test on unseen clients)
    """
    rng = np.random.default_rng(seed)
    tr = np.zeros(len(y), dtype=bool)
    va = np.zeros(len(y), dtype=bool)
    te = np.zeros(len(y), dtype=bool)

    attack_ips = set(src[y != 0])
    benign_ips = [s for s in np.unique(src) if s not in attack_ips]
    rng.shuffle(benign_ips)
    n = len(benign_ips)
    n_tr = max(1, int(n * train)) if n else 0
    n_va = max(1, int(n * val)) if n > 2 else 0
    b_tr = set(benign_ips[:n_tr])
    b_va = set(benign_ips[n_tr:n_tr + n_va])
    b_te = set(benign_ips[n_tr + n_va:])

    for i, (yi, s) in enumerate(zip(y, src)):
        if s not in attack_ips:
            tr[i] = s in b_tr
            va[i] = s in b_va
            te[i] = s in b_te

    for s in attack_ips:
        idx = np.where(src == s)[0]
        # windows are already time-sorted per IP inside the NPZ builder
        n_i = len(idx)
        a = max(1, int(n_i * train))
        b = max(a + 1, int(n_i * (train + val)))
        if n_i < 6:
            tr[idx] = True
            continue
        tr[idx[:a]] = True
        va[idx[a:b]] = True
        te[idx[b:]] = True
        if te[idx].sum() == 0:
            te[idx[-1]] = True
            tr[idx[-1]] = False

    # anything unassigned (shouldn't happen) goes to train
    leftover = ~(tr | va | te)
    tr |= leftover

    def mix(mask):
        return {
            'n': int(mask.sum()),
            'benign': int((y[mask] == 0).sum()),
            'attack': int((y[mask] != 0).sum()),
        }

    logger.info(f'Hybrid split train={mix(tr)} val={mix(va)} test={mix(te)}')
    return tr, va, te


def class_weights(y: np.ndarray, cap: float = 8.0) -> dict:
    n = len(y)
    counts = Counter(y.tolist())
    c = max(len(counts), 1)
    w = {}
    for k, nk in counts.items():
        w[int(k)] = min(cap, n / (c * nk))
    return w


def build_model(input_shape, num_classes):
    return CNNBiLSTMModel(
        input_shape=input_shape,
        num_classes=num_classes,
        cnn_filters=(64, 128),
        lstm_units=(64, 32),
        dropout_rate=0.5,
    ).model


def evaluate(model, X, y, class_names, tag: str, threshold: float = 0.80) -> dict:
    probs = model.predict(X, verbose=0)
    pred = probs.argmax(axis=1)
    acc = float((pred == y).mean())
    attack_true = y != 0
    attack_score = 1.0 - probs[:, 0]
    attack_pred = attack_score >= threshold
    tp = int((attack_pred & attack_true).sum())
    fp = int((attack_pred & ~attack_true).sum())
    fn = int((~attack_pred & attack_true).sum())
    tn = int((~attack_pred & ~attack_true).sum())
    fpr = fp / max(fp + tn, 1)
    rec = tp / max(tp + fn, 1)
    syn_idx = class_names.index('Syn') if 'Syn' in class_names else -1
    syn_rec = None
    if syn_idx >= 0 and (y == syn_idx).any():
        syn_rec = float(((pred == syn_idx) & (y == syn_idx)).sum() / (y == syn_idx).sum())
    out = {
        'tag': tag,
        'n': int(len(y)),
        'acc_18': acc,
        'binary_recall': rec,
        'binary_fpr': fpr,
        'syn_recall': syn_rec,
        'threshold': threshold,
        'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
    }
    syn_s = f'{syn_rec:.3f}' if syn_rec is not None else 'n/a'
    logger.info(
        f'{tag}: 18-acc={acc:.3f}  attack-recall={rec:.3f}  '
        f'FPR={fpr:.3f}  Syn-recall={syn_s}  n={len(y)}'
    )
    return out


def train_central(Xtr, ytr, Xva, yva, num_classes, weights, epochs: int):
    import tensorflow as tf
    model = build_model(Xtr.shape[1:], num_classes)
    cb = [
        tf.keras.callbacks.EarlyStopping(monitor='val_loss', patience=4, restore_best_weights=True),
        tf.keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=2, min_lr=1e-5),
    ]
    model.fit(
        Xtr, ytr,
        validation_data=(Xva, yva),
        epochs=epochs,
        batch_size=32,
        class_weight=weights,
        verbose=2,
        callbacks=cb,
    )
    return model


def assign_nodes(y: np.ndarray, src: np.ndarray) -> np.ndarray:
    out = np.empty(len(y), dtype=np.int32)
    for i, (yi, s) in enumerate(zip(y, src)):
        if int(yi) == 0:
            out[i] = hash(str(s)) % 3
        else:
            out[i] = NODE_BY_CLASS.get(int(yi), hash(str(s)) % 3)
    return out


def train_federated(Xtr, ytr, src_tr, num_classes, weights, rounds: int, epochs: int):
    builder = lambda: build_model(Xtr.shape[1:], num_classes)
    global_model = builder()
    server = SimpleFLServer(global_model=global_model, num_rounds=rounds)

    node_ids = assign_nodes(ytr, src_tr)
    nodes = []
    for k, name in enumerate(NODE_NAMES):
        mask = node_ids == k
        if mask.sum() < 8:
            logger.warning(f'{name} has only {mask.sum()} samples — skipping')
            continue
        node = FLNode(
            node_id=name,
            local_data=(Xtr[mask], ytr[mask]),
            model_builder_fn=builder,
            epochs_per_round=epochs,
            batch_size=32,
            class_weight=weights,
        )
        nodes.append(node)
        server.register_node(name, int(mask.sum()))
        logger.info(f'{name}: {int(mask.sum()):,} windows  labels={dict(Counter(ytr[mask].tolist()))}')

    for r in range(1, rounds + 1):
        logger.info(f'===== FL ROUND {r}/{rounds} =====')
        gw = server.get_global_weights()
        updates = {}
        for node in nodes:
            updates[node.node_id] = node.participate_in_round(gw, verbose=0)
        server.aggregate_and_update(updates)

    return global_model


def write_contract(class_names, feature_names, model_path: Path):
    with open(EXTRACTOR, 'rb') as f:
        ext = pickle.load(f)
    with open(SELECTION, 'rb') as f:
        sel = pickle.load(f)['ensemble']
    scaler = ext['scaler']
    all_clean = list(ext['feature_names'])
    sel_idx = [all_clean.index(n) for n in feature_names]
    contract = {
        'model_path': str(model_path.as_posix()),
        'input_shape': [10, 40],
        'num_classes': len(class_names),
        'class_names': class_names,
        'feature_names': feature_names,
        'benign_index': 0,
        'attack_score': '1 - softmax[benign_index]',
        'leaky_columns_excluded': ['Unnamed: 0', 'Class'],
        'scaler': {
            'type': 'StandardScaler',
            'fitted_on': '77 leak-free CIC columns then sliced to 40',
            'mean_40': scaler.mean_[sel_idx].tolist(),
            'scale_40': scaler.scale_[sel_idx].tolist(),
        },
        'selection': {
            'method': 'ensemble',
            'indices_in_77': list(sel['indices']),
        },
    }
    OUT_CONTRACT.write_text(json.dumps(contract, indent=2))
    logger.info(f'Wrote {OUT_CONTRACT}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--rounds', type=int, default=12)
    parser.add_argument('--epochs', type=int, default=3, help='Local epochs per FL round')
    parser.add_argument('--central-epochs', type=int, default=20)
    parser.add_argument('--skip-central', action='store_true')
    parser.add_argument('--skip-federated', action='store_true')
    parser.add_argument('--threshold', type=float, default=0.80)
    args = parser.parse_args()

    X, y, src, class_names, feature_names = load_windows()
    tr, va, te = hybrid_split(y, src)
    weights = class_weights(y[tr])
    logger.info(f'Class weights (capped): { {class_names[k]: round(v, 2) for k, v in sorted(weights.items())} }')

    metrics = {'class_names': class_names, 'n_total': int(len(y))}
    chosen = None

    if not args.skip_central:
        logger.info('===== CENTRALISED TRAINING =====')
        central = train_central(X[tr], y[tr], X[va], y[va], len(class_names), weights, args.central_epochs)
        OUT_CENTRAL.parent.mkdir(parents=True, exist_ok=True)
        central.save(OUT_CENTRAL)
        metrics['central'] = {
            'val': evaluate(central, X[va], y[va], class_names, 'central-val', args.threshold),
            'test': evaluate(central, X[te], y[te], class_names, 'central-test', args.threshold),
        }
        chosen = OUT_CENTRAL

    if not args.skip_federated:
        logger.info('===== FEDERATED FedAvg (3 Non-IID nodes) =====')
        fl = train_federated(X[tr], y[tr], src[tr], len(class_names), weights, args.rounds, args.epochs)
        fl.save(OUT_FL)
        metrics['federated'] = {
            'val': evaluate(fl, X[va], y[va], class_names, 'fl-val', args.threshold),
            'test': evaluate(fl, X[te], y[te], class_names, 'fl-test', args.threshold),
            'rounds': args.rounds,
            'epochs_per_round': args.epochs,
            'nodes': list(NODE_NAMES),
        }
        chosen = OUT_FL

    write_contract(class_names, feature_names, chosen or OUT_FL)
    OUT_METRICS.parent.mkdir(parents=True, exist_ok=True)
    OUT_METRICS.write_text(json.dumps(metrics, indent=2))
    logger.info(f'Wrote {OUT_METRICS}')
    logger.info('Path-B training complete.')


if __name__ == '__main__':
    main()
