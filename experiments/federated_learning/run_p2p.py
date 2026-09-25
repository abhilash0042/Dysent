"""
In-process P2P federated learning entry point.

Separate from experiments/federated_learning/run_standard.py.
This runner does not create a central aggregation server.

    python experiments/federated_learning/run_p2p.py --transport inprocess --seed 42

Without --synthetic, the run stops if the processed CIC-DDoS2019 files are
absent. It does not invent a dataset. --synthetic is an explicit smoke path
and is labeled as such in the log.
"""

from __future__ import annotations

import argparse
import logging
import pickle
import sys
from pathlib import Path

import numpy as np
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from projects.fl.p2p import load_topology, topology_from_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_p2p")


class DatasetUnavailable(SystemExit):
    """Real CIC-DDoS2019 inputs are not in this checkout."""


def _resolve_config(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_file():
        return candidate
    rooted = ROOT / path
    if rooted.is_file():
        return rooted
    raise SystemExit(f"Config not found: {path}")


def _load_config(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, dict):
        raise SystemExit(f"Config is empty: {path}")
    return config


def _missing_cic_files(config: dict) -> list[str]:
    data_cfg = config.get("data", {})
    missing = []
    npz = ROOT / data_cfg.get(
        "processed_npz", "data/processed/cicddos2019_full_processed.npz"
    )
    if not npz.is_file():
        missing.append(str(npz))
    if data_cfg.get("use_selected_features", True):
        selection = ROOT / data_cfg.get(
            "feature_selection_pkl",
            "data/processed/cicddos2019_full_processed_feature_selection.pkl",
        )
        if not selection.is_file():
            missing.append(str(selection))
    loader = ROOT / "scripts" / "data" / "load_cicddos.py"
    if not loader.is_file():
        missing.append(str(loader))
    return missing


def require_cic_dataset(config: dict) -> None:
    missing = _missing_cic_files(config)
    if not missing:
        return
    lines = [
        "P2P CIC-DDoS2019 run cannot start.",
        "A required dataset file or scripts/data/load_cicddos.py is missing.",
        "No synthetic dataset was generated in its place.",
        "Missing:",
    ]
    lines.extend(f"  - {item}" for item in missing)
    lines.append(
        "Re-run with --synthetic for an in-process smoke test on random tensors, "
        "or provide the files above before a real experiment."
    )
    raise DatasetUnavailable("\n".join(lines))


def load_cic_arrays(config: dict):
    require_cic_dataset(config)
    from scripts.data.load_cicddos import reshape_for_cnn_bilstm

    data_cfg = config["data"]
    model_cfg = config["model"]
    npz_path = ROOT / data_cfg["processed_npz"]
    logger.info("Loading CIC-DDoS2019 arrays from %s", npz_path)
    loaded = np.load(npz_path)
    X = loaded["X"]
    y = loaded["y"]
    if data_cfg.get("use_selected_features", True):
        selection_path = ROOT / data_cfg["feature_selection_pkl"]
        with selection_path.open("rb") as handle:
            selection = pickle.load(handle)
        key = data_cfg.get("feature_selection_key", "ensemble")
        X = X[:, selection[key]["indices"]]
        logger.info("Selected %s features via %s", X.shape[1], key)
    from sklearn.model_selection import train_test_split

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=float(data_cfg.get("test_size", 0.15)),
        random_state=int(config["training"].get("seed", 42)),
        stratify=y,
    )
    timesteps = int(model_cfg.get("timesteps", 10))
    X_train = reshape_for_cnn_bilstm(X_train, timesteps)
    X_test = reshape_for_cnn_bilstm(X_test, timesteps)
    return X_train, y_train, X_test, y_test


