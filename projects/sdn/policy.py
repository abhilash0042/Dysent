"""Map model output + telemetry to a mitigation action."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from projects.sdn.contract import SDNModelContract
from projects.sdn.detector import DetectionAlert


class ActionType(str, Enum):
    NONE = 'none'
    LOG = 'log'
    RATE_LIMIT = 'rate_limit'
    BLOCK = 'block'


@dataclass
class MitigationAction:
    action: ActionType
    source_ip: str
    attack_class: str
    attack_score: float
    pps: float
    reason: str
    ttl_seconds: int = 300


class MitigationPolicy:
    """
    Two-stage gate (matches the training plan):
      1. Telemetry — is pps above baseline?
      2. Model — attack_score = 1 - p(Benign)
    """

    def __init__(self, contract: SDNModelContract, volumetric_multiplier: float = 3.0):
        self.c = contract
        self.volumetric_multiplier = volumetric_multiplier

    def decide(self, alert: DetectionAlert) -> MitigationAction:
        ip = alert.source_ip
        score = alert.attack_score
        pps = alert.pps
        cls = alert.attack_class
        vol = self.c.pps_threshold * self.volumetric_multiplier
        slow = (
            alert.incomplete_ratio >= 0.5
            and alert.concurrent >= 8
        )

        if pps >= vol:
            return MitigationAction(
                ActionType.BLOCK, ip, cls, score, pps,
                f'Volumetric flood ({pps:.0f} >= {vol:.0f} events/s)',
                ttl_seconds=300,
            )

        if slow:
            return MitigationAction(
                ActionType.BLOCK, ip, cls, max(score, 0.85), pps,
                f'Slowloris-style hold (incomplete={alert.incomplete_ratio:.0%}, '
                f'concurrent={alert.concurrent}, iat={alert.mean_iat_us:.0f}us)',
                ttl_seconds=180,
            )

        # Quiet browsing must stay up even if CIC features look like an attack class.
        if pps < self.c.pps_threshold:
            return MitigationAction(
                ActionType.NONE, ip, cls, score, pps,
                f'Normal rate ({pps:.0f}<{self.c.pps_threshold:.0f} events/s) — allow',
            )

        if score >= self.c.block_threshold and pps >= self.c.pps_threshold:
            return MitigationAction(
                ActionType.BLOCK, ip, cls, score, pps,
                f'High confidence attack ({score:.2f}) at {pps:.0f} pps',
                ttl_seconds=300,
            )

        if score >= self.c.alert_threshold:
            # Lab dataplane: RATE_LIMIT still forwarded. Promote to BLOCK
            # so Discarded increments and the protected app stays up.
            return MitigationAction(
                ActionType.BLOCK, ip, cls, score, pps,
                f'Suspicious ({score:.2f}) — block (lab discard, not rate-limit)',
                ttl_seconds=180,
            )

        if score >= self.c.rate_limit_threshold:
            return MitigationAction(
                ActionType.LOG, ip, cls, score, pps,
                f'Watch ({score:.2f})',
            )

        return MitigationAction(
            ActionType.NONE, ip, cls, score, pps, 'Benign-looking',
        )
