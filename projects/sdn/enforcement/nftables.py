"""nftables drop set, applied inside WSL Ubuntu (root) from Windows or native Linux."""

from __future__ import annotations

import ipaddress
import logging
import os
import platform
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List

from projects.sdn.enforcement.base import BlockRule, EnforcementBackend

logger = logging.getLogger(__name__)

TABLE = 'dysent'
SET_NAME = 'blocked'


def _wsl_root(cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ['wsl', '-d', 'Ubuntu', '-u', 'root', '--', 'bash', '-lc', cmd],
        capture_output=True, text=True, timeout=20,
    )


class NftablesBackend(EnforcementBackend):
    def __init__(self):
        self._blocks: Dict[str, BlockRule] = {}
        self.packets_blocked_total = 0
        self.via_wsl = os.name == 'nt'
        self.available = False
        self._ensure_table()

    def _nft(self, snippet: str) -> subprocess.CompletedProcess:
        cmd = f'nft {snippet}'
        if self.via_wsl:
            return _wsl_root(cmd)
        if hasattr(os, 'geteuid') and os.geteuid() != 0:
            cmd = f'sudo -n nft {snippet}'
        return subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=20)

    def _ensure_table(self) -> None:
        script = f'''
        nft list table inet {TABLE} >/dev/null 2>&1 || nft add table inet {TABLE}
        nft list set inet {TABLE} {SET_NAME} >/dev/null 2>&1 || \
          nft add set inet {TABLE} {SET_NAME} '{{ type ipv4_addr; flags timeout; }}'
        nft list chain inet {TABLE} input >/dev/null 2>&1 || \
          nft add chain inet {TABLE} input '{{ type filter hook input priority 0; policy accept; }}'
        nft list chain inet {TABLE} forward >/dev/null 2>&1 || \
          nft add chain inet {TABLE} forward '{{ type filter hook forward priority 0; policy accept; }}'
        nft list ruleset | grep -q 'ip saddr @{SET_NAME} drop' || \
          nft add rule inet {TABLE} input ip saddr @{SET_NAME} drop
        nft list ruleset | grep -q 'ip saddr @{SET_NAME} drop' || true
        '''
        if self.via_wsl:
            r = _wsl_root(script)
        else:
            r = subprocess.run(['bash', '-lc', script], capture_output=True, text=True, timeout=25)
        self.available = r.returncode == 0
        if not self.available:
            logger.warning('nftables not ready: %s', (r.stderr or r.stdout).strip()[:400])
        else:
            logger.info('nftables table inet %s ready (wsl=%s)', TABLE, self.via_wsl)

    def block_ip(self, source_ip: str, ttl_seconds: int = 300, meta: dict | None = None) -> bool:
        try:
            addr = ipaddress.ip_address(source_ip.split('%')[0])
            if addr.is_loopback or addr.is_link_local or addr.is_multicast:
                logger.info('nftables will not OS-block protected address %s', source_ip)
                return False
        except ValueError:
            return False
        meta = meta or {}
        ttl = max(30, int(ttl_seconds))
        r = self._nft(f'add element inet {TABLE} {SET_NAME} \'{{ {source_ip} timeout {ttl}s }}\'')
        if r.returncode != 0:
            logger.warning('nftables block failed %s: %s', source_ip, (r.stderr or r.stdout).strip())
            return False
        now = datetime.utcnow()
        self._blocks[source_ip] = BlockRule(
            source_ip=source_ip,
            action='drop',
            attack_class=meta.get('attack_class', ''),
            attack_score=float(meta.get('attack_score', 0)),
            installed_at=now.isoformat() + 'Z',
            expires_at=(now + timedelta(seconds=ttl)).isoformat() + 'Z',
        )
        logger.warning('nftables BLOCK %s ttl=%ss', source_ip, ttl)
        return True

    def rate_limit_ip(self, source_ip: str, kbps: int = 500, ttl_seconds: int = 120) -> bool:
        return self.block_ip(source_ip, ttl_seconds=ttl_seconds)

    def revoke(self, source_ip: str) -> bool:
        self._nft(f'delete element inet {TABLE} {SET_NAME} \'{{ {source_ip} }}\'')
        self._blocks.pop(source_ip, None)
        return True

    def is_blocked(self, source_ip: str) -> bool:
        return source_ip in self._blocks

    def list_rules(self) -> List[BlockRule]:
        return list(self._blocks.values())

    def stats(self) -> Dict:
        return {
            'backend': 'nftables',
            'available': self.available,
            'via_wsl': self.via_wsl,
            'platform': platform.system(),
            'active_blocks': len(self._blocks),
            'packets_blocked_total': self.packets_blocked_total,
        }
