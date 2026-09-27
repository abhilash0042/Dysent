"""PCMI v1: signed, canonical, checkable mitigation intent.

v1 intentionally uses SHA-256 commitment + public clipping + Ed25519.
It is NOT a zero-knowledge proof.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
import base64, hashlib, json, time, uuid
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.exceptions import InvalidSignature

@dataclass
class PCMI:
    victim_ip: str
    match: dict
    action: str
    ttl: int
    idle_timeout: int
    confidence: float
    collateral_est: float
    model_commit: str
    issuer_id: str
    timestamp: float
    nonce: str
    update_norm: float
    clip_bound: float
    signature: str = ''


def canonical_payload(pcmi: PCMI) -> bytes:
    d = asdict(pcmi); d.pop('signature', None)
    return json.dumps(d, sort_keys=True, separators=(',', ':')).encode()


def commit_update(delta_weights, round_id: int, node_id: str) -> str:
    h = hashlib.sha256()
    for w in delta_weights:
        h.update(__import__('numpy').ascontiguousarray(w).tobytes())
    h.update(str(round_id).encode()); h.update(b'|'); h.update(node_id.encode())
    return h.hexdigest()


def create_pcmi(**kwargs) -> PCMI:
    kwargs.setdefault('ttl', 300); kwargs.setdefault('idle_timeout', 60)
    kwargs.setdefault('timestamp', time.time()); kwargs.setdefault('nonce', uuid.uuid4().hex)
    kwargs.setdefault('update_norm', 0.0); kwargs.setdefault('clip_bound', 1.0)
    return PCMI(**kwargs)


def sign_pcmi(pcmi: PCMI, private_key: Ed25519PrivateKey) -> PCMI:
    pcmi.signature = base64.b64encode(private_key.sign(canonical_payload(pcmi))).decode()
    return pcmi


def verify_pcmi(pcmi: PCMI, public_key: Ed25519PublicKey, max_age: float = 60.0) -> tuple[bool, str]:
    if pcmi.action not in {'drop', 'meter', 'sinkhole'}:
        return False, 'invalid_action'
    if pcmi.update_norm > pcmi.clip_bound:
        return False, 'clip_bound_exceeded'
    if abs(time.time() - pcmi.timestamp) > max_age:
        return False, 'expired'
    try:
        public_key.verify(base64.b64decode(pcmi.signature), canonical_payload(pcmi))
    except (InvalidSignature, ValueError, TypeError):
        return False, 'invalid_signature'
    return True, 'accepted'
