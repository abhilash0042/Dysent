"""
Dynamic Dashboard Server
========================
Flask backend that serves real-time pipeline status to the dashboard.
Reads live_status.json written by the unified pipeline.

Usage:
    python dashboard/server.py
    Then open: http://localhost:5050
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import os
import json
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from flask import Flask, jsonify, send_from_directory, request
from flask_cors import CORS

from projects.sdn.block_log import (
    BLOCK_LOG_FILE,
    append_block,
    read_block_log,
    write_command,
)

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Path to live status file (written by the pipeline)
STATUS_FILE = project_root / "results" / "unified_pipeline" / "live_status.json"
LEDGER_FILE = project_root / "results" / "unified_pipeline" / "live_ledger.json"
SDN_STATUS_FILE = project_root / "results" / "sdn" / "live_sdn_status.json"
SDN_ALERTS_FILE = project_root / "results" / "sdn" / "live_sdn_alerts.json"
SDN_CONSOLE_FILE = project_root / "results" / "sdn" / "iitkgp_console.json"
IITKGP_ACCESS_FILE = project_root / "results" / "sdn" / "iitkgp_access.json"
ATTACK_STATE_FILE = project_root / "results" / "sdn" / "attack_state.json"

LAB_ALLOW_IP = os.environ.get('SDN_ALLOW_IP', '127.0.0.1')
LAB_ATTACK_IP = os.environ.get('SDN_ATTACK_IP', '127.0.0.2')
GATEWAY_PORT = 8091
APP_PORT = 8765

_attack_procs: list = []
_gateway_procs: list = []
_attack_lock = threading.Lock()


def get_docker_status():
    """Check real Docker container status"""
    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--filter", "name=fabric",
             "--format", "{{.Names}}|{{.Status}}|{{.Ports}}"],
            capture_output=True, text=True, timeout=5
        )
        containers = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            parts = line.split('|')
            name = parts[0] if len(parts) > 0 else ''
            status = parts[1] if len(parts) > 1 else ''
            ports = parts[2] if len(parts) > 2 else ''
            is_up = 'Up' in status
            containers.append({
                "name": name,
                "status": "UP" if is_up else "DOWN",
                "status_detail": status,
                "ports": ports,
                "is_up": is_up
            })
        return containers
    except Exception as e:
        return [{"name": "error", "status": str(e), "is_up": False}]


@app.route('/')
def index():
    """Serve the dashboard HTML"""
    return send_from_directory('.', 'live_dashboard.html')


@app.route('/sdn')
def sdn_command():
    return send_from_directory('.', 'sdn_command.html')


@app.route('/favicon.ico')
def favicon():
    return '', 204


@app.route('/api/status')
def get_status():
    """Return current pipeline status"""
    try:
        if STATUS_FILE.exists():
            with open(STATUS_FILE, 'r') as f:
                data = json.load(f)
            data['_source'] = 'live'
            data['_read_at'] = datetime.now().isoformat()
            return jsonify(data)
        else:
            return jsonify({
                '_source': 'waiting',
                'state': 'WAITING',
                'message': 'Pipeline not started yet. Run: python experiments/unified/run_full_pipeline.py',
                'timestamp': datetime.now().isoformat()
            })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ledger')
def get_ledger():
    """Return blockchain ledger transactions"""
    try:
        if LEDGER_FILE.exists():
            with open(LEDGER_FILE, 'r') as f:
                return jsonify(json.load(f))
        return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/docker')
def get_docker():
    """Return live Docker container status"""
    return jsonify(get_docker_status())


@app.route('/api/sdn/status')
def get_sdn_status():
    """Return SDN controller live status (written by run_sdn_defense.py)."""
    try:
        if SDN_STATUS_FILE.exists():
            with open(SDN_STATUS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            data['_source'] = 'live'
            data['_read_at'] = datetime.now().isoformat()
            return jsonify(data)
        return jsonify({
            '_source': 'waiting',
            'state': 'WAITING',
            'message': 'SDN not running. Run: python experiments/mininet/run_sdn_defense.py',
            'timestamp': datetime.now().isoformat(),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/sdn/alerts')
def get_sdn_alerts():
    """Return recent SDN mitigation alerts."""
    try:
        if SDN_ALERTS_FILE.exists():
            with open(SDN_ALERTS_FILE, 'r', encoding='utf-8') as f:
                return jsonify(json.load(f))
        return jsonify([])
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _read_json(path, default):
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except Exception:
        pass
    return default


def _write_attack_state(payload):
    ATTACK_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(ATTACK_STATE_FILE, 'w', encoding='utf-8') as f:
        json.dump(payload, f)


def _kill_proc(p):
    try:
        if os.name == 'nt':
            subprocess.run(
                ['taskkill', '/F', '/T', '/PID', str(p.pid)],
                capture_output=True, timeout=8,
            )
        else:
            p.kill()
    except Exception:
        try:
            p.kill()
        except Exception:
            pass


def _stop_all_attacks():
    global _attack_procs
    killed = []
    for p in list(_attack_procs):
        killed.append(p.pid)
        _kill_proc(p)
    _attack_procs.clear()
    return killed


def _reap_attacks():
    global _attack_procs
    alive = []
    for p in _attack_procs:
        if p.poll() is None:
            alive.append(p)
    _attack_procs = alive
    return alive


def _stop_attacks_locked():
    killed = []
    for p in list(_attack_procs):
        _kill_proc(p)
        killed.append(p.pid)
    _attack_procs.clear()
    _write_attack_state({'running': False, 'stopped_at': datetime.now().isoformat()})
    return killed


def _fresh_logs(items, max_age=45.0):
    now = datetime.utcnow()
    out = []
    for x in items or []:
        ts = str((x or {}).get('timestamp') or '')
        try:
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            if dt.tzinfo is not None:
                dt = dt.replace(tzinfo=None)
            age = (now - dt).total_seconds()
        except Exception:
            continue
        if 0 <= age <= max_age:
            out.append(x)
    return out


def _gateway_fresh(status):
    ts = str((status or {}).get('timestamp') or '')
    try:
        dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return (datetime.utcnow() - dt).total_seconds() <= 12
    except Exception:
        return False


def _probe_url(url, timeout=0.8):
    try:
        req = urllib.request.Request(url, headers={'Connection': 'close', 'User-Agent': 'dysent-health'})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            r.read(32)
            return True, r.status, ''
    except urllib.error.HTTPError as e:
        return e.code < 500, e.code, type(e).__name__
    except Exception as e:
        return False, None, type(e).__name__


@app.route('/api/sdn/ops')
def sdn_ops():
    status = _read_json(SDN_STATUS_FILE, {'_source': 'waiting', 'state': 'WAITING'})
    alerts = _read_json(SDN_ALERTS_FILE, [])
    console = _read_json(SDN_CONSOLE_FILE, [])
    iitkgp = _read_json(IITKGP_ACCESS_FILE, [])
    attack = _read_json(ATTACK_STATE_FILE, {'running': False})
    alive = _reap_attacks()
    attack['running'] = bool(alive)
    attack['pids'] = [p.pid for p in alive]
    gw_live = _gateway_fresh(status)
    if not gw_live:
        status = {
            'state': 'GATEWAY_OFF',
            'backend': 'off (SDN gateway not running)',
            'served': 0,
            'discarded': 0,
            'actions_taken': 0,
            'blocked_ips': [],
            'last_prediction': None,
            '_source': 'stale_cleared',
        }
    else:
        status['_source'] = 'live'

    children = status.get('children') or {}
    app_gw = children.get('app_gateway') or {}
    status['served'] = int(status.get('served') or 0)
    status['discarded'] = int(status.get('discarded') or app_gw.get('requests_discarded') or 0)
    block_log = read_block_log()
    status['actions_taken'] = max(int(status.get('actions_taken') or 0), len(block_log))
    latest = block_log[-1] if block_log else None
    pred = status.get('last_prediction')
    stale_pred = (
        not pred
        or pred.get('action') == 'rate_limit'
        or (latest and pred.get('attack_class') == 'DrDoS_NTP' and latest.get('attack_class') != 'DrDoS_NTP')
    )
    if stale_pred and latest:
        status['last_prediction'] = {
            'source_ip': latest.get('source_ip'),
            'attack_class': latest.get('attack_class'),
            'attack_score': latest.get('attack_score'),
            'pps': latest.get('pps', 0),
            'action': latest.get('action'),
            'reason': latest.get('reason'),
            'switch': latest.get('switch'),
        }

    status['allowlisted_source'] = LAB_ALLOW_IP
    status['lab_attack_source'] = LAB_ATTACK_IP

    t_probe = time.time()
    if attack.get('mode') == 'direct':
        probe_url = f'http://127.0.0.1:{APP_PORT}/__ping'
    elif gw_live:
        probe_url = f'http://127.0.0.1:{GATEWAY_PORT}/__ping'
    else:
        probe_url = f'http://127.0.0.1:{APP_PORT}/__ping'
    app_ok, app_code, app_err = _probe_url(probe_url)
    probe_ms = int((time.time() - t_probe) * 1000)
    gw_health = status.get('app_health') or {}
    died_at = status.get('app_down_at_request')

    if app_ok:
        status['app_health'] = {
            'ok': True,
            'status': 'UP',
            'fail_streak': 0,
            'error': '',
            'http': app_code or 200,
            'source': 'live_probe',
            'latency_ms': probe_ms,
        }
        status['app_down_at_request'] = None
    else:
        status['app_health'] = {
            'ok': False,
            'status': 'DOWN',
            'fail_streak': gw_health.get('fail_streak', 3),
            'error': app_err or gw_health.get('error', 'unreachable'),
            'http': app_code,
            'source': 'live_probe',
            'latency_ms': probe_ms,
        }
        if died_at is None and attack['running']:
            status['app_down_at_request'] = status.get('served') or gw_health.get('served') or 0

    return jsonify({
        'status': status,
        'alerts': _fresh_logs(alerts if isinstance(alerts, list) else [], 45)[-40:],
        'console': _fresh_logs(console if isinstance(console, list) else [], 45)[-80:],
        'iitkgp': _fresh_logs(iitkgp if isinstance(iitkgp, list) else [], 45)[-80:],
        'gateway_live': gw_live,
        'block_log': block_log[-80:] if gw_live or block_log else read_block_log()[-80:],
        'attack': attack,
        'app_live': bool(app_ok),
        'probe_ms': probe_ms,
        '_read_at': datetime.now().isoformat(),
    })


@app.route('/api/sdn/attack/start', methods=['POST'])
def sdn_attack_start():
    """Lab-only: flood the local IITKgp demo."""
    body = request.get_json(silent=True) or {}
    mode = body.get('mode', 'sdn')
    if mode == 'sdn':
        _ensure_loopback_alias()
        _ensure_iitkgp()
        _ensure_gateway()
        url = f'http://127.0.0.1:{GATEWAY_PORT}/'
        bind = LAB_ATTACK_IP
        label = 'Application via SDN'
    else:
        url = f'http://127.0.0.1:{APP_PORT}/'
        bind = None
        label = 'No SDN (direct to app)'
    script = project_root / 'scripts' / 'ddos_stress_test.py'
    with _attack_lock:
        _stop_attacks_locked()
        procs = []
        creation = 0
        if sys.platform == 'win32':
            creation = subprocess.CREATE_NEW_PROCESS_GROUP
        nproc = 2 if mode == 'sdn' else 1
        if mode == 'sdn':
            cmd = [sys.executable, str(script), '--url', url, '--bind', bind, '--hybrid', '--hold', '180',
                   '--slowloris', '80', '--workers', '80', '--per-round', '400']
        else:
            cmd = [sys.executable, str(script), '--url', url, '--crash', '--hold', '7200', '--slowloris', '3']
        for _ in range(nproc):
            p = subprocess.Popen(
                cmd,
                cwd=str(project_root),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=creation,
            )
            _attack_procs.append(p)
            procs.append(p.pid)
        _write_attack_state({
            'running': True,
            'mode': mode,
            'url': url,
            'source_ip': bind or LAB_ALLOW_IP,
            'pids': procs,
            'started_at': datetime.now().isoformat(),
        })
    return jsonify({
        'ok': True,
        'message': f'{label}: flood on {url} from {bind or LAB_ALLOW_IP} ({len(procs)} workers)',
        'pids': procs,
        'mode': mode,
        'source_ip': bind or LAB_ALLOW_IP,
    })


@app.route('/api/sdn/attack/stop', methods=['POST'])
def sdn_attack_stop():
    with _attack_lock:
        killed = _stop_attacks_locked()
    return jsonify({'ok': True, 'message': 'Attack stopped', 'killed': killed})


def _port_open(port: int, timeout: float = 0.4) -> bool:
    s = socket.socket()
    s.settimeout(timeout)
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except OSError:
        return False


def _spawn(cmd, extra_env=None):
    creation = subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    return subprocess.Popen(
        cmd,
        cwd=str(project_root),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=creation,
        env=env,
    )


def _ensure_loopback_alias() -> bool:
    """Add 127.0.0.2 on loopback so the lab attacker != the browser."""
    try:
        if sys.platform == 'win32':
            chk = subprocess.run(
                ['netsh', 'interface', 'ipv4', 'show', 'addresses', 'Loopback Pseudo-Interface 1'],
                capture_output=True, text=True, timeout=8,
            )
            if LAB_ATTACK_IP in (chk.stdout or ''):
                return True
            add = subprocess.run(
                ['netsh', 'interface', 'ipv4', 'add', 'address',
                 'Loopback Pseudo-Interface 1', LAB_ATTACK_IP, '255.255.255.255'],
                capture_output=True, text=True, timeout=8,
            )
            return add.returncode == 0 or LAB_ATTACK_IP in (add.stderr or '')
        chk = subprocess.run(['ip', '-4', 'addr', 'show', 'dev', 'lo'], capture_output=True, text=True, timeout=5)
        if LAB_ATTACK_IP in (chk.stdout or ''):
            return True
        add = subprocess.run(['ip', 'addr', 'add', f'{LAB_ATTACK_IP}/8', 'dev', 'lo'], capture_output=True, text=True, timeout=5)
        return add.returncode == 0
    except Exception:
        return False


def _ensure_iitkgp() -> bool:
    if _port_open(APP_PORT):
        return True
    _spawn([sys.executable, str(project_root / 'scripts' / 'serve_iitkgp.py')])
    for _ in range(20):
        time.sleep(0.25)
        if _port_open(APP_PORT):
            return True
    return _port_open(APP_PORT)


def _ensure_gateway() -> bool:
    global _gateway_procs
    if _port_open(GATEWAY_PORT):
        return True
    _ensure_loopback_alias()
    p = _spawn([
        sys.executable, str(project_root / 'experiments' / 'mininet' / 'run_live_defense.py'),
        '--bind', '127.0.0.1',
        '--port', str(GATEWAY_PORT),
        '--upstream', f'127.0.0.1:{APP_PORT}',
        '--pps-threshold', '40',
        '--allow', LAB_ALLOW_IP,
    ])
    _gateway_procs.append(p)
    for _ in range(90):
        time.sleep(0.5)
        if _port_open(GATEWAY_PORT):
            return True
    return _port_open(GATEWAY_PORT)


@app.route('/api/sdn/apply', methods=['POST'])
def sdn_apply_framework():
    """Stop the occupy flood, bring the app back, install SDN block on the switch."""
    with _attack_lock:
        killed = _stop_attacks_locked()
    app_up = _ensure_iitkgp()
    gw_up = _ensure_gateway()
    attack_ip = LAB_ATTACK_IP
    rec = append_block({
        'source_ip': attack_ip,
        'action': 'block',
        'attack_class': 'Slowloris',
        'attack_score': 0.99,
        'pps': 0,
        'reason': f'Operator applied SDN — attacker {attack_ip} blocked on :{GATEWAY_PORT}, app :{APP_PORT} restored',
        'switch': 'composite:app_gateway',
        'ttl_seconds': 300,
    })
    write_command({
        'op': 'block',
        'ip': attack_ip,
        'attack_class': 'Slowloris',
        'attack_score': 0.99,
        'reason': rec['reason'],
        'ttl_seconds': 300,
    })
    recovered = False
    last_err = ''
    for _ in range(16):
        ok, code, err = _probe_url(f'http://127.0.0.1:{GATEWAY_PORT}/__ping', timeout=1.2)
        last_err = err or str(code)
        if ok:
            recovered = True
            break
        time.sleep(0.4)
    return jsonify({
        'ok': recovered,
        'message': (
            f'SDN applied — IITKgp serving via :{GATEWAY_PORT}. Attacker {attack_ip} blocked.'
            if recovered else
            f'SDN applied but gateway probe still failing ({last_err}). Try reload :{GATEWAY_PORT}.'
        ),
        'killed_attack_pids': killed,
        'gateway_up': gw_up,
        'app_listen': app_up,
        'app_live': recovered,
        'block': rec,
    })


@app.route('/api/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'ok',
        'server': 'FL-DDoS Dashboard',
        'timestamp': datetime.now().isoformat(),
        'pipeline_active': STATUS_FILE.exists()
    })


if __name__ == '__main__':
    os.makedirs(STATUS_FILE.parent, exist_ok=True)
    print("\n" + "=" * 60)
    print("  FL-DDoS Dynamic Dashboard Server")
    print("=" * 60)
    print(f"\n  Dashboard:  http://localhost:5050")
    print(f"  API:        http://localhost:5050/api/status")
    print(f"  Docker:     http://localhost:5050/api/docker")
    print(f"  Ledger:     http://localhost:5050/api/ledger")
    print(f"  SDN WAR ROOM: http://localhost:5050/sdn")
    print(f"  SDN API:      http://localhost:5050/api/sdn/ops")
    print(f"\n  Status file: {STATUS_FILE}")
    print("=" * 60 + "\n")
    app.run(host='0.0.0.0', port=5050, debug=False, threaded=True)
