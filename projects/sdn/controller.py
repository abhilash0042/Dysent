"""Closed-loop SDN controller: telemetry → detector → policy → enforcement."""

from __future__ import annotations

import logging
from typing import Optional

from projects.sdn.block_log import append_block
from projects.sdn.contract import SDNModelContract
from projects.sdn.detector import SDNDetector, DetectionAlert
from projects.sdn.enforcement.base import EnforcementBackend
from projects.sdn.policy import ActionType, MitigationPolicy, MitigationAction
from projects.sdn.status import SDNStatusWriter

logger = logging.getLogger(__name__)


class SDNController:
    """
    Model-swappable closed loop.

    To upgrade the model later:
      1. Train new .keras
      2. Update models/sdn_model_contract.json (model_path + scaler if needed)
      3. Restart this controller — no code changes
    """

    def __init__(
        self,
        backend: EnforcementBackend,
        contract: SDNModelContract | None = None,
        contract_path: str | None = None,
    ):
        self.contract = contract or SDNModelContract.load(contract_path)
        self.detector = SDNDetector(contract=self.contract, pad_incomplete=True)
        self.policy = MitigationPolicy(self.contract)
        self.backend = backend
        self.status = SDNStatusWriter()
        self.actions_taken = 0
        self.observations = 0
        self._last_extra: dict = {}

    def process(
        self,
        source_ip: str,
        raw_features,
        packets_this_second: float = 0.0,
        *,
        features_already_scaled: bool = False,
        incomplete_ratio: float = 0.0,
        concurrent: int = 0,
        mean_iat_us: float = 0.0,
    ) -> Optional[MitigationAction]:
        self.observations += 1
        if self.backend.is_blocked(source_ip):
            self.backend.record_drop(source_ip, packets=int(packets_this_second))
            return None

        alert = self.detector.observe(
            source_ip, raw_features, packets_this_second,
            features_already_scaled=features_already_scaled,
            incomplete_ratio=incomplete_ratio,
            concurrent=concurrent,
            mean_iat_us=mean_iat_us,
        )
        if alert is None:
            return None

        action = self.policy.decide(alert)
        self._apply(action, alert)
        if action.action != ActionType.NONE:
            self._publish(action, alert)
        return action

    def _apply(self, action: MitigationAction, alert: DetectionAlert):
        meta = {
            'attack_class': alert.attack_class,
            'attack_score': alert.attack_score,
            'packets': int(alert.pps),
        }
        if action.action == ActionType.BLOCK:
            self.backend.block_ip(action.source_ip, action.ttl_seconds, meta)
            self.actions_taken += 1
            logger.warning('BLOCK %s (%s score=%.2f)', action.source_ip, alert.attack_class, alert.attack_score)
            append_block({
                'source_ip': action.source_ip,
                'action': 'block',
                'attack_class': alert.attack_class,
                'attack_score': round(alert.attack_score, 4),
                'pps': round(alert.pps, 1),
                'reason': action.reason,
                'switch': self.backend.stats().get('backend', ''),
                'ttl_seconds': action.ttl_seconds,
            })
        elif action.action == ActionType.RATE_LIMIT:
            self.backend.rate_limit_ip(action.source_ip, kbps=500, ttl_seconds=action.ttl_seconds)
            self.actions_taken += 1
            logger.info('RATE-LIMIT %s score=%.2f', action.source_ip, alert.attack_score)
            append_block({
                'source_ip': action.source_ip,
                'action': 'rate_limit',
                'attack_class': alert.attack_class,
                'attack_score': round(alert.attack_score, 4),
                'pps': round(alert.pps, 1),
                'reason': action.reason,
                'switch': self.backend.stats().get('backend', ''),
                'ttl_seconds': action.ttl_seconds,
            })
        elif action.action == ActionType.LOG:
            logger.info('WATCH %s %s score=%.2f', action.source_ip, alert.attack_class, alert.attack_score)

    def _publish(self, action: MitigationAction, alert: DetectionAlert):
        self.status.push_alert({
            'source_ip': alert.source_ip,
            'attack_class': alert.attack_class,
            'attack_score': round(alert.attack_score, 4),
            'benign_prob': round(alert.benign_prob, 4),
            'pps': round(alert.pps, 1),
            'action': action.action.value,
            'reason': action.reason,
        })
        self.flush_status({
            'last_alert': {
                'source_ip': alert.source_ip,
                'attack_class': alert.attack_class,
                'attack_score': alert.attack_score,
                'action': action.action.value,
            },
        })

    def flush_status(self, extra: dict | None = None):
        st = self.backend.stats()
        payload = {
            'model': self.contract.resolve_model_path().name,
            'input_shape': list(self.contract.input_shape),
            'observations': self.observations,
            'actions_taken': self.actions_taken,
            'blocked_ips': [
                {
                    'source_ip': r.source_ip,
                    'action': r.action,
                    'attack_class': r.attack_class,
                    'attack_score': r.attack_score,
                    'installed_at': r.installed_at,
                    'switch': st.get('backend', ''),
                }
                for r in self.backend.list_rules()
            ],
            'packets_blocked': st.get('packets_blocked_total', 0),
            'backend': st.get('backend', ''),
            'children': st.get('children', {}),
        }
        if extra:
            self._last_extra.update(extra)
        if self._last_extra:
            payload.update(self._last_extra)
        payload.setdefault('served', 0)
        payload.setdefault('discarded', 0)
        self.status.write_status(payload)
