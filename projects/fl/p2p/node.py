"""P2P gossip node. Local training is delegated to the existing FLNode."""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from projects.fl.p2p.topology import Topology
from projects.fl.p2p.transport import PeerUpdate, Transport, weight_sha256

logger = logging.getLogger(__name__)

ROUND_SKEW_LIMIT = 2


def size_weighted_pair_mix(
    w_self: list,
    n_self: int,
    w_peer: list,
    n_peer: int,
) -> list:
    """Sample-size-weighted average of two full Keras weight lists.

    mixed = (n_self * w_self + n_peer * w_peer) / (n_self + n_peer)

    Every array is mixed, including non-trainable BatchNorm parameters, matching
    the arrays that centralized FedAvg averages via Keras get_weights().
    """
    if n_self <= 0 or n_peer <= 0:
        raise ValueError("Sample counts must be positive")
    if len(w_self) != len(w_peer) or len(w_self) == 0:
        raise ValueError(
            f"Weight lists differ in length: {len(w_self)} vs {len(w_peer)}"
        )

    total = float(n_self + n_peer)
    mixed = []
    for index, (local, peer) in enumerate(zip(w_self, w_peer)):
        local_array = np.asarray(local)
        peer_array = np.asarray(peer)
        if local_array.shape != peer_array.shape:
            raise ValueError(
                f"Shape mismatch at index {index}: "
                f"{local_array.shape} vs {peer_array.shape}"
            )
        mixed.append((n_self * local_array + n_peer * peer_array) / total)
    return mixed


def _valid_sample_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _weights_match_reference(weights: Any, reference: list | None) -> str | None:
    if not isinstance(weights, list) or len(weights) == 0:
        return "malformed weights"
    for layer in weights:
        if not isinstance(layer, np.ndarray):
            return "malformed weights"
    if reference is None:
        return None
    if len(weights) != len(reference):
        return "malformed weights"
    for layer, expected in zip(weights, reference):
        if layer.shape != np.asarray(expected).shape:
            return "malformed weights"
    return None


def validate_peer_update(
    update: PeerUpdate,
    *,
    receiver_id: str,
    current_round: int,
    topology: Topology,
    reference_weights: list | None = None,
) -> tuple[bool, str]:
    """Accept a neighbor update or return a short rejection reason.

    Rejects unknown peers, round skew greater than 2, bad sample counts,
    malformed weight lists, and a sha256 field that does not match the bytes.
    """
    if not isinstance(update, PeerUpdate) or not update.org_id:
        return False, "malformed update"
    if not topology.is_allowed(receiver_id, update.org_id):
        return False, "unknown peer"
    if not isinstance(update.round, int) or isinstance(update.round, bool):
        return False, "malformed update"
    if abs(update.round - current_round) > ROUND_SKEW_LIMIT:
        return False, "round skew"
    if not _valid_sample_count(update.n_samples):
        return False, "invalid sample count"
    weight_error = _weights_match_reference(update.weights, reference_weights)
    if weight_error:
        return False, weight_error
    if update.sha256 is not None and update.sha256 != weight_sha256(update.weights):
        return False, "weight hash mismatch"
    return True, "ok"


class GossipNode:
    """One organization. Trains with FLNode and mixes neighbor weights.

    This class does not know about sockets. Delivery goes through Transport.
    """

    def __init__(self, org_id: str, fl_node: Any, topology: Topology, transport: Transport):
        topology.neighbors(org_id)
        self.org_id = org_id
        self.fl_node = fl_node
        self.topology = topology
        self.transport = transport
        self._round_weights: list | None = None
        self._n_samples: int | None = None

    def publish_local_update(self, round_number: int) -> PeerUpdate:
        """Train on local data and send the resulting weights to neighbors."""
        if self.fl_node.local_model is None:
            self.fl_node.initialize_model()

        self.fl_node.train_local_model(verbose=0)
        weights = [np.array(layer, copy=True) for layer in self.fl_node.get_model_weights()]
        n_samples = int(len(self.fl_node.X_local))
        if n_samples <= 0:
            raise ValueError(f"{self.org_id} has no local samples")

        update = PeerUpdate(
            org_id=self.org_id,
            round=round_number,
            n_samples=n_samples,
            weights=weights,
            sha256=weight_sha256(weights),
        )
        self._round_weights = weights
        self._n_samples = n_samples

        for neighbor_id in self.topology.neighbors(self.org_id):
            self.transport.send(self.org_id, neighbor_id, update)

        logger.info(
            "%s published round %s update (%s samples, %s neighbors)",
            self.org_id,
            round_number,
            n_samples,
            len(self.topology.neighbors(self.org_id)),
        )
        return update

    def collect_and_mix(self, round_number: int) -> dict:
        """Validate inbox updates, mix accepted neighbor weights, install them."""
        if self._round_weights is None or self._n_samples is None:
            raise RuntimeError(f"{self.org_id} must publish before mixing")

        accepted: list[PeerUpdate] = []
        rejected: list[tuple[str, str]] = []
        seen: set[str] = set()

        for update in self.transport.receive(self.org_id):
            sender = getattr(update, "org_id", "")
            if sender in seen:
                rejected.append((str(sender), "duplicate peer"))
                continue
            ok, reason = validate_peer_update(
                update,
                receiver_id=self.org_id,
                current_round=round_number,
                topology=self.topology,
                reference_weights=self._round_weights,
            )
            if not ok:
                rejected.append((str(sender), reason))
                logger.info("%s rejected %s: %s", self.org_id, sender, reason)
                continue
            seen.add(sender)
            accepted.append(update)

        mixed = [np.array(layer, copy=True) for layer in self._round_weights]
        running_count = self._n_samples
        for update in accepted:
            mixed = size_weighted_pair_mix(
                mixed, running_count, update.weights, update.n_samples
            )
            running_count += update.n_samples

        self.fl_node.set_model_weights(mixed)
        self._round_weights = [np.array(layer, copy=True) for layer in mixed]

        logger.info(
            "%s round %s mixed %s neighbor update(s), rejected %s",
            self.org_id,
            round_number,
            len(accepted),
            len(rejected),
        )
        return {
            "org_id": self.org_id,
            "round": round_number,
            "accepted": [update.org_id for update in accepted],
            "rejected": rejected,
            "n_samples": self._n_samples,
            "mixed_sample_count": running_count,
        }
