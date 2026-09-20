"""
Simple Blockchain Logs Viewer
Works with both simulation and real Fabric modes
No SDK required!
"""

import json
from pathlib import Path

# Where FL logs are stored (simulation mode)
LOG_FILE = Path(__file__).parent.parent / "fl_blockchain_logs.json"

def view_fl_logs():
    """Display all FL blockchain logs"""
    
    print("="*70)
    print("FL BLOCKCHAIN AUDIT TRAIL")
    print("="*70)
    print()
    
    if not LOG_FILE.exists():
        print("❌ No blockchain logs found yet")
        print(f"   Expected location: {LOG_FILE}")
        print()
        print("Run FL training to generate logs:")
        print("  python experiments/federated_learning/run_realtime_fl.py")
        return
    
    # Load logs
    with open(LOG_FILE, 'r') as f:
        logs = json.load(f)
    
    print(f"✅ Found {len(logs)} blockchain transactions")
    print()
    
    # Group by node
    nodes = {}
    for log in logs:
        node_id = log.get('node_id', 'unknown')
        if node_id not in nodes:
            nodes[node_id] = []
        nodes[node_id].append(log)
    
    print(f"Registered Nodes: {len(nodes)}")
    print("-"*70)
    for node_id in sorted(nodes.keys()):
        print(f"  • {node_id} ({len(nodes[node_id])} operations)")
    
    print()
    print("="*70)
    print("TRANSACTION DETAILS")
    print("="*70)
    
    for i, log in enumerate(logs, 1):
        print(f"\n[Transaction #{i}]")
        print(f"  Node ID    : {log.get('node_id')}")
        print(f"  Round      : {log.get('round_num')}")
        print(f"  Accuracy   : {log.get('accuracy', 0):.4f}")
        print(f"  Loss       : {log.get('loss', 0):.4f}")
        print(f"  Timestamp  : {log.get('timestamp')}")
        print("-"*70)
    
    # Summary by round
    print("\n" + "="*70)
    print("SUMMARY BY ROUND")
    print("="*70)
    
    rounds = {}
    for log in logs:
        rnd = log.get('round_num', 0)
        if rnd not in rounds:
            rounds[rnd] = []
        rounds[rnd].append(log)
    
    for rnd in sorted(rounds.keys()):
        round_logs = rounds[rnd]
        avg_acc = sum(l.get('accuracy', 0) for l in round_logs) / len(round_logs)
        avg_loss = sum(l.get('loss', 0) for l in round_logs) / len(round_logs)
        
        print(f"\nRound {rnd}:")
        print(f"  Participants: {len(round_logs)}")
        print(f"  Avg Accuracy: {avg_acc:.4f}")
        print(f "  Avg Loss: {avg_loss:.4f}")
        print(f"  Nodes: {', '.join([l.get('node_id') for l in round_logs])}")

if __name__ == "__main__":
    view_fl_logs()
