"""In-memory enforcement for Windows / dry-run demos."""

from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, List

from projects.sdn.enforcement.base import BlockRule, EnforcementBackend


class SimulationBackend(EnforcementBackend):
    def __init__(self):
        self._blocks: Dict[str, BlockRule] = {}
        self._limits: Dict[str, BlockRule] = {}
        self.packets_blocked_total = 0

    def block_ip(self, source_ip: str, ttl_seconds: int = 300, meta: dict | None = None) -> bool:
        now = datetime.utcnow()
        meta = meta or {}
        packets = int(meta.get('packets', 0))
        existing = self._blocks.get(source_ip)
        if existing:
            self.packets_blocked_total += packets
            return True
        self._blocks[source_ip] = BlockRule(
            source_ip=source_ip,
            action='drop',
            attack_class=meta.get('attack_class', 'unknown'),
            attack_score=float(meta.get('attack_score', 0)),
            installed_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(),
        )
        self.packets_blocked_total += packets
        return True

    def is_blocked(self, source_ip: str) -> bool:
        self._expire()
        return source_ip in self._blocks

    def record_drop(self, source_ip: str, packets: int = 0) -> None:
        if self.is_blocked(source_ip):
            self.packets_blocked_total += int(packets)

    def rate_limit_ip(self, source_ip: str, kbps: int = 500, ttl_seconds: int = 120) -> bool:
        now = datetime.utcnow()
        self._limits[source_ip] = BlockRule(
            source_ip=source_ip,
            action=f'rate_limit_{kbps}kbps',
            attack_class='',
            attack_score=0.0,
            installed_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(),
        )
        return True

    def revoke(self, source_ip: str) -> bool:
        self._blocks.pop(source_ip, None)
        self._limits.pop(source_ip, None)
        return True

    def list_rules(self) -> List[BlockRule]:
        self._expire()
        return list(self._blocks.values()) + list(self._limits.values())

    def stats(self) -> Dict:
        self._expire()
        return {
            'backend': 'simulation',
            'active_blocks': len(self._blocks),
            'active_rate_limits': len(self._limits),
            'packets_blocked_total': self.packets_blocked_total,
        }

    def _expire(self):
        now = datetime.utcnow()
        for store in (self._blocks, self._limits):
            expired = [ip for ip, r in store.items() if r.expires_at and r.expires_at < now.isoformat()]
            for ip in expired:
                store.pop(ip, None)
