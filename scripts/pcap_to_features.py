#!/usr/bin/env python3
"""
PCAP to Feature Converter
Converts PCAP files to CSV features compatible with FL-DDoS system
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scapy.all import rdpcap, IP, TCP, UDP, ICMP
import numpy as np
import pandas as pd
from typing import Dict, List, Optional

class PcapFeatureExtractor:
    """Extract features from PCAP files for FL system"""
    
    def __init__(self):
        self.feature_names = [
            'pkt_length', 'pkt_ttl', 'pkt_protocol',
            'src_port', 'dst_port',
            'tcp_flags_syn', 'tcp_flags_ack', 'tcp_flags_fin',
            'tcp_flags_rst', 'tcp_flags_psh', 'tcp_flags_urg',
            'tcp_window_size', 'payload_size'
        ]
    
    def extract_features(self, packet) -> Optional[Dict[str, float]]:
        """Extract features from single packet"""
        if not packet.haslayer(IP):
            return None
        
        features = {}
        ip_layer = packet[IP]
        
        # Basic packet features
        features['pkt_length'] = float(len(packet))
        features['pkt_ttl'] = float(ip_layer.ttl)
        features['pkt_protocol'] = float(ip_layer.proto)
        
        # TCP/UDP features
        if packet.haslayer(TCP):
            tcp = packet[TCP]
            features['src_port'] = float(tcp.sport)
            features['dst_port'] = float(tcp.dport)
            features['tcp_flags_syn'] = float(tcp.flags.S)
            features['tcp_flags_ack'] = float(tcp.flags.A)
            features['tcp_flags_fin'] = float(tcp.flags.F)
            features['tcp_flags_rst'] = float(tcp.flags.R)
            features['tcp_flags_psh'] = float(tcp.flags.P)
            features['tcp_flags_urg'] = float(tcp.flags.U)
            features['tcp_window_size'] = float(tcp.window)
            features['payload_size'] = float(len(tcp.payload))
        elif packet.haslayer(UDP):
            udp = packet[UDP]
            features['src_port'] = float(udp.sport)
            features['dst_port'] = float(udp.dport)
            # Fill TCP-specific with defaults
            for key in ['tcp_flags_syn', 'tcp_flags_ack', 'tcp_flags_fin',
                       'tcp_flags_rst', 'tcp_flags_psh', 'tcp_flags_urg',
                       'tcp_window_size']:
                features[key] = 0.0
            features['payload_size'] = float(len(udp.payload))
        else:
            # ICMP or other
            for key in ['src_port', 'dst_port', 'tcp_flags_syn', 'tcp_flags_ack',
                       'tcp_flags_fin', 'tcp_flags_rst', 'tcp_flags_psh',
                       'tcp_flags_urg', 'tcp_window_size', 'payload_size']:
                features[key] = 0.0
        
        return features
    
    def pcap_to_dataframe(
        self,
        pcap_file: str,
        max_packets: int = 10000,
        label: int = 0  # 0=benign, 1=attack
    ) -> pd.DataFrame:
        """
        Convert PCAP to DataFrame
        
        Args:
            pcap_file: Path to PCAP file
            max_packets: Maximum packets to process
            label: Label for all packets (0 or 1)
        
        Returns:
            DataFrame with features
        """
        print(f"Loading PCAP: {pcap_file}")
        packets = rdpcap(pcap_file)
        total_packets = len(packets)
        print(f"Loaded {total_packets} packets")
        
        features_list = []
        
        for idx, packet in enumerate(packets[:max_packets]):
            features = self.extract_features(packet)
            
            if features:
                features_list.append(features)
            
            if idx % 1000 == 0 and idx > 0:
                print(f"Processed {idx}/{min(max_packets, total_packets)} packets")
        
        # Create DataFrame
        df = pd.DataFrame(features_list)
        df['label'] = label
        
        print(f"Extracted features from {len(df)} packets")
        return df


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Convert PCAP to CSV features for FL-DDoS system"
    )
    parser.add_argument("pcap_file", help="Input PCAP file")
    parser.add_argument("output_csv", help="Output CSV file")
    parser.add_argument(
        "--max-packets",
        type=int,
        default=10000,
        help="Maximum packets to process (default: 10000)"
    )
    parser.add_argument(
        "--label",
        type=int,
        default=0,
        choices=[0, 1],
        help="Label for packets: 0=benign, 1=attack (default: 0)"
    )
    
    args = parser.parse_args()
    
    # Convert PCAP
    extractor = PcapFeatureExtractor()
    df = extractor.pcap_to_dataframe(
        args.pcap_file,
        max_packets=args.max_packets,
        label=args.label
    )
    
    # Save to CSV
    df.to_csv(args.output_csv, index=False)
    print(f"\n✅ Saved {len(df)} packet features to {args.output_csv}")
    
    # Show statistics
    print(f"\nDataset Statistics:")
    print(f"  Total packets: {len(df)}")
    print(f"  Features: {len(df.columns)-1}")  # -1 for label
    print(f"  Label distribution: {df['label'].value_counts().to_dict()}")
    print(f"\nSample features:")
    print(df.head())


if __name__ == "__main__":
    main()