def deterministic_subset_indices(y: np.ndarray, max_samples: int, seed: int) -> np.ndarray:
    """Take a seeded per-class slice of real rows. Does not synthesize values."""
    labels = np.asarray(y)
    classes = np.unique(labels)
    if max_samples < len(classes) * 4:
        raise ValueError(
            f"max_samples={max_samples} is too small for {len(classes)} classes "
            "(need at least 4 rows per class so the hold-out split stays stratified)"
        )
    per_class = max_samples // len(classes)
    rng = np.random.RandomState(seed)
    chosen = []
    for label in classes:
        pool = np.flatnonzero(labels == label)
        if len(pool) < 4:
            raise ValueError(f"Class {label} has only {len(pool)} rows in the processed file")
        take = min(per_class, len(pool))
        chosen.append(rng.choice(pool, size=take, replace=False))
    return np.concatenate(chosen)


def load_real_smoke_arrays(config: dict, seed: int, max_samples: int = 180):
    """Real CIC rows, ensemble-40 selection, then (N, 10, 4). Small subset only."""
    require_cic_dataset(config)
    from scripts.data.load_cicddos import reshape_for_cnn_bilstm

    data_cfg = config["data"]
    model_cfg = config["model"]
    npz_path = ROOT / data_cfg["processed_npz"]
    logger.info("Loading CIC-DDoS2019 arrays from %s", npz_path)
    loaded = np.load(npz_path)
    X = loaded["X"]
    y = loaded["y"]
    selection_path = ROOT / data_cfg["feature_selection_pkl"]
    with selection_path.open("rb") as handle:
        selection = pickle.load(handle)
    key = data_cfg.get("feature_selection_key", "ensemble")
    indices = selection[key]["indices"]
    X = X[:, indices]
    if X.shape[1] != 40:
        raise ValueError(f"Expected 40 ensemble features, got {X.shape[1]}")
    logger.info("Selected %s features via %s from %s rows", X.shape[1], key, len(y))

    chosen = deterministic_subset_indices(y, max_samples, seed)
    timesteps = int(model_cfg.get("timesteps", 10))
    X_small = reshape_for_cnn_bilstm(X[chosen], timesteps)
    y_small = np.asarray(y)[chosen]
    if X_small.shape[1:] != (10, 4):
        raise ValueError(f"Expected reshaped smoke rows (N, 10, 4), got {X_small.shape}")

    from sklearn.model_selection import train_test_split

    X_train, X_test, y_train, y_test = train_test_split(
        X_small,
        y_small,
        test_size=0.2,
        random_state=seed,
        stratify=y_small,
    )
    logger.info(
        "REAL CIC-DDoS2019 smoke subset: %s rows before hold-out, train %s, test %s, shape %s. "
        "Not the full dataset and not a 20-round run.",
        len(y_small),
        len(y_train),
        len(y_test),
        X_train.shape[1:],
    )
    return X_train, y_train, X_test, y_test


def make_synthetic_arrays(seed: int, orgs: list[str]):
    """Small random tensors for a smoke test. Not CIC-DDoS2019."""
    rng = np.random.default_rng(seed)
    per_org = 40
    total = per_org * len(orgs)
    X = rng.normal(size=(total, 10, 4)).astype(np.float32)
    y = np.resize(np.array([0, 1], dtype=np.int64), total)
    rng.shuffle(y)
    holdout = max(len(orgs), 20)
    return X[:-holdout], y[:-holdout], X[-holdout:], y[-holdout:]


def build_model_fn(input_shape, num_classes: int, model_cfg: dict):
    from projects.shared_libs.cnn_bilstm_model import CNNBiLSTMModel

    filters = tuple(model_cfg.get("cnn_filters", [64, 128]))
    units = tuple(model_cfg.get("lstm_units", [64, 32]))
    dropout = float(model_cfg.get("dropout_rate", 0.5))
    learning_rate = float(model_cfg.get("learning_rate", 0.001))

    def build():
        model = CNNBiLSTMModel(
            input_shape=input_shape,
            num_classes=num_classes,
            cnn_filters=filters,
            lstm_units=units,
            dropout_rate=dropout,
            learning_rate=learning_rate,
        )
        return model.model

    return build


