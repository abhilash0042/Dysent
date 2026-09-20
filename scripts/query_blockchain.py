"""
Query Hyperledger Fabric Blockchain for FL Node Registrations
Display all logged FL operations and node activities
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from projects.shared_libs.hyperledger_fabric_client import HyperledgerFabricClient
import json
from datetime import datetime

def display_all_blockchain_records():
    """Display all FL operations logged to blockchain"""
    
    print("="*70)
    print("BLOCKCHAIN FL AUDIT TRAIL")
    print("="*70)
    print()
    
    try:
        # Connect to blockchain
        client = HyperledgerFabricClient()
        
        if client.simulation_mode:
            print("⚠️  Running in SIMULATION mode")
            print("   (Still shows logged operations)")
        else:
            print("✅ Connected to REAL Hyperledger Fabric")
        
        print()
        
        # Query all records
        records = client.query_all_records()
        
        if not records:
            print("No records found in blockchain")
            return
        
        print(f"Total transactions logged: {len(records)}")
        print()
        print("="*70)
        
        # Group by node
        nodes = {}
        for record in records:
            node_id = record.get('node_id', 'unknown')
            if node_id not in nodes:
                nodes[node_id] = []
            nodes[node_id].append(record)
        
        print(f"\nRegistered Nodes: {len(nodes)}")
        print("-"*70)
        for node_id in sorted(nodes.keys()):
            print(f"  • {node_id} ({len(nodes[node_id])} operations)")
        
        print()
        print("="*70)
        print("DETAILED TRANSACTION LOG")
        print("="*70)
        
        # Display each record
        for i, record in enumerate(records, 1):
            print(f"\n[Transaction #{i}]")
            print(f"  Transaction ID : {record.get('tx_id', 'N/A')}")
            print(f"  Node ID        : {record.get('node_id', 'N/A')}")
            print(f"  Round Number   : {record.get('round_num', 'N/A')}")
            print(f"  Accuracy       : {record.get('accuracy', 'N/A')}")
            print(f"  Loss           : {record.get('loss', 'N/A')}")
            print(f"  Timestamp      : {record.get('timestamp', 'N/A')}")
            
            # Metadata
            metadata = record.get('metadata', {})
            if metadata:
                print(f"  Metadata       :")
                for key, value in metadata.items():
                    print(f"    - {key}: {value}")
            
            print("-"*70)
        
        print()
        print("="*70)
        print("SUMMARY BY ROUND")
        print("="*70)
        
        # Group by round
        rounds = {}
        for record in records:
            round_num = record.get('round_num', 0)
            if round_num not in rounds:
                rounds[round_num] = []
            rounds[round_num].append(record)
        
        for round_num in sorted(rounds.keys()):
            round_records = rounds[round_num]
            avg_acc = sum(r.get('accuracy', 0) for r in round_records) / len(round_records)
            avg_loss = sum(r.get('loss', 0) for r in round_records) / len(round_records)
            
            print(f"\nRound {round_num}:")
            print(f"  Nodes participated: {len(round_records)}")
            print(f"  Avg Accuracy: {avg_acc:.4f}")
            print(f"  Avg Loss: {avg_loss:.4f}")
            print(f"  Nodes: {', '.join([r.get('node_id', 'unknown') for r in round_records])}")
        
        print()
        print("="*70)
        print(f"✅ Successfully retrieved {len(records)} blockchain records")
        print("="*70)
        
    except Exception as e:
        print(f"❌ Error querying blockchain: {e}")
        import traceback
        traceback.print_exc()

def query_by_node(node_id):
    """Query records for specific node"""
    
    print(f"\n{'='*70}")
    print(f"BLOCKCHAIN RECORDS FOR NODE: {node_id}")
    print(f"{'='*70}\n")
    
    client = HyperledgerFabricClient()
    records = client.query_by_node(node_id)
    
    if not records:
        print(f"No records found for node: {node_id}")
        return
    
    print(f"Total operations by {node_id}: {len(records)}\n")
    
    for i, record in enumerate(records, 1):
        print(f"Operation {i}:")
        print(f"  Round: {record.get('round_num')}")
        print(f"  Accuracy: {record.get('accuracy', 0):.4f}")
        print(f"  Loss: {record.get('loss', 0):.4f}")
        print(f"  Timestamp: {record.get('timestamp')}")
        print()

def query_by_round(round_num):
    """Query records for specific FL round"""
    
    print(f"\n{'='*70}")
    print(f"BLOCKCHAIN RECORDS FOR ROUND: {round_num}")
    print(f"{'='*70}\n")
    
    client = HyperledgerFabricClient()
    records = client.query_by_round(round_num)
    
    if not records:
        print(f"No records found for round: {round_num}")
        return
    
    print(f"Nodes participated in Round {round_num}: {len(records)}\n")
    
    for record in records:
        print(f"Node: {record.get('node_id')}")
        print(f"  Accuracy: {record.get('accuracy', 0):.4f}")
        print(f"  Loss: {record.get('loss', 0):.4f}")
        print()

def export_to_json(output_file="blockchain_audit.json"):
    """Export all blockchain records to JSON"""
    
    client = HyperledgerFabricClient()
    records = client.query_all_records()
    
    with open(output_file, 'w') as f:
        json.dump(records, f, indent=2)
    
    print(f"✅ Exported {len(records)} records to {output_file}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Query FL Blockchain Audit Trail")
    parser.add_argument('--all', action='store_true', help='Show all records')
    parser.add_argument('--node', type=str, help='Query specific node')
    parser.add_argument('--round', type=int, help='Query specific round')
    parser.add_argument('--export', type=str, help='Export to JSON file')
    
    args = parser.parse_args()
    
    if args.export:
        export_to_json(args.export)
    elif args.node:
        query_by_node(args.node)
    elif args.round is not None:
        query_by_round(args.round)
    else:
        # Default: show all
        display_all_blockchain_records()
