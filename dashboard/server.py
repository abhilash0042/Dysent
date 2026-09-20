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
import subprocess
from datetime import datetime
from flask import Flask, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

# Path to live status file (written by the pipeline)
STATUS_FILE = project_root / "results" / "unified_pipeline" / "live_status.json"
LEDGER_FILE = project_root / "results" / "unified_pipeline" / "live_ledger.json"


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
    print(f"\n  Status file: {STATUS_FILE}")
    print("=" * 60 + "\n")
    app.run(host='0.0.0.0', port=5050, debug=False)