def _load_run_arrays(config, orgs, seed, synthetic, real_smoke, max_samples, rounds, epochs, batch_size):
    num_rounds = int(rounds if rounds is not None else config.get("training", {}).get("num_rounds", 1))
    epochs_per_round = int(
        epochs if epochs is not None else config.get("training", {}).get("epochs_per_round", 1)
    )
    if synthetic:
        logger.info("SYNTHETIC smoke data. This is not a CIC-DDoS2019 experiment.")
        arrays = make_synthetic_arrays(seed, orgs)
        if rounds is None:
            num_rounds = 1
        if epochs is None:
            epochs_per_round = 1
        batch_size = min(batch_size, 16)
    elif real_smoke:
        logger.info("REAL CIC-DDoS2019 smoke subset. Not the full 20-round experiment.")
        arrays = load_real_smoke_arrays(config, seed, max_samples)
        if rounds is None:
            num_rounds = 1
        if epochs is None:
            epochs_per_round = 1
        batch_size = min(batch_size, 16)
    else:
        arrays = load_cic_arrays(config)
    return arrays, num_rounds, epochs_per_round, batch_size


def run_tcp_organization(
    config: dict,
    *,
    org_id: str,
    seed: int,
    synthetic: bool,
    rounds: int | None,
    epochs: int | None,
    real_smoke: bool,
    max_samples: int,
):
    """Train one organization in this process and gossip over localhost TCP."""
    from projects.fl.fl_node_client import FLNode
    from projects.fl.p2p import GossipNode
    from projects.fl.p2p.tcp_transport import TcpTransport, endpoints_from_config
    from projects.shared_libs.data_processor import DataPartitioner

    training = config.setdefault("training", {})
    training["seed"] = seed
    topology = topology_from_config(config)
    orgs = topology.organizations()
    if org_id not in orgs:
        raise SystemExit(f"Unknown organization {org_id}. Known: {orgs}")

    endpoints = endpoints_from_config(config)
    timeout = float((config.get("tcp") or {}).get("timeout_seconds", 15))
    transport = TcpTransport(
        org_id,
        endpoints,
        topology.neighbors(org_id),
        timeout=timeout,
    )
    transport.start()
    try:
        X_train, y_train, X_test, y_test, num_rounds, epochs_per_round, batch_size = (
            _prepare_tcp_arrays(
                config, orgs, seed, synthetic, real_smoke, max_samples, rounds, epochs, training
            )
        )
        hellos = transport.exchange_hellos()
        logger.info("%s neighbor HELLO status: %s", org_id, hellos)

        np.random.seed(seed)
        partitioner = DataPartitioner(
            num_nodes=len(orgs),
            iid=config.get("data", {}).get("distribution", "iid") == "iid",
        )
        parts = partitioner.partition(X_train, y_train)
        org_index = orgs.index(org_id)
        X_node, y_node = parts[org_index]
        num_classes = int(len(np.unique(y_train)))
        if num_classes < 2:
            num_classes = 2

        import tensorflow as tf

        tf.random.set_seed(seed)
        model_builder = build_model_fn(X_train.shape[1:], num_classes, config.get("model", {}))
        fl_node = FLNode(
            node_id=org_id,
            local_data=(X_node, y_node),
            model_builder_fn=model_builder,
            epochs_per_round=epochs_per_round,
            batch_size=batch_size,
        )
        node = GossipNode(org_id, fl_node, topology, transport)
        logger.info(
            "Starting TCP P2P org %s on %s:%s, %s rounds, %s local epochs, shape %s, samples %s",
            org_id,
            endpoints[org_id][0],
            endpoints[org_id][1],
            num_rounds,
            epochs_per_round,
            X_node.shape,
            len(X_node),
        )
        history = []
        for round_number in range(1, num_rounds + 1):
            node.publish_local_update(round_number)
            report = node.collect_and_mix(round_number)
            history.append(report)
            logger.info(
                "TCP_RESULT org=%s mixed=%s accepted=%s rejected=%s",
                org_id,
                len(report["accepted"]),
                report["accepted"],
                report["rejected"],
            )
        metrics = node.fl_node.evaluate_on_test(X_test, y_test)
        logger.info("%s hold-out metrics: %s", org_id, metrics)
        if synthetic or real_smoke:
            logger.info("These metrics are not a full CIC-DDoS2019 accuracy result.")
        return {
            "org_id": org_id,
            "rounds": history,
            "probe_metrics": metrics,
            "samples": int(len(X_node)),
            "input_shape": tuple(X_node.shape[1:]),
            "hellos": hellos,
        }
    finally:
        transport.close()


