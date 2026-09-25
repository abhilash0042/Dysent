"""Focused TCP transport tests. They do not train on CIC-DDoS2019."""

from __future__ import annotations

import pickle
import socket
import struct
import sys
import threading
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from projects.fl.p2p.node import GossipNode, validate_peer_update
from projects.fl.p2p.tcp_transport import (
    MAX_MESSAGE_BYTES,
    MessageTooLarge,
    TcpTransport,
    recv_frame,
    send_frame,
)
from projects.fl.p2p.topology import Topology
from projects.fl.p2p.transport import PeerUpdate


class StubFLNode:
    def __init__(self, weights, n_samples: int):
        self.local_model = object()
        self.X_local = np.zeros((n_samples, 1))
        self._weights = [np.array(layer, copy=True) for layer in weights]

    def initialize_model(self):
        self.local_model = object()

    def train_local_model(self, verbose=0):
        return {"loss": 0.0, "accuracy": 1.0}

    def get_model_weights(self):
        return [np.array(layer, copy=True) for layer in self._weights]

    def set_model_weights(self, weights):
        self._weights = [np.array(layer, copy=True) for layer in weights]


def _free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def _pair(timeout: float = 2.0):
    ports = {"org_campus": _free_port(), "org_isp": _free_port()}
    endpoints = {org: ("127.0.0.1", port) for org, port in ports.items()}
    campus = TcpTransport("org_campus", endpoints, ["org_isp"], timeout=timeout)
    isp = TcpTransport("org_isp", endpoints, ["org_campus"], timeout=timeout)
    return campus, isp


def test_two_tcp_peers_complete_hello():
    campus, isp = _pair()
    campus.start()
    isp.start()
    try:
        campus_hello = campus.exchange_hellos()
        isp_hello = isp.exchange_hellos()
        assert campus_hello["org_isp"] is True
        assert isp_hello["org_campus"] is True
    finally:
        campus.close()
        isp.close()


def test_tcp_message_round_trip():
    campus, isp = _pair()
    campus.start()
    isp.start()
    try:
        campus.exchange_hellos()
        update = PeerUpdate("org_campus", 1, 3, [np.array([1.0, 2.0])], sha256="abc")
        campus.send("org_campus", "org_isp", update)
        received = isp.receive("org_isp")
        assert len(received) == 1
        assert received[0].org_id == "org_campus"
        assert received[0].n_samples == 3
        np.testing.assert_allclose(received[0].weights[0], [1.0, 2.0])
    finally:
        campus.close()
        isp.close()


def test_length_prefix_framing():
    message = {"type": "HEARTBEAT", "org_id": "org_campus"}
    payload = pickle.dumps(message, protocol=pickle.HIGHEST_PROTOCOL)
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def accept_header():
        conn, _addr = server.accept()
        try:
            header = conn.recv(4)
            assert header == struct.pack(">I", len(payload))
            body = conn.recv(len(payload))
            assert pickle.loads(body) == message
        finally:
            conn.close()

    thread = threading.Thread(target=accept_header)
    thread.start()
    try:
        client = socket.create_connection(("127.0.0.1", port), timeout=2)
        send_frame(client, message)
        client.close()
        thread.join(timeout=3)
        assert not thread.is_alive()
    finally:
        server.close()


def test_oversized_message_is_rejected():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    caught: list[Exception] = []

    def accept_and_read():
        conn, _addr = server.accept()
        try:
            recv_frame(conn)
        except MessageTooLarge as exc:
            caught.append(exc)
        finally:
            conn.close()

    thread = threading.Thread(target=accept_and_read)
    thread.start()
    try:
        client = socket.create_connection(("127.0.0.1", port), timeout=2)
        client.sendall(struct.pack(">I", MAX_MESSAGE_BYTES + 1))
        client.close()
        thread.join(timeout=3)
    finally:
        server.close()
    assert caught
    assert MAX_MESSAGE_BYTES == 64 * 1024 * 1024


def test_unknown_tcp_sender_is_rejected_by_validation():
    campus, isp = _pair(timeout=1.0)
    campus.start()
    isp.start()
    try:
        node = GossipNode(
            "org_campus",
            StubFLNode([np.array([1.0, 1.0])], 3),
            Topology({"org_campus": ["org_isp"], "org_isp": ["org_campus"]}),
            campus,
        )
        node.publish_local_update(1)
        evil = socket.create_connection(campus.endpoints["org_campus"], timeout=2)
        send_frame(
            evil,
            {
                "type": "GOSSIP_PUSH",
                "org_id": "org_evil",
                "round": 1,
                "n_samples": 9,
                "weights": [np.array([9.0, 9.0])],
                "sha256": None,
            },
        )
        evil.shutdown(socket.SHUT_WR)
        import time
        time.sleep(0.3)
        evil.close()
        report = node.collect_and_mix(1)
        assert ("org_evil", "unknown peer") in report["rejected"]
        assert "org_evil" not in report["accepted"]
        np.testing.assert_allclose(node.fl_node.get_model_weights()[0], [1.0, 1.0])
        ok, reason = validate_peer_update(
            PeerUpdate("org_evil", 1, 9, [np.array([9.0, 9.0])]),
            receiver_id="org_campus",
            current_round=1,
            topology=node.topology,
            reference_weights=[np.array([1.0, 1.0])],
        )
        assert not ok and reason == "unknown peer"
    finally:
        campus.close()
        isp.close()


def test_peer_disconnect_does_not_crash_the_node():
    campus, _isp = _pair(timeout=1.0)
    campus.start()
    try:
        visitor = socket.create_connection(campus.endpoints["org_campus"], timeout=2)
        visitor.close()
        campus.send(
            "org_campus",
            "org_isp",
            PeerUpdate("org_campus", 1, 1, [np.array([0.0])]),
        )
        received = campus.receive("org_campus")
        assert received == []
    finally:
        campus.close()
