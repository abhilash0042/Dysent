"""Pluggable dataplane — swap Mininet OVS vs host nftables without touching the detector."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class BlockRule:
    source_ip: str
    action: str
    attack_class: str
    attack_score: float
    packets_blocked: int = 0
    installed_at: str = ''
    expires_at: str = ''


class EnforcementBackend(ABC):
    @abstractmethod
    def block_ip(self, source_ip: str, ttl_seconds: int = 300, meta: dict | None = None) -> bool:
        ...

    @abstractmethod
    def rate_limit_ip(self, source_ip: str, kbps: int = 500, ttl_seconds: int = 120) -> bool:
        ...

    @abstractmethod
    def revoke(self, source_ip: str) -> bool:
        ...

    @abstractmethod
    def list_rules(self) -> List[BlockRule]:
        ...

    @abstractmethod
    def stats(self) -> Dict:
        ...

    def is_blocked(self, source_ip: str) -> bool:
        return any(r.source_ip == source_ip and r.action == 'drop' for r in self.list_rules())

    def record_drop(self, source_ip: str, packets: int = 0) -> None:
        """Count packets discarded after a block is already installed."""
        return