def _prepare_tcp_arrays(config, orgs, seed, synthetic, real_smoke, max_samples, rounds, epochs, training):
    batch_size = int(training.get("batch_size", 64))
    arrays, num_rounds, epochs_per_round, batch_size = _load_run_arrays(
        config, orgs, seed, synthetic, real_smoke, max_samples, rounds, epochs, batch_size
    )
    X_train, y_train, X_test, y_test = arrays
    return X_train, y_train, X_test, y_test, num_rounds, epochs_per_round, batch_size


def run(
    config: dict,
    *,
    transport_name: str,
    seed: int,
    synthetic: bool,
    rounds: int | None,
    epochs: int | None,
    real_smoke: bool = False,
    max_samples: int = 180,
    org_id: str | None = None,
):
    if transport_name == "tcp":
        if not org_id:
            raise SystemExit(
                "TCP mode runs one organization per process. "
                "Pass --org, or launch experiments/federated_learning/run_p2p_tcp.py."
            )
        return run_tcp_organization(
            config,
            org_id=org_id,
            seed=seed,
            synthetic=synthetic,
            rounds=rounds,
            epochs=epochs,
            real_smoke=real_smoke,
            max_samples=max_samples,
        )
    if transport_name != "inprocess":
        raise SystemExit(
            f"Transport {transport_name!r} is not implemented. Use 'inprocess' or 'tcp'."
        )

    training = config.setdefault("training", {})
    training["seed"] = seed
    np.random.seed(seed)

    topology = topology_from_config(config)
    orgs = topology.organizations()
    num_rounds = int(rounds if rounds is not None else training.get("num_rounds", 1))
    epochs_per_round = int(
        epochs if epochs is not None else training.get("epochs_per_round", 1)
    )
    batch_size = int(training.get("batch_size", 64))

    if synthetic:
        logger.info("SYNTHETIC smoke data. This is not a CIC-DDoS2019 experiment.")
        X_train, y_train, X_test, y_test = make_synthetic_arrays(seed, orgs)
        if rounds is None:
            num_rounds = 1
        if epochs is None:
            epochs_per_round = 1
        batch_size = min(batch_size, 16)
    elif real_smoke:
        logger.info("REAL CIC-DDoS2019 in-process smoke test. Not the full experiment.")
        X_train, y_train, X_test, y_test = load_real_smoke_arrays(config, seed, max_samples)
        if rounds is None:
            num_rounds = 1
        if epochs is None:
            epochs_per_round = 1
        batch_size = min(batch_size, 16)
    else:
        X_train, y_train, X_test, y_test = load_cic_arrays(config)

    import tensorflow as tf

    from projects.fl.fl_node_client import FLNode
    from projects.fl.p2p import GossipNode, InProcessTransport
    from projects.shared_libs.data_processor import DataPartitioner

    tf.random.set_seed(seed)

    partitioner = DataPartitioner(
        num_nodes=len(orgs),
        iid=config.get("data", {}).get("distribution", "iid") == "iid",
    )
    parts = partitioner.partition(X_train, y_train)
    num_classes = int(len(np.unique(y_train)))
    if num_classes < 2:
        num_classes = 2
    model_builder = build_model_fn(X_train.shape[1:], num_classes, config.get("model", {}))
    transport = InProcessTransport()

    nodes: list[GossipNode] = []
    for org_id, (X_node, y_node) in zip(orgs, parts):
        fl_node = FLNode(
            node_id=org_id,
            local_data=(X_node, y_node),
            model_builder_fn=model_builder,
            epochs_per_round=epochs_per_round,
            batch_size=batch_size,
        )
        nodes.append(GossipNode(org_id, fl_node, topology, transport))

    logger.info(
        "Starting in-process P2P FL: %s organizations, %s rounds, %s local epochs",
        len(nodes),
        num_rounds,
        epochs_per_round,
    )
    history = []
    for round_number in range(1, num_rounds + 1):
        for node in nodes:
            node.publish_local_update(round_number)
        round_reports = [node.collect_and_mix(round_number) for node in nodes]
        history.append(round_reports)
        logger.info("Completed P2P round %s/%s", round_number, num_rounds)

    probe = nodes[0]
    metrics = probe.fl_node.evaluate_on_test(X_test, y_test)
    if synthetic:
        source = "synthetic smoke test"
    elif real_smoke:
        source = "CIC-DDoS2019 real-data smoke subset"
    else:
        source = "CIC-DDoS2019"
    logger.info("Data source: %s", source)
    logger.info("Train rows: %s, input shape: %s", len(y_train), X_train.shape[1:])
    for org_id, (X_node, _y_node) in zip(orgs, parts):
        logger.info("Organization %s samples: %s shape %s", org_id, len(X_node), X_node.shape)
    logger.info("Probe org %s hold-out metrics: %s", probe.org_id, metrics)
    if synthetic or real_smoke:
        logger.info("These metrics are not a full CIC-DDoS2019 accuracy result.")
    return {
        "source": source,
        "rounds": history,
        "probe_metrics": metrics,
        "train_rows": int(len(y_train)),
        "input_shape": tuple(X_train.shape[1:]),
        "org_samples": {org_id: int(len(X_node)) for org_id, (X_node, _y_node) in zip(orgs, parts)},
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="In-process P2P federated learning")
    parser.add_argument("--transport", default="inprocess", choices=["inprocess", "tcp"])
    parser.add_argument(
        "--org",
        default=None,
        help="Run one organization process. Required when --transport tcp.",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--config", default="config/p2p_fl.yaml")
    parser.add_argument("--rounds", type=int, default=None)
    parser.add_argument("--epochs", type=int, default=None)
    parser.add_argument(
        "--synthetic",
        action="store_true",
        help="Run a small random-tensor smoke test. Does not claim CIC-DDoS2019 results.",
    )
    parser.add_argument(
        "--real-smoke",
        action="store_true",
        help="One in-process round on a small real CIC-DDoS2019 subset. Not the full experiment.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=180,
        help="Row cap for --real-smoke, divided across classes. Ignored by --synthetic.",
    )
    args = parser.parse_args(argv)
    if args.synthetic and args.real_smoke:
        raise SystemExit("Choose either --synthetic or --real-smoke, not both.")

    config_path = _resolve_config(args.config)
    config = _load_config(config_path)
    load_topology(config_path)
    seed = args.seed if args.seed is not None else int(config.get("training", {}).get("seed", 42))
    try:
        run(
            config,
            transport_name=args.transport,
            seed=seed,
            synthetic=args.synthetic,
            rounds=args.rounds,
            epochs=args.epochs,
            real_smoke=args.real_smoke,
            max_samples=args.max_samples,
            org_id=args.org,
        )
    except DatasetUnavailable as exc:
        logger.error("%s", exc)
        raise


if __name__ == "__main__":
    main()
