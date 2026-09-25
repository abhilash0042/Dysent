"""Phase 1 P2P federated learning tests. Synthetic arrays only."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.data.load_cicddos import reshape_for_cnn_bilstm
from projects.fl.p2p.node import size_weighted_pair_mix, validate_peer_update
from projects.fl.p2p.topology import Topology, load_topology
from projects.fl.p2p.transport import InProcessTransport, PeerUpdate
from projects.fl.p2p.node import GossipNode

P2P_SOURCES = [
    ROOT / "projects" / "fl" / "p2p" / "__init__.py",
    ROOT / "projects" / "fl" / "p2p" / "transport.py",
    ROOT / "projects" / "fl" / "p2p" / "topology.py",
    ROOT / "projects" / "fl" / "p2p" / "node.py",
    ROOT / "experiments" / "federated_learning" / "run_p2p.py",
]

RING = {
    "org_campus": ["org_isp", "org_gov"],
    "org_isp": ["org_campus", "org_bank"],
    "org_bank": ["org_isp", "org_cloud"],
    "org_cloud": ["org_bank", "org_gov"],
    "org_gov": ["org_cloud", "org_campus"],
}


class StubFLNode:
    """Duck-typed stand-in for FLNode. Tests do not train a Keras model."""

    def __init__(self, weights, n_samples: int):
        self.local_model = object()
        self.X_local = np.zeros((n_samples, 1))
        self._weights = [np.array(layer, copy=True) for layer in weights]
        self.train_calls = 0

    def initialize_model(self):
        self.local_model = object()

    def train_local_model(self, verbose=0):
        self.train_calls += 1
        return {"loss": 0.0, "accuracy": 1.0}

    def get_model_weights(self):
        return [np.array(layer, copy=True) for layer in self._weights]

    def set_model_weights(self, weights):
        self._weights = [np.array(layer, copy=True) for layer in weights]


def _ring() -> Topology:
    return Topology(RING)


def _update(org_id, weights, n_samples=4, round_number=1, sha256=None) -> PeerUpdate:
    copied = [np.array(layer, copy=True) for layer in weights]
    return PeerUpdate(org_id, round_number, n_samples, copied, sha256)


def test_reshape_forty_features_is_ten_by_four():
    reshaped = reshape_for_cnn_bilstm(np.zeros((2, 40)), timesteps=10)
    assert reshaped.shape == (2, 10, 4)


def test_reshape_preserves_feature_order_and_values():
    rows = np.arange(80, dtype=np.float32).reshape(2, 40)
    reshaped = reshape_for_cnn_bilstm(rows, 10)
    np.testing.assert_array_equal(reshaped.reshape(2, 40), rows)
    np.testing.assert_array_equal(reshaped[0, 0], rows[0, :4])
    np.testing.assert_array_equal(reshaped[0, 1], rows[0, 4:8])
    np.testing.assert_array_equal(reshaped[1, 9], rows[1, 36:40])


def test_reshape_rejects_non_divisible_feature_count():
    with pytest.raises(ValueError, match="not divisible"):
        reshape_for_cnn_bilstm(np.zeros((2, 79)), timesteps=10)


def test_reshape_rejects_non_positive_timesteps():
    rows = np.zeros((2, 40))
    with pytest.raises(ValueError, match="positive integer"):
        reshape_for_cnn_bilstm(rows, 0)
    with pytest.raises(ValueError, match="positive integer"):
        reshape_for_cnn_bilstm(rows, -1)
    with pytest.raises(ValueError, match="positive integer"):
        reshape_for_cnn_bilstm(rows, True)


def test_size_weighted_pair_mix_documented_case():
    mixed = size_weighted_pair_mix(
        [np.array([1.0, 1.0])],
        3,
        [np.array([0.0, 0.0])],
        1,
    )
    np.testing.assert_allclose(mixed[0], np.array([0.75, 0.75]))


def test_size_weighted_pair_mix_multiple_layers():
    local = [np.ones((2, 2)), np.array([1.0, 1.0, 1.0])]
    peer = [np.zeros((2, 2)), np.zeros(3)]
    mixed = size_weighted_pair_mix(local, 3, peer, 1)
    np.testing.assert_allclose(mixed[0], np.full((2, 2), 0.75))
    np.testing.assert_allclose(mixed[1], np.full((3,), 0.75))


def test_equal_counts_are_not_required_for_the_formula():
    mixed = size_weighted_pair_mix(
        [np.array([1.0])],
        1,
        [np.array([0.0])],
        1,
    )
    np.testing.assert_allclose(mixed[0], np.array([0.5]))


def test_topology_allow_list_matches_config():
    topology = load_topology(ROOT / "config" / "p2p_fl.yaml")
    assert topology.organizations() == list(RING)
    for org_id, peers in RING.items():
        assert topology.neighbors(org_id) == peers
        for peer in peers:
            assert topology.is_allowed(org_id, peer)
        assert not topology.is_allowed(org_id, "org_evil")
    assert not topology.is_allowed("org_campus", "org_bank")
    assert not topology.is_allowed("org_campus", "org_campus")


def test_unknown_peer_is_rejected():
    topology = _ring()
    update = _update("org_evil", [np.array([0.0, 0.0])])
    ok, reason = validate_peer_update(
        update,
        receiver_id="org_campus",
        current_round=1,
        topology=topology,
        reference_weights=[np.array([1.0, 1.0])],
    )
    assert not ok
    assert reason == "unknown peer"


def test_round_skew_is_rejected():
    topology = _ring()
    update = _update("org_isp", [np.array([0.0, 0.0])], round_number=8)
    ok, reason = validate_peer_update(
        update,
        receiver_id="org_campus",
        current_round=1,
        topology=topology,
        reference_weights=[np.array([1.0, 1.0])],
    )
    assert not ok
    assert reason == "round skew"


def test_round_difference_of_two_is_allowed():
    topology = _ring()
    update = _update("org_isp", [np.array([0.0, 0.0])], round_number=3)
    ok, reason = validate_peer_update(
        update,
        receiver_id="org_campus",
        current_round=1,
        topology=topology,
        reference_weights=[np.array([1.0, 1.0])],
    )
    assert ok
    assert reason == "ok"


def test_malformed_update_is_rejected():
    topology = _ring()
    reference = [np.array([1.0, 1.0])]
    bad_weights = _update("org_isp", [np.array([0.0, 0.0, 0.0])])
    ok, reason = validate_peer_update(
        bad_weights,
        receiver_id="org_campus",
        current_round=1,
        topology=topology,
        reference_weights=reference,
    )
    assert not ok
    assert reason == "malformed weights"

    not_arrays = PeerUpdate("org_isp", 1, 4, ["nope"])
    ok, reason = validate_peer_update(
        not_arrays,
        receiver_id="org_campus",
        current_round=1,
        topology=topology,
        reference_weights=reference,
    )
    assert not ok
    assert reason == "malformed weights"


def test_invalid_sample_count_is_rejected():
    topology = _ring()
    update = _update("org_isp", [np.array([0.0, 0.0])], n_samples=0)
    ok, reason = validate_peer_update(
        update,
        receiver_id="org_campus",
        current_round=1,
        topology=topology,
        reference_weights=[np.array([1.0, 1.0])],
    )
    assert not ok
    assert reason == "invalid sample count"


def test_inprocess_exchange_mixes_neighbor_weights():
    topology = Topology(
        {
            "org_campus": ["org_isp"],
            "org_isp": ["org_campus"],
        }
    )
    transport = InProcessTransport()
    campus = GossipNode(
        "org_campus",
        StubFLNode([np.array([1.0, 1.0])], n_samples=3),
        topology,
        transport,
    )
    isp = GossipNode(
        "org_isp",
        StubFLNode([np.array([0.0, 0.0])], n_samples=1),
        topology,
        transport,
    )
    campus.publish_local_update(1)
    isp.publish_local_update(1)
    campus_report = campus.collect_and_mix(1)
    isp_report = isp.collect_and_mix(1)

    assert campus_report["accepted"] == ["org_isp"]
    assert isp_report["accepted"] == ["org_campus"]
    assert campus_report["rejected"] == []
    np.testing.assert_allclose(campus.fl_node.get_model_weights()[0], [0.75, 0.75])
    np.testing.assert_allclose(isp.fl_node.get_model_weights()[0], [0.75, 0.75])
    assert transport.pending_count("org_campus") == 0


def test_node_rejects_unlisted_sender_and_keeps_local_weights():
    topology = Topology(
        {
            "org_campus": ["org_isp"],
            "org_isp": ["org_campus"],
        }
    )
    transport = InProcessTransport()
    campus = GossipNode(
        "org_campus",
        StubFLNode([np.array([1.0, 1.0])], n_samples=3),
        topology,
        transport,
    )
    campus.publish_local_update(1)
    transport.receive("org_isp")
    poison = _update("org_evil", [np.array([9.0, 9.0])], n_samples=100)
    transport.send("org_evil", "org_campus", poison)
    report = campus.collect_and_mix(1)
    assert report["accepted"] == []
    assert report["rejected"] == [("org_evil", "unknown peer")]
    np.testing.assert_allclose(campus.fl_node.get_model_weights()[0], [1.0, 1.0])


def test_node_rejects_round_skew_and_malformed_from_a_neighbor():
    topology = Topology(
        {
            "org_campus": ["org_isp"],
            "org_isp": ["org_campus"],
        }
    )
    transport = InProcessTransport()
    campus = GossipNode(
        "org_campus",
        StubFLNode([np.array([1.0, 1.0])], n_samples=3),
        topology,
        transport,
    )
    campus.publish_local_update(1)
    transport.receive("org_isp")
    skewed = _update("org_isp", [np.array([0.0, 0.0])], round_number=9)
    transport.send("org_isp", "org_campus", skewed)
    report = campus.collect_and_mix(1)
    assert report["rejected"] == [("org_isp", "round skew")]
    np.testing.assert_allclose(campus.fl_node.get_model_weights()[0], [1.0, 1.0])


def test_p2p_sources_do_not_reference_the_central_server():
    banned = ("FederatedServer", "SimpleFLServer", "aggregation_server")
    for path in P2P_SOURCES:
        text = path.read_text(encoding="utf-8")
        for token in banned:
            assert token not in text, f"{path.name} contains {token}"
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert "aggregation_server" not in module
                assert "socket" not in module
                for alias in node.names:
                    assert alias.name not in {"FederatedServer", "SimpleFLServer", "socket"}
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != "socket"


def test_importing_p2p_does_not_import_the_central_server():
    import importlib

    imported = importlib.import_module("projects.fl.p2p")
    assert hasattr(imported, "GossipNode")
    loaded = {name for name in sys.modules if "aggregation_server" in name}
    assert loaded == set()


def test_real_cic_inputs_pass_the_dataset_gate():
    loader = ROOT / "scripts" / "data" / "load_cicddos.py"
    assert loader.is_file()
    from experiments.federated_learning.run_p2p import (
        _load_config,
        _resolve_config,
        require_cic_dataset,
    )

    config = _load_config(_resolve_config("config/p2p_fl.yaml"))
    npz = ROOT / config["data"]["processed_npz"]
    selection = ROOT / config["data"]["feature_selection_pkl"]
    assert npz.is_file()
    assert selection.is_file()
    require_cic_dataset(config)


def test_real_cic_smoke_subset_partitions_into_disjoint_orgs():
    from experiments.federated_learning.run_p2p import _load_config, _resolve_config, load_real_smoke_arrays
    from projects.shared_libs.data_processor import DataPartitioner

    config = _load_config(_resolve_config("config/p2p_fl.yaml"))
    X_train, y_train, X_test, y_test = load_real_smoke_arrays(config, seed=42, max_samples=180)

    assert X_train.shape[1:] == (10, 4)
    assert X_test.shape[1:] == (10, 4)
    assert len(X_train) + len(X_test) == 180
    assert len(X_train) < 431371
    assert set(np.unique(y_train)).issubset(set(range(18)))
    assert len(y_train) == len(X_train)

    np.random.seed(42)
    parts = DataPartitioner(num_nodes=5, iid=True).partition(X_train, y_train)
    assert len(parts) == 5
    seen = []
    for X_node, y_node in parts:
        assert X_node.shape[1:] == (10, 4)
        assert len(X_node) == len(y_node)
        assert len(X_node) > 0
        seen.append(len(X_node))
    assert sum(seen) == len(X_train)

    index_rows = np.arange(len(y_train)).reshape(-1, 1)
    np.random.seed(42)
    index_parts = DataPartitioner(num_nodes=5, iid=True).partition(index_rows, y_train)
    flat = np.concatenate([part[0].ravel() for part in index_parts])
    assert len(flat) == len(np.unique(flat)) == len(y_train)
    for (X_node, y_node), (idx, y_idx) in zip(parts, index_parts):
        np.testing.assert_array_equal(y_node, y_idx)
        np.testing.assert_array_equal(y_node, y_train[idx.ravel()])
        np.testing.assert_array_equal(X_node, X_train[idx.ravel()])


def test_runner_reports_missing_cic_data():
    from experiments.federated_learning.run_p2p import DatasetUnavailable, require_cic_dataset

    config = {
        "data": {
            "processed_npz": "data/processed/does_not_exist_cicddos2019_full_processed.npz",
            "use_selected_features": True,
            "feature_selection_pkl": "data/processed/does_not_exist_feature_selection.pkl",
        }
    }
    with pytest.raises(DatasetUnavailable) as caught:
        require_cic_dataset(config)
    message = str(caught.value)
    assert "CIC-DDoS2019" in message
    assert "does_not_exist_cicddos2019_full_processed.npz" in message
    assert "No synthetic dataset was generated" in message
