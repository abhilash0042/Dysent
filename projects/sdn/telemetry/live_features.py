"""Build the contract's 40 CIC-style features from one second of live packets."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np

from projects.sdn.contract import SDNModelContract


@dataclass
class LivePacket:
    ts: float
    src: str
    dst: str
    length: int
    proto: int = 6
    flags: str = ''
    header_len: int = 40
    window: int = 8192
    payload_len: int = 0


@dataclass
class SourceBucket:
    packets: List[LivePacket] = field(default_factory=list)
    bytes_total: int = 0
    incomplete: int = 0
    complete: int = 0

    def add(self, pkt: LivePacket, incomplete_http: bool | None = None):
        self.packets.append(pkt)
        self.bytes_total += max(0, int(pkt.length))
        if incomplete_http is True:
            self.incomplete += 1
        elif incomplete_http is False:
            self.complete += 1


def _stats(values: np.ndarray) -> tuple[float, float, float, float, float]:
    if values.size == 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0
    return (
        float(values.min()),
        float(values.max()),
        float(values.mean()),
        float(values.std(ddof=0)),
        float(values.var(ddof=0)),
    )


def _iat_us(timestamps: List[float]) -> tuple[float, float, float, float]:
    if len(timestamps) < 2:
        return 0.0, 0.0, 0.0, 0.0
    diffs = np.diff(np.asarray(timestamps, dtype=np.float64)) * 1_000_000.0
    diffs = diffs[diffs >= 0]
    if diffs.size == 0:
        return 0.0, 0.0, 0.0, 0.0
    return float(diffs.mean()), float(diffs.std(ddof=0)), float(diffs.max()), float(diffs.sum())


def features_from_packets(
    packets: List[LivePacket],
    protected_ip: str,
    duration_s: float,
    contract: SDNModelContract,
) -> np.ndarray:
    """Map live packets for one source toward `protected_ip` into a (40,) raw vector."""
    duration_s = max(duration_s, 1e-3)
    fwd = [p for p in packets if p.dst == protected_ip or protected_ip in ('', '*')]
    bwd = [p for p in packets if p.src == protected_ip]
    if not fwd and packets:
        fwd = list(packets)
        bwd = []

    all_len = np.array([p.length for p in packets], dtype=np.float64) if packets else np.zeros(0)
    fwd_len = np.array([p.length for p in fwd], dtype=np.float64) if fwd else np.zeros(0)
    bwd_len = np.array([p.length for p in bwd], dtype=np.float64) if bwd else np.zeros(0)
    pmin, pmax, pmean, pstd, pvar = _stats(all_len)
    fmin, fmax, fmean, _, _ = _stats(fwd_len)
    _, bmax, bmean, _, _ = _stats(bwd_len)

    n = len(packets)
    n_fwd = max(len(fwd), 1 if fwd_len.size else 0)
    n_bwd = len(bwd)
    bytes_total = float(all_len.sum()) if all_len.size else 0.0
    fwd_bytes = float(fwd_len.sum()) if fwd_len.size else 0.0

    flow_iat_mean, flow_iat_std, flow_iat_max, _ = _iat_us([p.ts for p in packets])
    fwd_iat_mean, fwd_iat_std, fwd_iat_max, fwd_iat_total = _iat_us([p.ts for p in fwd])
    bwd_iat_mean, _, bwd_iat_max, _ = _iat_us([p.ts for p in bwd])

    ack = sum(1 for p in fwd if 'A' in (p.flags or '').upper())
    urg = sum(1 for p in fwd if 'U' in (p.flags or '').upper())
    data_pkts = sum(1 for p in fwd if p.payload_len > 0)
    proto = int(fwd[0].proto) if fwd else 6
    init_win = int(fwd[0].window) if fwd else 8192
    fwd_hdr = float(sum(p.header_len for p in fwd))
    bwd_hdr = float(sum(p.header_len for p in bwd))
    duration_us = duration_s * 1_000_000.0

    raw = {
        'Packet Length Min': pmin,
        'Avg Fwd Segment Size': fmean,
        'Fwd Packet Length Mean': fmean,
        'Fwd Packet Length Min': fmin,
        'Avg Packet Size': pmean,
        'Packet Length Mean': pmean,
        'Fwd Packet Length Max': fmax,
        'Flow Bytes/s': bytes_total / duration_s,
        'Fwd Packets/s': n_fwd / duration_s,
        'Fwd IAT Mean': fwd_iat_mean,
        'Flow Packets/s': n / duration_s if n else 0.0,
        'Flow IAT Mean': flow_iat_mean,
        'Packet Length Max': pmax,
        'Flow IAT Std': flow_iat_std,
        'Flow Duration': duration_us,
        'Fwd IAT Max': fwd_iat_max,
        'Fwd Act Data Packets': float(data_pkts),
        'Fwd Packets Length Total': fwd_bytes,
        'Fwd IAT Std': fwd_iat_std,
        'Subflow Fwd Packets': float(n_fwd),
        'Flow IAT Max': flow_iat_max,
        'Fwd IAT Total': fwd_iat_total,
        'Subflow Fwd Bytes': fwd_bytes,
        'ACK Flag Count': float(ack),
        'Total Fwd Packets': float(n_fwd),
        'Protocol': float(proto),
        'Init Fwd Win Bytes': float(init_win),
        'Bwd IAT Mean': bwd_iat_mean,
        'Idle Std': 0.0,
        'Idle Max': 0.0,
        'Packet Length Std': pstd,
        'Bwd Packets/s': n_bwd / duration_s,
        'Bwd IAT Max': bwd_iat_max,
        'Packet Length Variance': pvar,
        'URG Flag Count': float(urg),
        'Avg Bwd Segment Size': bmean,
        'Fwd Header Length': fwd_hdr,
        'Bwd Packet Length Max': bmax,
        'Bwd Header Length': bwd_hdr,
        'Subflow Bwd Packets': float(n_bwd),
    }
    vec = np.array([raw.get(name, 0.0) for name in contract.feature_names], dtype=np.float32)
    return np.nan_to_num(vec, nan=0.0, posinf=0.0, neginf=0.0)
