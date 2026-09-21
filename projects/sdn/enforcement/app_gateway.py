"""In-process block list used by the live TCP/HTTP gateway.

This is real application enforcement: accepted sockets from blocked IPs
are closed immediately and never proxied to the protected app.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List

from projects.sdn.enforcement.base import BlockRule, EnforcementBackend


class AppGatewayBackend(EnforcementBackend):
    def __init__(self):
        self._blocks: Dict[str, BlockRule] = {}
        self.packets_blocked_total = 0
        self.requests_discarded = 0

    def block_ip(self, source_ip: str, ttl_seconds: int = 300, meta: dict | None = None) -> bool:
        meta = meta or {}
        now = datetime.utcnow()
        self._blocks[source_ip] = BlockRule(
            source_ip=source_ip,
            action='drop',
            attack_class=meta.get('attack_class', ''),
            attack_score=float(meta.get('attack_score', 0)),
            installed_at=now.isoformat() + 'Z',
            expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat() + 'Z',
        )
        self.packets_blocked_total += int(meta.get('packets', 0))
        return True

    def rate_limit_ip(self, source_ip: str, kbps: int = 500, ttl_seconds: int = 120) -> bool:
        meta = {'attack_class': 'rate_limit'}
        now = datetime.utcnow()
        self._blocks[source_ip] = BlockRule(
            source_ip=source_ip,
            action='rate_limit',
            attack_class='rate_limit',
            attack_score=0.0,
            installed_at=now.isoformat() + 'Z',
            expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat() + 'Z',
        )
        return True

    def revoke(self, source_ip: str) -> bool:
        self._blocks.pop(source_ip, None)
        return True

    def is_blocked(self, source_ip: str) -> bool:
        self._expire()
        rule = self._blocks.get(source_ip)
        return bool(rule and rule.action == 'drop')

    def record_drop(self, source_ip: str, packets: int = 0) -> None:
        if self.is_blocked(source_ip):
            self.packets_blocked_total += int(packets)
            self.requests_discarded += 1

    def list_rules(self) -> List[BlockRule]:
        self._expire()
        return list(self._blocks.values())

    def stats(self) -> Dict:
        self._expire()
        return {
            'backend': 'app_gateway',
            'active_blocks': len(self._blocks),
            'packets_blocked_total': self.packets_blocked_total,
            'requests_discarded': self.requests_discarded,
        }

    def _expire(self):
        now = datetime.utcnow().isoformat() + 'Z'
        expired = [ip for ip, r in self._blocks.items() if r.expires_at and r.expires_at < now]
        for ip in expired:
            self._blocks.pop(ip, None)
