"""Windows Defender Firewall enforcement via netsh (requires Administrator)."""

from __future__ import annotations

import ipaddress
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List

from projects.sdn.enforcement.base import BlockRule, EnforcementBackend

logger = logging.getLogger(__name__)

RULE_PREFIX = 'DYSENT_SDN_'


def _is_os_protected(source_ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(source_ip.split('%')[0])
    except ValueError:
        return True
    return addr.is_loopback or addr.is_link_local or addr.is_multicast or addr.is_unspecified


class WindowsFirewallBackend(EnforcementBackend):
    def __init__(self):
        self._blocks: Dict[str, BlockRule] = {}
        self.packets_blocked_total = 0
        self.available = self._probe()

    def _probe(self) -> bool:
        try:
            r = subprocess.run(
                ['netsh', 'advfirewall', 'show', 'currentprofile'],
                capture_output=True, text=True, timeout=8,
            )
            return r.returncode == 0
        except Exception:
            return False

    def _run(self, args: List[str]) -> subprocess.CompletedProcess:
        return subprocess.run(['netsh'] + args, capture_output=True, text=True, timeout=15)

    def block_ip(self, source_ip: str, ttl_seconds: int = 300, meta: dict | None = None) -> bool:
        if _is_os_protected(source_ip):
            logger.info('Windows firewall will not OS-block protected address %s', source_ip)
            return False
        meta = meta or {}
        name = f'{RULE_PREFIX}{source_ip}'
        r = self._run([
            'advfirewall', 'firewall', 'add', 'rule',
            f'name={name}',
            'dir=in', 'action=block', 'enable=yes',
            f'remoteip={source_ip}',
            'profile=any',
            'description=Dysent SDN DDoS block (auto)',
        ])
        if r.returncode != 0:
            logger.warning('Windows firewall block failed for %s: %s', source_ip, (r.stderr or r.stdout).strip())
            return False
        now = datetime.utcnow()
        self._blocks[source_ip] = BlockRule(
            source_ip=source_ip,
            action='drop',
            attack_class=meta.get('attack_class', ''),
            attack_score=float(meta.get('attack_score', 0)),
            installed_at=now.isoformat() + 'Z',
            expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat() + 'Z',
        )
        logger.warning('Windows Firewall BLOCK %s (ttl=%ss)', source_ip, ttl_seconds)
        return True

    def rate_limit_ip(self, source_ip: str, kbps: int = 500, ttl_seconds: int = 120) -> bool:
        logger.info('Windows QoS rate-limit not used; blocking %s instead', source_ip)
        return self.block_ip(source_ip, ttl_seconds=ttl_seconds)

    def revoke(self, source_ip: str) -> bool:
        self._run(['advfirewall', 'firewall', 'delete', 'rule', f'name={RULE_PREFIX}{source_ip}'])
        self._blocks.pop(source_ip, None)
        return True

    def is_blocked(self, source_ip: str) -> bool:
        return source_ip in self._blocks

    def list_rules(self) -> List[BlockRule]:
        return list(self._blocks.values())

    def stats(self) -> Dict:
        return {
            'backend': 'windows_firewall',
            'available': self.available,
            'active_blocks': len(self._blocks),
            'packets_blocked_total': self.packets_blocked_total,
        }
