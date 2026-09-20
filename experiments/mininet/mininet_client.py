"""
Mininet FL Client Wrapper
Wraps the FLNode with real TCP socket communication.
"""

import sys
import socket
import pickle
import struct
import logging
import numpy as np
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from ddosdfl.projects.fl.fl_node_client import FLNode
from ddosdfl.projects.shared_libs.cnn_bilstm_model import CNNBiLSTMModel
from ddosdfl.scripts.data.generate_modern_2026_attacks import Modern2026AttackGenerator
from ddosdfl.scripts.data.load_cicddos import reshape_for_cnn_bilstm

logging.basicConfig(level=logging.INFO)
# Use client-specific logger to avoid confusion? We rely on node_id.

HOST = '10.0.0.254' # Assumes Server IP in Mininet
PORT = 5000

def send_msg(sock, data):
    """Send message with length prefix"""
    msg = pickle.dumps(data)
    msg_len = struct.pack('>I', len(msg))
    sock.sendall(msg_len + msg)

def recv_msg(sock):
    """Receive message with length prefix"""
    raw_msglen = recvall(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack('>I', raw_msglen)[0]
    raw_msg = recvall(sock, msglen)
    return pickle.loads(raw_msg)

def recvall(sock, n):
    """Helper to receive n bytes"""
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data

class NetworkedFLClient:
    def __init__(self, node_id):
        self.node_id = node_id
        self.logger = logging.getLogger(f"Client_{node_id}")
        
        # 1. Generate Local Data (Authentic 2026 Data)
        self.logger.info("Generating local dataset...")
        gen = Modern2026AttackGenerator(seed=int(node_id.replace('h', '')))
        X_raw, y = gen.generate_modern_dataset(num_samples=500, num_features=40)
        X = reshape_for_cnn_bilstm(X_raw, 10)
        
        # 2. Init FL Logic
        def model_fn():
             return CNNBiLSTMModel(input_shape=(10, 4), num_classes=10).model
             
        self.fl_node = FLNode(
            node_id=node_id,
            local_data=(X, y),
            model_builder_fn=model_fn,
            epochs_per_round=1
        )
        
    def start(self, server_ip):
        """Connect to server and start training loop"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.logger.info(f"Connecting to server at {server_ip}:{PORT}...")
        
        try:
            sock.connect((server_ip, PORT))
            self.logger.info("✅ Connected!")
            
            # 1. Register
            send_msg(sock, {'type': 'REGISTER', 'node_id': self.node_id})
            
            # 2. Wait for Init
            msg = recv_msg(sock)
            if msg['type'] == 'INIT':
                self.logger.info("Received Initialization from Server")
                self.fl_node.set_model_weights(msg['weights'])
                
                # Training Loop
                while True:
                    self.logger.info("Starting Training Round...")
                    
                    # Train Locally
                    metrics = self.fl_node.train_local_model(verbose=0)
                    
                    # Send Update
                    update = self.fl_node.create_update_package()
                    self.logger.info("Sending Model Update...")
                    send_msg(sock, {'type': 'UPDATE', 'data': update})
                    
                    # Wait for Global Model (Round Complete)
                    msg = recv_msg(sock)
                    if not msg or msg['type'] == 'STOP':
                        break
                        
                    if msg['type'] == 'ROUND_COMPLETE':
                        self.logger.info(f"Round {msg['round']} Complete. Updating Global Weights.")
                        self.fl_node.set_model_weights(msg['weights'])
            
        except Exception as e:
            self.logger.error(f"Connection error: {e}")
        finally:
            sock.close()
            self.logger.info("Connection closed.")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python mininet_client.py <node_id> <server_ip>")
        sys.exit(1)
        
    node_id = sys.argv[1]
    server_ip = sys.argv[2]
    
    client = NetworkedFLClient(node_id)
    client.start(server_ip)
