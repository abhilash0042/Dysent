"""
Mininet FL Server Wrapper
Wraps the FederatedServer with a real TCP socket listener for authentic network traffic.
"""

import sys
import socket
import pickle
import struct
import threading
import logging
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from ddosdfl.projects.fl.aggregation_server import FederatedServer
from ddosdfl.projects.shared_libs.cnn_bilstm_model import CNNBiLSTMModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MininetServer")

HOST = '0.0.0.0'
PORT = 5000

def send_msg(sock, data):
    """Send message with length prefix"""
    msg = pickle.dumps(data)
    # limit max message size to avoid issues, but pickle can be large
    # verify length
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

class NetworkedFLServer:
    def __init__(self):
        # Initialize FL Server logic (In-Memory)
        # Create a dummy model for initialization
        logger.info("Initializing FL Server logic...")
        # Use 10 classes to match Client's Modern2026AttackGenerator
        model = CNNBiLSTMModel(input_shape=(10, 4), num_classes=10).model
        self.fl_server = FederatedServer(global_model=model, min_nodes=2)
        
        self.clients = {} # {client_addr: socket}
        self.client_ids = []
    
    def start(self):
        """Start TCP Server"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind((HOST, PORT))
        server_socket.listen(5)
        
        logger.info(f"🚀 Server listening on {HOST}:{PORT}")
        
        while True:
            client_sock, addr = server_socket.accept()
            logger.info(f"➕ Client connected: {addr}")
            
            # Handle client in a thread
            t = threading.Thread(target=self.handle_client, args=(client_sock, addr))
            t.start()
            
    def handle_client(self, conn, addr):
        try:
            # 1. Registration
            msg = recv_msg(conn)
            if msg['type'] == 'REGISTER':
                node_id = msg['node_id']
                self.clients[node_id] = conn
                self.client_ids.append(node_id)
                logger.info(f"Registered Node: {node_id}")
                
                # Send registration ack + Initial Global Model
                global_weights = self.fl_server.global_model.get_weights()
                send_msg(conn, {
                    'type': 'INIT',
                    'weights': global_weights,
                    'config': {'rounds': 3} # Short simulation
                })
                
                # Enter Training Loop (mock command for this thread)
                self.client_loop(conn, node_id)
                
        except Exception as e:
            logger.error(f"Error handling client {addr}: {e}")
        finally:
            conn.close()

    def client_loop(self, conn, node_id):
        """Handle training rounds for a specific client"""
        for round_num in range(1, 4):
            logger.info(f"--- Round {round_num}: Waiting for update from {node_id} ---")
            
            # Wait for Update
            msg = recv_msg(conn)
            if not msg or msg['type'] != 'UPDATE':
                break
                
            update = msg['data']
            logger.info(f"Received update from {node_id}: Accuracy={update['metrics']['accuracy']:.4f}")
            
            # (In simulation we aggregate naively just to keep traffic moving)
            # Send back "Aggregated" weights (just bounce back or slightly modify for demo)
            # In real system, we'd wait for all, but here we just ack to keep traffic flowing for Wireshark
            
            # Simulate aggregation delay
            import time
            time.sleep(1)
            
            global_weights = self.fl_server.global_model.get_weights() # Return same for demo
            send_msg(conn, {
                'type': 'ROUND_COMPLETE',
                'round': round_num,
                'weights': global_weights
            })
            
        logger.info(f"Client {node_id} finished training.")
        send_msg(conn, {'type': 'STOP'})

if __name__ == "__main__":
    server = NetworkedFLServer()
    server.start()
