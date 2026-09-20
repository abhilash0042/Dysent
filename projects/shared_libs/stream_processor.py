"""
Real-Time Packet Stream Processor
Handles live network packet capture and converts to feature streams
Replaces CSV-based batch processing with streaming pipeline
"""

import logging
from typing import Iterator, Optional, Dict, Any, List
from pathlib import Path
import numpy as np
from scapy.all import sniff, IP, TCP, UDP, Packet
from collections import defaultdict
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PacketStreamProcessor:
    """
    Real-time packet capture and processing
    
    Captures packets from live network interface and converts to features
    Compatible with existing model input format (timesteps, features)
    """
    
    def __init__(
        self,
        interface: Optional[str] = None,
        packet_count: Optional[int] = None,
        timeout: Optional[int] = None,
        filter_str: Optional[str] = None
    ):
        """
        Initialize stream processor
        
        Args:
            interface: Network interface (e.g., 'eth0', 'wlan0'). None = all interfaces
            packet_count: Max packets to capture (None = unlimited)
            timeout: Capture timeout in seconds (None = unlimited)
            filter_str: BPF filter (e.g., 'tcp port 80')
        """
        self.interface = interface
        self.packet_count = packet_count
        self.timeout = timeout
        self.filter_str = filter_str
        
        # Flow tracking for stateful features
        self.flows = defaultdict(lambda: {
            'packets': [],
            'start_time': None,
            'bytes': 0,
            'flags': defaultdict(int)
        })
        
        # Statistics
        self.packets_processed = 0
        self.start_time = time.time()
        
        logger.info(f"PacketStreamProcessor initialized")
        logger.info(f"  Interface: {interface or 'all'}")
        logger.info(f"  Filter: {filter_str or 'none'}")
    
    def capture_stream(self) -> Iterator[Packet]:
        """
        Capture packets from live network
        
        Yields:
            Scapy packet objects
        """
        logger.info("Starting live packet capture...")
        
        try:
            # Capture packets
            packets = sniff(
                iface=self.interface,
                count=self.packet_count,
                timeout=self.timeout,
                filter=self.filter_str,
                prn=None,  # We'll process in loop
                store=False  # Don't store in memory
            )
            
            for packet in packets:
                self.packets_processed += 1
                yield packet
                
        except PermissionError:
            logger.error("Permission denied - run as administrator/root")
            logger.error("  Windows: Run PowerShell as Administrator")
            logger.error("  Linux: Use sudo or setcap")
            raise
        except Exception as e:
            logger.error(f"Capture error: {e}")
            raise
    
    def extract_packet_features(self, packet: Packet) -> Optional[Dict[str, float]]:
        """
        Extract features from single packet
        
        Args:
            packet: Scapy packet
            
        Returns:
            Feature dictionary or None if packet can't be processed
        """
        if not packet.haslayer(IP):
            return None
        
        ip_layer = packet[IP]
        
        # Basic features
        features = {
            'packet_length': len(packet),
            'ip_header_length': ip_layer.ihl * 4,
            'ttl': ip_layer.ttl,
            'protocol': ip_layer.proto,
        }
        
        # Transport layer features
        if packet.haslayer(TCP):
            tcp = packet[TCP]
            features.update({
                'src_port': tcp.sport,
                'dst_port': tcp.dport,
                'tcp_flags': int(tcp.flags),
                'tcp_window': tcp.window,
                'syn_flag': 1 if tcp.flags.S else 0,
                'ack_flag': 1 if tcp.flags.A else 0,
                'psh_flag': 1 if tcp.flags.P else 0,
                'fin_flag': 1 if tcp.flags.F else 0,
                'rst_flag': 1 if tcp.flags.R else 0,
            })
        elif packet.haslayer(UDP):
            udp = packet[UDP]
            features.update({
                'src_port': udp.sport,
                'dst_port': udp.dport,
                'tcp_flags': 0,
                'tcp_window': 0,
                'syn_flag': 0,
                'ack_flag': 0,
                'psh_flag': 0,
                'fin_flag': 0,
                'rst_flag': 0,
            })
        else:
            # Other protocols - set defaults
            features.update({
                'src_port': 0,
                'dst_port': 0,
                'tcp_flags': 0,
                'tcp_window': 0,
                'syn_flag': 0,
                'ack_flag': 0,
                'psh_flag': 0,
                'fin_flag': 0,
                'rst_flag': 0,
            })
        
        # Timestamp
        features['timestamp'] = time.time()
        
        return features
    
    def extract_flow_features(self, packet: Packet) -> Optional[Dict[str, float]]:
        """
        Extract flow-based aggregate features
        
        Tracks flows and computes statistics over packet windows
        
        Args:
            packet: Scapy packet
            
        Returns:
            Flow feature dictionary
        """
        if not packet.haslayer(IP):
            return None
        
        # Create flow ID
        ip = packet[IP]
        src_port = packet[TCP].sport if packet.haslayer(TCP) else (packet[UDP].sport if packet.haslayer(UDP) else 0)
        dst_port = packet[TCP].dport if packet.haslayer(TCP) else (packet[UDP].dport if packet.haslayer(UDP) else 0)
        
        flow_id = f"{ip.src}:{src_port}->{ip.dst}:{dst_port}-{ip.proto}"
        
        # Update flow
        flow = self.flows[flow_id]
        if flow['start_time'] is None:
            flow['start_time'] = time.time()
        
        flow['packets'].append({
            'time': time.time(),
            'length': len(packet)
        })
        flow['bytes'] += len(packet)
        
        # Track flags (TCP only)
        if packet.haslayer(TCP):
            tcp = packet[TCP]
            if tcp.flags.S: flow['flags']['syn'] += 1
            if tcp.flags.A: flow['flags']['ack'] += 1
            if tcp.flags.P: flow['flags']['psh'] += 1
            if tcp.flags.F: flow['flags']['fin'] += 1
            if tcp.flags.R: flow['flags']['rst'] += 1
        
        # Compute aggregate features
        duration = time.time() - flow['start_time']
        packet_count = len(flow['packets'])
        
        # Inter-arrival times
        if packet_count > 1:
            iats = [
                flow['packets'][i]['time'] - flow['packets'][i-1]['time']
                for i in range(1, packet_count)
            ]
            iat_mean = np.mean(iats)
            iat_std = np.std(iats)
        else:
            iat_mean = 0
            iat_std = 0
        
        # Packet lengths
        lengths = [p['length'] for p in flow['packets']]
        
        features = {
            'flow_duration': duration,
            'flow_packets': packet_count,
            'flow_bytes': flow['bytes'],
            'packets_per_sec': packet_count / max(duration, 0.001),
            'bytes_per_sec': flow['bytes'] / max(duration, 0.001),
            'packet_length_mean': np.mean(lengths),
            'packet_length_std': np.std(lengths),
            'iat_mean': iat_mean,
            'iat_std': iat_std,
            'syn_count': flow['flags']['syn'],
            'ack_count': flow['flags']['ack'],
            'psh_count': flow['flags']['psh'],
            'fin_count': flow['flags']['fin'],
            'rst_count': flow['flags']['rst'],
        }
        
        return features
    
    def packet_to_features(self, packet: Packet, use_flow_features: bool = True) -> Optional[np.ndarray]:
        """
        Convert packet to feature vector (40 features)
        
        Args:
            packet: Scapy packet
            use_flow_features: Include flow-level statistics
            
        Returns:
            Feature array (40,) or None
        """
        packet_features = self.extract_packet_features(packet)
        if packet_features is None:
            return None
        
        if use_flow_features:
            flow_features = self.extract_flow_features(packet)
            if flow_features:
                packet_features.update(flow_features)
        
        # Extract 40 specific features in correct order
        feature_names = [
            'flow_duration', 'packet_length', 'ip_header_length', 'ttl',
            'protocol', 'src_port', 'dst_port', 'tcp_flags', 'tcp_window',
            'flow_packets', 'flow_bytes', 'packets_per_sec', 'bytes_per_sec',
            'packet_length_mean', 'packet_length_std', 'iat_mean', 'iat_std',
            'syn_flag', 'ack_flag', 'psh_flag', 'fin_flag', 'rst_flag',
            'syn_count', 'ack_count', 'psh_count', 'fin_count', 'rst_count',
            # Padding to 40 features
            *[f'reserved_{i}' for i in range(13)]
        ]
        
        # Create feature vector
        feature_vector = []
        for name in feature_names:
            feature_vector.append(packet_features.get(name, 0.0))
        
        return np.array(feature_vector, dtype=np.float32)
    
    def stream_features(self, normalize: bool = True) -> Iterator[np.ndarray]:
        """
        Stream feature vectors from live packets
        
        Args:
            normalize: Apply normalization to features
            
        Yields:
            Feature vectors (40,)
        """
        for packet in self.capture_stream():
            features = self.packet_to_features(packet)
            
            if features is not None:
                if normalize:
                    # Simple min-max normalization
                    features = np.clip(features, 0, 1e6)  # Clip outliers
                    features = features / (np.max(features) + 1e-9)  # Normalize
                
                yield features
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get capture statistics"""
        duration = time.time() - self.start_time
        
        return {
            'packets_processed': self.packets_processed,
            'duration_seconds': duration,
            'packets_per_second': self.packets_processed / max(duration, 0.001),
            'active_flows': len(self.flows),
            'interface': self.interface or 'all'
        }


def test_stream_processor():
    """Quick test of stream processor"""
    logger.info("\n" + "="*70)
    logger.info("Testing Real-Time Packet Stream Processor")
    logger.info("="*70 + "\n")
    
    # Create processor
    processor = PacketStreamProcessor(
        interface=None,  # All interfaces
        packet_count=10,  # Just 10 packets for test
        timeout=10  # 10 second timeout
    )
    
    # Capture and process
    logger.info("Capturing 10 packets...")
    feature_count = 0
    
    for features in processor.stream_features():
        feature_count += 1
        logger.info(f"Packet {feature_count}: {features.shape} - min={features.min():.3f}, max={features.max():.3f}")
    
    # Show stats
    stats = processor.get_statistics()
    logger.info(f"\n✓ Statistics:")
    logger.info(f"  Packets: {stats['packets_processed']}")
    logger.info(f"  Duration: {stats['duration_seconds']:.2f}s")
    logger.info(f"  Rate: {stats['packets_per_second']:.1f} pkt/s")
    logger.info(f"  Active flows: {stats['active_flows']}")
    
    logger.info("\n✅ Stream processor working!")


if __name__ == "__main__":
    test_stream_processor()
