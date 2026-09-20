"""
Live WiFi Traffic Capture and DDoS Detection
Captures real network traffic and analyzes with Explainable AI
"""

import sys
from pathlib import Path
from scapy.all import sniff, IP, TCP, UDP, get_if_list
from collections import defaultdict
import time
import numpy as np
import requests
import logging

# Setup paths
project_root = Path(__file__).resolve().parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import CNNBiLSTMModel
from ddosdfl.projects.shared_libs.explainable_ai import create_explainer
from tensorflow import keras

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("LiveWiFi")

class LiveWiFiDetector:
    """Capture and analyze live WiFi traffic"""
    
    def __init__(self, interface="Wi-Fi", model_path=None):
        self.interface = interface
        self.flows = defaultdict(lambda: {
            'packets': [],
            'start_time': time.time(),
            'syn_count': 0,
            'ack_count': 0,
            'bytes': 0
        })
        
        # Load model
        model_file = Path("c:/Users/HP/Desktop/Major Project/Main File-Code/ddosdfl/models/best_model.keras")
        if model_file.exists():
            logger.info(f"Loading trained model from {model_file}")
            self.model = keras.models.load_model(model_file)
        else:
            logger.info("Using default model")
            model_wrapper = CNNBiLSTMModel(input_shape=(10, 4), num_classes=2)
            self.model = model_wrapper.get_model()
        
        # Initialize explainer
        feature_names = ['packet_rate', 'packet_size', 'syn_ratio', 'flow_duration']
        self.explainer = create_explainer(self.model, feature_names)
        
        logger.info(f"✅ Detector initialized on interface: {interface}")
    
    def extract_flow_features(self, flow_key):
        """Extract features from captured flow"""
        flow = self.flows[flow_key]
        
        if not flow['packets']:
            return None
        
        # Calculate features
        duration = time.time() - flow['start_time']
        packet_count = len(flow['packets'])
        
        features = {
            'packet_rate': packet_count / max(duration, 0.001),
            'packet_size': flow['bytes'] / max(packet_count, 1),
            'syn_ratio': flow['syn_count'] / max(packet_count, 1),
            'flow_duration': duration
        }
        
        return features
    
    def process_packet(self, packet):
        """Process each captured packet"""
        
        if not packet.haslayer(IP):
            return
        
        # Extract flow identifier
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        protocol = packet[IP].proto
        
        src_port = packet.sport if hasattr(packet, 'sport') else 0
        dst_port = packet.dport if hasattr(packet, 'dport') else 0
        
        flow_key = (src_ip, dst_ip, src_port, dst_port, protocol)
        
        # Update flow statistics
        flow = self.flows[flow_key]
        flow['packets'].append(packet)
        flow['bytes'] += len(packet)
        
        # Count TCP flags
        if packet.haslayer(TCP):
            if packet[TCP].flags & 0x02:  # SYN flag
                flow['syn_count'] += 1
            if packet[TCP].flags & 0x10:  # ACK flag
                flow['ack_count'] += 1
        
        # Analyze flow if enough packets collected
        if len(flow['packets']) >= 10:
            self.analyze_flow(flow_key)
            # Reset flow
            del self.flows[flow_key]
    
    def analyze_flow(self, flow_key):
        """Analyze completed flow for DDoS"""
        
        features = self.extract_flow_features(flow_key)
        if not features:
            return
        
        # Convert to model input format
        feature_array = np.array([
            [features['packet_rate'], features['packet_size'], 
             features['syn_ratio'], features['flow_duration']]
        ] * 10).reshape(1, 10, 4)
        
        # Get prediction with explanation
        result = self.explainer.explain_prediction(feature_array)
        
        # Display result
        if result['prediction'] == 1:  # Attack
            logger.info(f"\n⚠️  ATTACK DETECTED!")
            logger.info(f"Flow: {flow_key[0]}:{flow_key[2]} -> {flow_key[1]}:{flow_key[3]}")
            logger.info(f"Confidence: {result['confidence']*100:.1f}%")
            logger.info(f"Explanation: {result['explanation_text']}")
            
            if result['top_features']:
                logger.info("Top Features:")
                for feat, contrib in result['top_features'].items():
                    logger.info(f"  - {feat}: {contrib*100:.1f}%")
            
            # Send to dashboard (if running)
            try:
                requests.post('http://localhost:5000/api/attack_detected', json={
                    'prediction': result['prediction_label'],
                    'confidence': result['confidence'],
                    'explanation': result['explanation_text'],
                    'top_features': result['top_features']
                }, timeout=0.5)
                logger.info("  -> Sent to dashboard")
            except:
                pass  # Dashboard not running
    
    def start_monitoring(self, duration=60):
        """Start live monitoring"""
        
        logger.info(f"\n{'='*70}")
        logger.info(f"🔴 LIVE WiFi MONITORING ACTIVE")
        logger.info(f"Interface: {self.interface}")
        logger.info(f"Duration: {duration}s (or Ctrl+C to stop)")
        logger.info(f"{'='*70}\n")
        
        try:
            sniff(
                iface=self.interface,
                prn=self.process_packet,
                store=False,
                timeout=duration
            )
        except KeyboardInterrupt:
            logger.info("\n\n✅ Monitoring stopped by user")
        except Exception as e:
            logger.error(f"\n❌ Error: {e}")
            logger.info("\nTroubleshooting:")
            logger.info("  1. Run as Administrator (Windows) or with sudo (Linux)")
            logger.info("  2. Install Npcap: https://npcap.com/")
            logger.info("  3. Check interface name:")
            logger.info(f"     Available interfaces: {get_if_list()}")
        
        logger.info(f"\n{'='*70}")
        logger.info(f"Monitoring complete. Analyzed {len(self.flows)} flows.")
        logger.info(f"{'='*70}\n")

def list_interfaces():
    """List available network interfaces"""
    print("\nAvailable network interfaces:")
    for i, iface in enumerate(get_if_list(), 1):
        print(f"  {i}. {iface}")
    print()

def main():
    """Run live WiFi detector"""
    
    import argparse
    parser = argparse.ArgumentParser(description="Live WiFi DDoS Detector")
    parser.add_argument('--interface', default='Wi-Fi', help='Network interface name')
    parser.add_argument('--duration', type=int, default=300, help='Monitoring duration (seconds)')
    parser.add_argument('--list', action='store_true', help='List available interfaces')
    
    args = parser.parse_args()
    
    if args.list:
        list_interfaces()
        return
    
    # Check admin privileges on Windows
    if sys.platform.startswith('win'):
        import ctypes
        if not ctypes.windll.shell32.IsUserAnAdmin():
            logger.error("❌ Please run as Administrator")
            logger.info("Right-click PowerShell -> Run as Administrator")
            return
    
    # Initialize detector
    detector = LiveWiFiDetector(
        interface=args.interface,
        model_path="models/best_model.keras"
    )
    
    # Start monitoring
    detector.start_monitoring(duration=args.duration)

if __name__ == "__main__":
    main()
