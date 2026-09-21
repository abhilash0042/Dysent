"""
SDN closed-loop defense demo.

Windows (default): simulation backend + replayed telemetry
WSL + sudo:        ovs backend + Mininet (when OVS is installed)

Usage:
  python experiments/mininet/run_sdn_defense.py
  python experiments/mininet/run_sdn_defense.py --mode ovs --duration 120
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(project_root))

from projects.sdn.contract import SDNModelContract
from projects.sdn.controller import SDNController
from projects.sdn.enforcement.simulation import SimulationBackend
from projects.sdn.enforcement.ovs import OvsBackend
from projects.sdn.policy import ActionType
from projects.sdn.telemetry.replay import replay_stream

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)


def run_replay_demo(duration: int, max_windows: int, backend_name: str = 'sim'):
    contract = SDNModelContract.load()
    backend = SimulationBackend() if backend_name == 'sim' else OvsBackend()
    ctrl = SDNController(backend, contract=contract)
    logger.info('SDN demo — backend=%s model=%s input=%s',
                backend_name, contract.resolve_model_path().name, contract.input_shape)
    logger.info('Thresholds: pps=%.0f alert=%.2f block=%.2f',
                contract.pps_threshold, contract.alert_threshold, contract.block_threshold)

    t0 = time.time()
    blocks = 0
    discarded = 0
    for i, (ip, feat, pps, _label) in enumerate(replay_stream(max_windows=max_windows)):
        if time.time() - t0 > duration:
            break
        if ctrl.backend.is_blocked(ip):
            ctrl.backend.record_drop(ip, packets=int(pps))
            discarded += 1
            if discarded % 25 == 0:
                ctrl.flush_status()
            continue
        act = ctrl.process(ip, feat, pps, features_already_scaled=True)
        if act and act.action == ActionType.BLOCK:
            blocks += 1
        if i % 50 == 0 and i:
            logger.info('  tick %d  obs=%d  unique_blocks=%d  discarded_ticks=%d',
                        i, ctrl.observations, blocks, discarded)
        time.sleep(0.02)

    ctrl.flush_status()
    st = ctrl.backend.stats()
    logger.info('Demo finished: observations=%d unique_blocks=%d discarded_ticks=%d packets_blocked=%s',
                ctrl.observations, blocks, discarded, st.get('packets_blocked_total'))
    logger.info('Status → results/sdn/live_sdn_status.json (dashboard /api/sdn/status)')


def main():
    p = argparse.ArgumentParser(description='SDN closed-loop defense demo')
    p.add_argument('--mode', choices=('sim', 'ovs'), default='sim')
    p.add_argument('--duration', type=int, default=90, help='Seconds to run')
    p.add_argument('--max-windows', type=int, default=200)
    args = p.parse_args()
    run_replay_demo(args.duration, args.max_windows, backend_name=args.mode)


if __name__ == '__main__':
    main()
