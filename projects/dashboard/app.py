"""
FL-DDoS Monitoring Dashboard
Real-time WebSocket updates for FL training and attack detection
"""

from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO, emit
import json
import time
from datetime import datetime
from pathlib import Path
import threading
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'fl-ddos-dashboard-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global FL state
fl_state = {
    'current_round': 0,
    'total_rounds': 20,
    'accuracy': 0.0,
    'loss': 0.0,
    'nodes': {},
    'attacks_detected': 0,
    'is_training': False,
    'history': [],
    'latest_detections': [],
    'explanations': [],
    'total_traffic_analyzed': 0,
    'current_throughput': 0
}


@app.route('/')
def index():
    return render_template('dashboard.html')


@app.route('/api/status')
def get_status():
    return jsonify(fl_state)


@app.route('/api/start_training')
def start_training():
    fl_state['is_training'] = True
    threading.Thread(target=simulate_fl_training, daemon=True).start()
    return jsonify({'status': 'started'})


@app.route('/api/stop_training')
def stop_training():
    fl_state['is_training'] = False
    return jsonify({'status': 'stopped'})


@app.route('/api/attack_detected', methods=['POST'])
def report_attack():
    # TODO: add authentication
    from flask import request
    data = request.get_json()
    
    detection = {
        'timestamp': datetime.now().isoformat(),
        'prediction': data.get('prediction', 'Unknown'),
        'confidence': data.get('confidence', 0.0),
        'explanation': data.get('explanation', ''),
        'top_features': data.get('top_features', {})
    }
    
    fl_state['latest_detections'].insert(0, detection)
    fl_state['latest_detections'] = fl_state['latest_detections'][:10]
    
    if data.get('prediction') != 'Benign':
        fl_state['attacks_detected'] += 1
    
    socketio.emit('attack_alert', detection)
    return jsonify({'status': 'received'})


@app.route('/api/explanations')
def get_explanations():
    return jsonify(fl_state['latest_detections'])


def simulate_fl_training():
    """Demo FL training simulator"""
    fl_state['current_round'] = 0
    fl_state['accuracy'] = 0.5
    fl_state['loss'] = 2.0
    fl_state['attacks_detected'] = 0
    fl_state['history'] = []
    
    # Setup 5 nodes
    for i in range(1, 6):
        fl_state['nodes'][f'node{i}'] = {
            'status': 'active',
            'accuracy': 0.5,
            'samples': random.randint(5000, 15000),
            'trust_score': random.uniform(0.85, 1.0)
        }
    
    while fl_state['is_training'] and fl_state['current_round'] < fl_state['total_rounds']:
        fl_state['current_round'] += 1
        
        # Gradual accuracy improvement
        fl_state['accuracy'] = min(0.99, fl_state['accuracy'] + random.uniform(0.01, 0.03))
        fl_state['loss'] = max(0.01, fl_state['loss'] * 0.9)
        
        # Update each node
        for node_id in fl_state['nodes']:
            node = fl_state['nodes'][node_id]
            node['accuracy'] = fl_state['accuracy'] + random.uniform(-0.05, 0.05)
            
            # Byzantine attack demo at round 10
            if fl_state['current_round'] == 10 and node_id == 'node3':
                node['trust_score'] = 0.4
                node['status'] = 'suspicious'
                fl_state['attacks_detected'] += 1
            elif node['status'] == 'suspicious':
                node['status'] = 'removed'
            else:
                node['trust_score'] = min(1.0, node['trust_score'] + random.uniform(-0.02, 0.05))
        
        # Add to history
        fl_state['history'].append({
            'round': fl_state['current_round'],
            'accuracy': fl_state['accuracy'],
            'loss': fl_state['loss'],
            'timestamp': datetime.now().isoformat()
        })
        
        # Emit update via WebSocket
        socketio.emit('fl_update', fl_state)
        
        time.sleep(2)  # 2 seconds per round
    
    fl_state['is_training'] = False
    socketio.emit('training_complete', {'message': 'Training completed!'})


@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', fl_state)


@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')


@socketio.on('request_update')
def handle_update_request():
    emit('fl_update', fl_state)


if __name__ == '__main__':
    print("="*70)
    print("FL-DDoS Monitoring Dashboard")
    print("="*70)
    print(f"\n🌐 Dashboard running at: http://localhost:5000")
    print(f"📊 Features:")
    print(f"  - Real-time FL monitoring")
    print(f"  - Node status visualization")
    print(f"  - Attack detection alerts")
    print(f"  - Performance graphs")
    print(f"\n💡 Open http://localhost:5000 in your browser")
    print("="*70 + "\n")
    
    socketio.run(app, debug=True, port=5000, allow_unsafe_werkzeug=True)
