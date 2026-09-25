"""Localhost TCP transport for one organization process.

GossipNode only calls Transport.send and Transport.receive. Framing matches
the repository's Mininet helpers: a 4-byte big-endian length followed by a
pickled payload. This module does not open a central coordinator.
"""

from __future__ import annotations

import logging
import pickle
import socket
import struct
import threading
import time
from typing import Any

from projects.fl.p2p.transport import PeerUpdate, Transport

logger = logging.getLogger(__name__)

MAX_MESSAGE_BYTES = 64 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 15.0
HEARTBEAT_INTERVAL_SECONDS = 5.0
# Live neighbors may still be training. Idle timeout stays 15s without a
# heartbeat; this cap only stops a process that would otherwise wait forever.
ROUND_WAIT_CAP_SECONDS = 180.0

MESSAGE_TYPES = (
    "HELLO",
    "HELLO_ACK",
    "GOSSIP_PUSH",
    "GOSSIP_PULL",
    "NACK",
    "HEARTBEAT",
    "BYE",
)


class MessageTooLarge(ValueError):
    """Framed payload exceeds MAX_MESSAGE_BYTES."""


def send_frame(sock: socket.socket, message: dict) -> None:
    """Send one length-prefixed pickled message."""
    payload = pickle.dumps(message, protocol=pickle.HIGHEST_PROTOCOL)
    if len(payload) > MAX_MESSAGE_BYTES:
        raise MessageTooLarge(
            f"Message is {len(payload)} bytes; limit is {MAX_MESSAGE_BYTES}"
        )
    sock.sendall(struct.pack(">I", len(payload)) + payload)


def recv_frame(sock: socket.socket, max_bytes: int = MAX_MESSAGE_BYTES) -> dict | None:
    """Read one length-prefixed message. Rejects oversized lengths before the body."""
    raw_length = _recvall(sock, 4)
    if raw_length is None:
        return None
    length = struct.unpack(">I", raw_length)[0]
    if length > max_bytes:
        raise MessageTooLarge(f"Refusing {length} byte message; limit is {max_bytes}")
    if length == 0:
        raise ValueError("Refusing empty framed message")
    body = _recvall(sock, length)
    if body is None:
        raise ConnectionError("Connection closed before the framed body arrived")
    message = pickle.loads(body)
    if not isinstance(message, dict) or message.get("type") not in MESSAGE_TYPES:
        raise ValueError(f"Malformed TCP message: {message!r}")
    return message


def _recvall(sock: socket.socket, nbytes: int) -> bytes | None:
    chunks = bytearray()
    while len(chunks) < nbytes:
        packet = sock.recv(nbytes - len(chunks))
        if not packet:
            return None if not chunks else None
        chunks.extend(packet)
    return bytes(chunks)


def update_to_message(update: PeerUpdate) -> dict:
    return {
        "type": "GOSSIP_PUSH",
        "org_id": update.org_id,
        "round": update.round,
        "n_samples": update.n_samples,
        "weights": [layer for layer in update.weights],
        "sha256": update.sha256,
    }


def message_to_update(message: dict) -> PeerUpdate:
    return PeerUpdate(
        org_id=str(message["org_id"]),
        round=message["round"],
        n_samples=message["n_samples"],
        weights=list(message["weights"]),
        sha256=message.get("sha256"),
    )


