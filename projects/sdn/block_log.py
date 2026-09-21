"""Append-only block / mitigation log for the War Room switch table."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, List

BLOCK_LOG_FILE = Path(__file__).resolve().parents[2] / 'results' / 'sdn' / 'block_log.json'
SDN_COMMAND_FILE = Path(__file__).resolve().parents[2] / 'results' / 'sdn' / 'sdn_commands.json'
MAX_EVENTS = 200


def _atomic_write(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, indent=2)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix='.tmp')
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
        raise


def read_block_log() -> List[dict]:
    try:
        if BLOCK_LOG_FILE.exists():
            with open(BLOCK_LOG_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, list):
                return data
    except Exception:
        pass
    return []


def append_block(event: dict) -> dict:
    rec = dict(event)
    rec.setdefault('timestamp', datetime.utcnow().isoformat() + 'Z')
    rec.setdefault('action', 'block')
    rec.setdefault('switch', 'app_gateway')
    log = read_block_log()
    log.append(rec)
    _atomic_write(BLOCK_LOG_FILE, log[-MAX_EVENTS:])
    return rec


def write_command(cmd: dict) -> None:
    payload = dict(cmd)
    payload['issued_at'] = datetime.utcnow().isoformat() + 'Z'
    _atomic_write(SDN_COMMAND_FILE, payload)
