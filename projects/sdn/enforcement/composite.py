"""Fan-out: apply the same decision on every dataplane that is available."""

from __future__ import annotations

import logging
from typing import Dict, List

from projects.sdn.enforcement.base import BlockRule, EnforcementBackend

logger = logging.getLogger(__name__)


class CompositeBackend(EnforcementBackend):
    def __init__(self, backends: List[EnforcementBackend], names: List[str] | None = None):
        self.backends = backends
        self.names = names or [type(b).__name__ for b in backends]
        self.packets_blocked_total = 0

    def block_ip(self, source_ip: str, ttl_seconds: int = 300, meta: dict | None = None) -> bool:
        ok = False
        for name, b in zip(self.names, self.backends):
            try:
                if b.block_ip(source_ip, ttl_seconds, meta):
                    ok = True
                    logger.info('enforced BLOCK on %s for %s', name, source_ip)
                else:
                    logger.warning('backend %s did not install block for %s', name, source_ip)
            except Exception as e:
                logger.warning('backend %s block error: %s', name, e)
        return ok

    def rate_limit_ip(self, source_ip: str, kbps: int = 500, ttl_seconds: int = 120) -> bool:
        ok = False
        for b in self.backends:
            try:
                ok = b.rate_limit_ip(source_ip, kbps, ttl_seconds) or ok
            except Exception as e:
                logger.warning('rate-limit error: %s', e)
        return ok

    def revoke(self, source_ip: str) -> bool:
        ok = True
        for b in self.backends:
            try:
                ok = b.revoke(source_ip) and ok
            except Exception:
                ok = False
        return ok

    def is_blocked(self, source_ip: str) -> bool:
        return any(b.is_blocked(source_ip) for b in self.backends)

    def record_drop(self, source_ip: str, packets: int = 0) -> None:
        self.packets_blocked_total += int(packets)
        for b in self.backends:
            b.record_drop(source_ip, packets)

    def list_rules(self) -> List[BlockRule]:
        seen = {}
        for b in self.backends:
            for r in b.list_rules():
                seen[r.source_ip] = r
        return list(seen.values())

    def stats(self) -> Dict:
        child = {n: b.stats() for n, b in zip(self.names, self.backends)}
        return {
            'backend': 'composite:' + '+'.join(self.names),
            'active_blocks': len(self.list_rules()),
            'packets_blocked_total': self.packets_blocked_total,
            'children': child,
        }