class TcpTransport(Transport):
    """One organization's TCP endpoint. Not a central server."""

    def __init__(
        self,
        org_id: str,
        endpoints: dict[str, tuple[str, int]],
        neighbors: list[str],
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ):
        if org_id not in endpoints:
            raise KeyError(f"No TCP endpoint configured for {org_id}")
        self.org_id = org_id
        self.endpoints = dict(endpoints)
        self.neighbors = list(neighbors)
        self.timeout = float(timeout)
        self.hello_acks: set[str] = set()
        self._inbox: list[PeerUpdate] = []
        self._latest: PeerUpdate | None = None
        self._last_seen: dict[str, float] = {}
        self._unavailable: set[str] = set()
        self._lock = threading.Lock()
        self._cv = threading.Condition(self._lock)
        self._stop = threading.Event()
        self._server: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None
        self._heartbeat_thread: threading.Thread | None = None

    def start(self) -> None:
        host, port = self.endpoints[self.org_id]
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(8)
        server.settimeout(1.0)
        self._server = server
        self._stop.clear()
        self._accept_thread = threading.Thread(
            target=self._accept_loop, name=f"{self.org_id}-accept", daemon=True
        )
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, name=f"{self.org_id}-heartbeat", daemon=True
        )
        self._accept_thread.start()
        self._heartbeat_thread.start()
        logger.info("%s listening on %s:%s", self.org_id, host, port)

    def exchange_hellos(self) -> dict[str, bool]:
        """Retry HELLO until each neighbor answers or the timeout elapses."""
        pending = set(self.neighbors)
        deadline = time.monotonic() + self.timeout
        while pending and time.monotonic() < deadline:
            for peer in list(pending):
                reply = self._exchange(peer, {"type": "HELLO", "org_id": self.org_id}, expect_reply=True)
                if reply and reply.get("type") == "HELLO_ACK" and reply.get("org_id") == peer:
                    pending.discard(peer)
                    with self._cv:
                        self.hello_acks.add(peer)
                        self._last_seen[peer] = time.monotonic()
                        self._cv.notify_all()
                    logger.info("%s HELLO_ACK from %s", self.org_id, peer)
            if pending:
                time.sleep(0.2)
        for peer in pending:
            self._mark_unavailable(peer, "HELLO failed")
        return {peer: peer in self.hello_acks for peer in self.neighbors}

    def send(self, sender_id: str, recipient_id: str, update: PeerUpdate) -> None:
        if update.org_id != sender_id:
            raise ValueError(
                f"Update org_id {update.org_id!r} does not match sender {sender_id!r}"
            )
        copied = update.copy()
        with self._cv:
            self._latest = copied
        try:
            self._exchange(recipient_id, update_to_message(copied), expect_reply=False)
            logger.info("%s pushed gossip to %s", sender_id, recipient_id)
        except (OSError, MessageTooLarge, TimeoutError) as exc:
            self._mark_unavailable(recipient_id, f"push failed: {exc}")

    def receive(self, org_id: str) -> list[PeerUpdate]:
        """Wait for neighbor gossip. A silent neighbor is dropped after the timeout."""
        if org_id != self.org_id:
            logger.warning("%s receive called for %s", self.org_id, org_id)
        started = time.monotonic()
        while (time.monotonic() - started) < ROUND_WAIT_CAP_SECONDS:
            with self._cv:
                arrived = {item.org_id for item in self._inbox}
            needed = [
                peer
                for peer in self.neighbors
                if peer not in arrived and peer not in self._unavailable
            ]
            if not needed:
                break
            now = time.monotonic()
            silent = [
                peer
                for peer in needed
                if now - self._last_seen.get(peer, started) >= self.timeout
            ]
            for peer in silent:
                self._mark_unavailable(peer, f"no contact for {self.timeout:.0f}s")
            if silent:
                continue
            self._pull_missing(set(needed))
            with self._cv:
                self._cv.wait(timeout=0.5)
        with self._cv:
            pending = []
            seen_orgs: set[str] = set()
            for item in self._inbox:
                if item.org_id in seen_orgs:
                    continue
                seen_orgs.add(item.org_id)
                pending.append(item)
            self._inbox.clear()
        logger.info(
            "%s received %s TCP update(s); unavailable %s",
            self.org_id,
            len(pending),
            sorted(self._unavailable),
        )
        return [item.copy() for item in pending]

    def close(self) -> None:
        for peer in self.neighbors:
            try:
                self._exchange(peer, {"type": "BYE", "org_id": self.org_id}, expect_reply=False)
            except (OSError, MessageTooLarge, TimeoutError):
                pass
        self._stop.set()
        server = self._server
        self._server = None
        if server is not None:
            try:
                server.close()
            except OSError:
                pass
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=2)
        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=2)
        logger.info("%s TCP transport closed", self.org_id)

    def _mark_unavailable(self, peer: str, reason: str) -> None:
        with self._cv:
            self._unavailable.add(peer)
            self._cv.notify_all()
        logger.warning("%s peer %s unavailable: %s", self.org_id, peer, reason)

    def _pull_missing(self, needed: set[str]) -> None:
        for peer in list(needed):
            try:
                reply = self._exchange(
                    peer,
                    {"type": "GOSSIP_PULL", "org_id": self.org_id, "round": None},
                    expect_reply=True,
                )
            except (OSError, MessageTooLarge, TimeoutError):
                continue
            if not reply:
                continue
            if reply.get("type") == "GOSSIP_PUSH":
                self._store_push(reply)
            elif reply.get("type") == "NACK":
                logger.info("%s pull from %s got NACK: %s", self.org_id, peer, reply.get("reason"))

    def _exchange(self, recipient_id: str, message: dict, expect_reply: bool) -> dict | None:
        if recipient_id not in self.endpoints:
            raise KeyError(f"No TCP endpoint for {recipient_id}")
        host, port = self.endpoints[recipient_id]
        sock = socket.create_connection((host, port), timeout=self.timeout)
        try:
            sock.settimeout(self.timeout)
            send_frame(sock, message)
            if not expect_reply:
                return None
            return recv_frame(sock)
        finally:
            sock.close()

    def _accept_loop(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                conn, _addr = self._server.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            worker = threading.Thread(
                target=self._handle_connection, args=(conn,), daemon=True
            )
            worker.start()

    def _handle_connection(self, conn: socket.socket) -> None:
        try:
            conn.settimeout(self.timeout)
            message = recv_frame(conn)
            if message is None:
                return
            reply = self._dispatch(message)
            if reply is not None:
                send_frame(conn, reply)
        except MessageTooLarge as exc:
            logger.warning("%s rejected oversized TCP message: %s", self.org_id, exc)
            try:
                send_frame(conn, {"type": "NACK", "org_id": self.org_id, "reason": "oversized"})
            except (OSError, MessageTooLarge):
                pass
        except (OSError, TimeoutError, ValueError, pickle.UnpicklingError) as exc:
            logger.warning("%s dropped a TCP connection: %s", self.org_id, exc)
        finally:
            try:
                conn.close()
            except OSError:
                pass

    def _dispatch(self, message: dict) -> dict | None:
        kind = message.get("type")
        sender = str(message.get("org_id", ""))
        if kind == "HELLO":
            self._touch(sender)
            if sender not in self.neighbors and sender != self.org_id:
                return {"type": "NACK", "org_id": self.org_id, "reason": "unknown peer"}
            return {"type": "HELLO_ACK", "org_id": self.org_id}
        if kind == "HELLO_ACK":
            self._touch(sender)
            with self._cv:
                self.hello_acks.add(sender)
                self._cv.notify_all()
            return None
        if kind == "GOSSIP_PUSH":
            self._touch(sender)
            self._store_push(message)
            return None
        if kind == "GOSSIP_PULL":
            self._touch(sender)
            with self._cv:
                latest = None if self._latest is None else self._latest.copy()
            if latest is None:
                return {"type": "NACK", "org_id": self.org_id, "reason": "no update yet"}
            if sender not in self.neighbors:
                return {"type": "NACK", "org_id": self.org_id, "reason": "unknown peer"}
            return update_to_message(latest)
        if kind == "HEARTBEAT":
            self._touch(sender)
            return {"type": "HEARTBEAT", "org_id": self.org_id}
        if kind == "BYE":
            self._touch(sender)
            logger.info("%s received BYE from %s", self.org_id, sender)
            return None
        if kind == "NACK":
            self._touch(sender)
            logger.info("%s received NACK from %s: %s", self.org_id, sender, message.get("reason"))
            return None
        return {"type": "NACK", "org_id": self.org_id, "reason": "unsupported"}

    def _store_push(self, message: dict) -> None:
        try:
            update = message_to_update(message)
        except (KeyError, TypeError) as exc:
            logger.warning("%s ignored malformed gossip: %s", self.org_id, exc)
            return
        with self._cv:
            self._inbox.append(update.copy())
            self._last_seen[update.org_id] = time.monotonic()
            self._cv.notify_all()

    def _touch(self, sender: str) -> None:
        if not sender:
            return
        with self._cv:
            self._last_seen[sender] = time.monotonic()
            self._cv.notify_all()

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(HEARTBEAT_INTERVAL_SECONDS):
            for peer in self.neighbors:
                if peer in self._unavailable:
                    continue
                try:
                    reply = self._exchange(
                        peer,
                        {"type": "HEARTBEAT", "org_id": self.org_id},
                        expect_reply=True,
                    )
                    if reply and reply.get("type") == "HEARTBEAT":
                        self._touch(peer)
                except (OSError, MessageTooLarge, TimeoutError, ValueError):
                    continue


def endpoints_from_config(config: dict[str, Any]) -> dict[str, tuple[str, int]]:
    """Map organization ids to host/port. Defaults are the Phase 3 localhost ring."""
    tcp_cfg = config.get("tcp") or {}
    host = str(tcp_cfg.get("host", "127.0.0.1"))
    default_ports = {
        "org_campus": 9101,
        "org_isp": 9102,
        "org_bank": 9103,
        "org_cloud": 9104,
        "org_gov": 9105,
    }
    endpoints: dict[str, tuple[str, int]] = {}
    for org_id, body in config.get("organizations", {}).items():
        port = default_ports.get(org_id)
        if isinstance(body, dict) and body.get("port") is not None:
            port = int(body["port"])
        if port is None:
            raise KeyError(f"{org_id} has no TCP port")
        endpoints[str(org_id)] = (host, port)
    return endpoints
