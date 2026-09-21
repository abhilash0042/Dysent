"""Atomic JSON status for dashboard/server.py."""

from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

SDN_STATUS_FILE = Path(__file__).resolve().parents[2] / 'results' / 'sdn' / 'live_sdn_status.json'
SDN_ALERTS_FILE = Path(__file__).resolve().parents[2] / 'results' / 'sdn' / 'live_sdn_alerts.json'
SDN_CONSOLE_FILE = Path(__file__).resolve().parents[2] / 'results' / 'sdn' / 'iitkgp_console.json'


def _atomic_write(path: Path, data: Any):
    """Write JSON without leaving a half-written file. Retries on Windows file locks."""
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        last_err: Exception | None = None
        for _ in range(12):
            try:
                os.replace(tmp_path, path)
                return
            except PermissionError as e:
                last_err = e
                time.sleep(0.05)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(payload)
        tmp_path.unlink(missing_ok=True)
        if last_err is None:
            return
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


class SDNStatusWriter:
    def __init__(self):
        self.alerts: List[dict] = []
        self.console: List[dict] = []
        self.max_alerts = 80
        self.max_console = 200

    def push_alert(self, alert: dict):
        alert['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        self.alerts.append(alert)
        self.alerts = self.alerts[-self.max_alerts:]
        _atomic_write(SDN_ALERTS_FILE, self.alerts)

    def write_status(self, payload: Dict):
        payload['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        payload['state'] = payload.get('state', 'ACTIVE')
        _atomic_write(SDN_STATUS_FILE, payload)

    def push_console(self, line: dict):
        line['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        self.console.append(line)
        self.console = self.console[-self.max_console:]
        _atomic_write(SDN_CONSOLE_FILE, self.console)
