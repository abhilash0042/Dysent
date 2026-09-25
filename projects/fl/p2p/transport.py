"""Transport interface for P2P weight exchange.

Gossip nodes depend on this interface only. Phase 1 delivers updates in-process.
A later TCP transport can implement the same send/receive methods.
"""

from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass

import numpy as np


@dataclass
class PeerUpdate:
    """One organization's model update for a gossip round.

    sha256 is an integrity field for later phases. Phase 1 does not sign updates
    or provide cryptographic authentication.
    """

    org_id: str
    round: int
    n_samples: int
    weights: list
    sha256: str | None = None

    def copy(self) -> PeerUpdate:
        return PeerUpdate(
            org_id=self.org_id,
            round=self.round,
            n_samples=self.n_samples,
            weights=[np.array(layer, copy=True) for layer in self.weights],
            sha256=self.sha256,
        )


def weight_sha256(weights: list) -> str:
    """Hash a Keras-style weight list. Not an authenticity check."""
    digest = hashlib.sha256()
    for layer in weights:
        array = np.ascontiguousarray(layer)
        digest.update(str(array.shape).encode("utf-8"))
        digest.update(str(array.dtype).encode("utf-8"))
        digest.update(array.tobytes())
    return digest.hexdigest()


class Transport(ABC):
    """Organization-to-organization update delivery."""

    @abstractmethod
    def send(self, sender_id: str, recipient_id: str, update: PeerUpdate) -> None:
        """Deliver one update from sender_id to recipient_id."""

    @abstractmethod
    def receive(self, org_id: str) -> list[PeerUpdate]:
        """Return pending updates addressed to org_id and clear that inbox."""


class InProcessTransport(Transport):
    """Queue-backed transport. No sockets."""

    def __init__(self) -> None:
        self._inbox: dict[str, list[PeerUpdate]] = defaultdict(list)

    def send(self, sender_id: str, recipient_id: str, update: PeerUpdate) -> None:
        if update.org_id != sender_id:
            raise ValueError(
                f"Update org_id {update.org_id!r} does not match sender {sender_id!r}"
            )
        self._inbox[recipient_id].append(update.copy())

    def receive(self, org_id: str) -> list[PeerUpdate]:
        pending = self._inbox.pop(org_id, [])
        return [item.copy() for item in pending]

    def pending_count(self, org_id: str) -> int:
        return len(self._inbox.get(org_id, []))
