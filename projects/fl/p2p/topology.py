"""Permissioned static neighbor graph for P2P federated learning."""

from __future__ import annotations

from pathlib import Path
from typing import Mapping

import yaml


class TopologyError(ValueError):
    """Neighbor graph is missing, unknown, or not an allow-list."""


class Topology:
    """Static allow-list. Acceptance is decided only from configured neighbors."""

    def __init__(self, neighbors: Mapping[str, list[str]]):
        graph = {org_id: list(peers) for org_id, peers in neighbors.items()}
        self._validate(graph)
        self._neighbors = graph

    @staticmethod
    def _validate(graph: dict[str, list[str]]) -> None:
        if not graph:
            raise TopologyError("Topology has no organizations")
        for org_id, peers in graph.items():
            if not org_id or not isinstance(org_id, str):
                raise TopologyError(f"Invalid organization id: {org_id!r}")
            if org_id in peers:
                raise TopologyError(f"{org_id} cannot list itself as a neighbor")
            unknown = [peer for peer in peers if peer not in graph]
            if unknown:
                raise TopologyError(
                    f"{org_id} lists unknown organizations: {unknown}"
                )
            if len(peers) != len(set(peers)):
                raise TopologyError(f"{org_id} has duplicate neighbors")
        for org_id, peers in graph.items():
            for peer in peers:
                if org_id not in graph[peer]:
                    raise TopologyError(
                        f"Neighbor link is not mutual: {org_id} -> {peer}"
                    )

    def organizations(self) -> list[str]:
        return list(self._neighbors)

    def neighbors(self, org_id: str) -> list[str]:
        self._require_org(org_id)
        return list(self._neighbors[org_id])

    def is_allowed(self, receiver_id: str, sender_id: str) -> bool:
        """True only when sender_id is on receiver_id's configured neighbor list."""
        self._require_org(receiver_id)
        return sender_id in self._neighbors[receiver_id]

    def _require_org(self, org_id: str) -> None:
        if org_id not in self._neighbors:
            raise TopologyError(f"Unknown organization: {org_id}")


def topology_from_config(config: Mapping) -> Topology:
    raw = config.get("organizations")
    if not isinstance(raw, Mapping) or not raw:
        raise TopologyError("config is missing organizations")
    neighbors: dict[str, list[str]] = {}
    for org_id, body in raw.items():
        if not isinstance(body, Mapping) or "neighbors" not in body:
            raise TopologyError(f"{org_id} is missing a neighbors list")
        peers = body["neighbors"]
        if not isinstance(peers, list):
            raise TopologyError(f"{org_id} neighbors must be a list")
        neighbors[str(org_id)] = [str(peer) for peer in peers]
    return Topology(neighbors)


def load_topology(path: str | Path) -> Topology:
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    if not isinstance(config, Mapping):
        raise TopologyError(f"Topology config is empty: {config_path}")
    return topology_from_config(config)
