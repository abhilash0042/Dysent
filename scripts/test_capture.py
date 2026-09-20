"""
Quick Test: Verify Packet Capture is Working
Run this before FL experiment to ensure traffic capture works
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from projects.shared_libs.stream_processor import PacketStreamProcessor
import time

print("="*60)
print("PACKET CAPTURE TEST")
print("="*60)
print("\nThis will attempt to capture 50 packets in 10 seconds")
print("Make sure you're generating traffic!")
print("\nSuggestions:")
print("  - Browse some websites")
print("  - Run: ping -t google.com")
print("  - Run: python scripts/advanced_traffic_generator.py")
print("\n" + "="*60 + "\n")

input("Press Enter when traffic is running...")

print("\nStarting capture...\n")

processor = PacketStreamProcessor(
    interface=None,  # All interfaces
    packet_count=50,  # Just 50 packets
    timeout=10
)

count = 0
start_time = time.time()

for features in processor.stream_features():
    count += 1
    if count <= 10:  # Show first 10
        print(f"Packet {count}: shape={features.shape}, min={features.min():.3f}, max={features.max():.3f}")
    elif count == 11:
        print("  ... (capturing remaining packets)")

duration = time.time() - start_time

# Show results
print(f"\n{'='*60}")
print("RESULTS")
print(f"{'='*60}")

if count > 0:
    print(f"✅ SUCCESS: Captured {count} packets in {duration:.1f}s")
    print(f"   Rate: {count/duration:.1f} packets/second")
    print("\nYour system is ready for real-time FL!")
    print("\nNext steps:")
    print("  1. Keep traffic generator running")
    print("  2. Run: python experiments/federated_learning/run_realtime_fl.py")
else:
    print(f"⚠ WARNING: No packets captured in {duration:.1f}s")
    print("\nTroubleshooting:")
    print("  1. Make sure traffic is actively being generated")
    print("  2. Check network interfaces (use scapy.all.get_if_list())")
    print("  3. Run as Administrator (Windows) or with sudo (Linux)")
    print("  4. Try specifying interface explicitly")

stats = processor.get_statistics()
print(f"\nDetailed Statistics:")
print(f"  Packets processed: {stats['packets_processed']}")
print(f"  Active flows: {stats['active_flows']}")
print(f"  Duration: {stats['duration_seconds']:.2f}s")
print(f"  Interface: {stats['interface']}")
print(f"{'='*60}\n")
