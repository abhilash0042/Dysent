"""In-process peer-to-peer federated learning.

This package does not use a central aggregation server.
"""

from projects.fl.p2p.node import GossipNode, size_weighted_pair_mix, validate_peer_update
from projects.fl.p2p.topology import Topology, load_topology, topology_from_config
from projects.fl.p2p.tcp_transport import TcpTransport
from projects.fl.p2p.transport import InProcessTransport, PeerUpdate, Transport, weight_sha256

__all__ = [
    "GossipNode",
    "InProcessTransport",
    "PeerUpdate",
    "TcpTransport",
    "Topology",
    "Transport",
    "load_topology",
    "size_weighted_pair_mix",
    "topology_from_config",
    "validate_peer_update",
    "weight_sha256",
]
