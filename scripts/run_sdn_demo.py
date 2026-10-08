"""Start the SDN demo stack: IITKgp app, gateway, and War Room dashboard."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PORT = 8765
GATEWAY_PORT = 8091
DASH_PORT = 5050
ALLOW_IP = '127.0.0.1'
ATTACK_IP = '127.0.0.2'


def port_open(port: int) -> bool:
    s = socket.socket()
    s.settimeout(0.4)
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except OSError:
        return False


def ensure_loopback_alias() -> None:
    if sys.platform == 'win32':
        chk = subprocess.run(
            ['netsh', 'interface', 'ipv4', 'show', 'addresses', 'Loopback Pseudo-Interface 1'],
            capture_output=True, text=True,
        )
        if ATTACK_IP not in (chk.stdout or ''):
            subprocess.run(
                ['netsh', 'interface', 'ipv4', 'add', 'address',
                 'Loopback Pseudo-Interface 1', ATTACK_IP, '255.255.255.255'],
                check=False,
            )
    else:
        chk = subprocess.run(['ip', '-4', 'addr', 'show', 'dev', 'lo'], capture_output=True, text=True)
        if ATTACK_IP not in (chk.stdout or ''):
            subprocess.run(['ip', 'addr', 'add', f'{ATTACK_IP}/8', 'dev', 'lo'], check=False)


def spawn(cmd: list[str]) -> subprocess.Popen:
    creation = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    return subprocess.Popen(cmd, cwd=str(ROOT), creationflags=creation)


def wait_port(port: int, label: str, timeout: float = 60.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if port_open(port):
            print(f'  OK  {label} listening on :{port}')
            return True
        time.sleep(0.5)
    print(f'  FAIL {label} did not open :{port} within {timeout:.0f}s')
    return False


def main() -> int:
    py = sys.executable
    print('DYSENT SDN demo startup')
    print('=' * 50)

    ensure_loopback_alias()
    print(f'  OK  loopback alias {ATTACK_IP} ready')

    if not port_open(APP_PORT):
        spawn([py, str(ROOT / 'scripts' / 'serve_iitkgp.py')])
        if not wait_port(APP_PORT, 'IITKgp app', 15):
            return 1
    else:
        print(f'  OK  IITKgp app already on :{APP_PORT}')

    if not port_open(GATEWAY_PORT):
        spawn([
            py, str(ROOT / 'experiments' / 'mininet' / 'run_live_defense.py'),
            '--bind', '127.0.0.1',
            '--port', str(GATEWAY_PORT),
            '--upstream', f'127.0.0.1:{APP_PORT}',
            '--pps-threshold', '40',
            '--allow', ALLOW_IP,
        ])
        if not wait_port(GATEWAY_PORT, 'SDN gateway', 90):
            return 1
    else:
        print(f'  OK  SDN gateway already on :{GATEWAY_PORT}')

    if not port_open(DASH_PORT):
        spawn([py, str(ROOT / 'dashboard' / 'server.py')])
        if not wait_port(DASH_PORT, 'War Room dashboard', 15):
            return 1
    else:
        print(f'  OK  War Room dashboard already on :{DASH_PORT}')

    print('=' * 50)
    print(f'Protected site:  http://127.0.0.1:{GATEWAY_PORT}/')
    print(f'War Room:        http://127.0.0.1:{DASH_PORT}/sdn')
    print(f'Browser allow:   {ALLOW_IP}  ·  Lab attack source: {ATTACK_IP}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
