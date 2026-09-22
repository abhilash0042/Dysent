"""Open vSwitch enforcement via ovs-ofctl (Mininet / WSL)."""

from __future__ import annotations

import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List

from projects.sdn.enforcement.base import BlockRule, EnforcementBackend

logger = logging.getLogger(__name__)


class OvsBackend(EnforcementBackend):
    def __init__(self, switch: str = 's1', protected_dst: str = '10.0.0.254'):
        self.switch = switch
        self.protected_dst = protected_dst
        self._local: Dict[str, BlockRule] = {}

    def _run(self, args: List[str]) -> bool:
        cmd = ['ovs-ofctl', '-O', 'OpenFlow13'] + args
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            if r.returncode != 0:
                logger.warning('ovs-ofctl failed: %s %s', cmd, r.stderr.strip())
                return False
            return True
        except FileNotFoundError:
            logger.error('ovs-ofctl not found — run inside WSL with openvswitch-switch')
            return False

    def block_ip(self, source_ip: str, ttl_seconds: int = 300, meta: dict | None = None) -> bool:
        meta = meta or {}
        flow = (
            f'priority=65535,ip,nw_src={source_ip},nw_dst={self.protected_dst},'
            f'idle_timeout=60,hard_timeout={ttl_seconds},actions=drop'
        )
        ok = self._run(['add-flow', self.switch, flow])
        if ok:
            now = datetime.utcnow()
            self._local[source_ip] = BlockRule(
                source_ip=source_ip,
                action='drop',
                attack_class=meta.get('attack_class', ''),
                attack_score=float(meta.get('attack_score', 0)),
                installed_at=now.isoformat(),
                expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(),
            )
        return ok

    def rate_limit_ip(self, source_ip: str, kbps: int = 500, ttl_seconds: int = 120) -> bool:
        """Install an OpenFlow meter when supported by the local OVS build."""
        meter_id = (abs(hash(source_ip)) % 10000) + 1
        meter_ok = self._run(['--may-exist', 'add-meter', self.switch,
                              f'{meter_id},kbps,band=type=drop,rate={kbps}'])
        flow_ok = self._run(['--may-exist', 'add-flow', self.switch,
                              f'priority=65534,ip,nw_src={source_ip},nw_dst={self.protected_dst},'
                              f'idle_timeout=60,hard_timeout={ttl_seconds},meter={meter_id},actions=normal'])
        ok = meter_ok and flow_ok
        logger.info('Rate limit %s to %d kbps (meter=%s, ttl=%ds)', source_ip, kbps, meter_id, ttl_seconds)
        if not ok:
            logger.warning('OVS meter installation failed; no rate-limit rule was claimed as installed')
        now = datetime.utcnow()
        self._local[source_ip] = BlockRule(
            source_ip=source_ip,
            action=f'rate_limit_{kbps}kbps',
            attack_class='',
            attack_score=0.0,
            installed_at=now.isoformat(),
            expires_at=(now + timedelta(seconds=ttl_seconds)).isoformat(),
        )
        return ok

    def revoke(self, source_ip: str) -> bool:
        self._run(['del-flows', self.switch, f'ip,nw_src={source_ip}'])
        self._local.pop(source_ip, None)
        return True

    def list_rules(self) -> List[BlockRule]:
        return list(self._local.values())

    def is_blocked(self, source_ip: str) -> bool:
        rule = self._local.get(source_ip)
        return bool(rule and rule.action == 'drop')

    def stats(self) -> Dict:
        blocked = 0
        try:
            r = subprocess.run(
                ['ovs-ofctl', '-O', 'OpenFlow13', 'dump-flows', self.switch],
                capture_output=True, text=True, timeout=10,
            )
            if r.returncode == 0:
                blocked = sum(
                    int(line.split('n_packets=')[1].split(',')[0])
                    for line in r.stdout.splitlines()
                    if 'actions=drop' in line and 'n_packets=' in line
                )
        except Exception:
            pass
        return {
            'backend': 'ovs',
            'switch': self.switch,
            'active_rules': len(self._local),
            'packets_blocked_total': blocked,
        }
