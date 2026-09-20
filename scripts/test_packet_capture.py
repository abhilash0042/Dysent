"""
Simple packet viewer to test if capture is working
Shows real-time packets as they're captured
"""

from scapy.all import sniff, get_if_list
import time

def packet_callback(packet):
    """Show each packet"""
    timestamp = time.strftime('%H:%M:%S')
    
    # Try to get IP layer info
    if packet.haslayer('IP'):
        src = packet['IP'].src
        dst = packet['IP'].dst
        proto = packet['IP'].proto
        print(f"[{timestamp}] {src} -> {dst} (Protocol: {proto})")
    else:
        print(f"[{timestamp}] Non-IP packet: {packet.summary()}")

def test_capture(interface, duration=30):
    """Test packet capture"""
    
    print("\n" + "="*70)
    print("PACKET CAPTURE TEST")
    print("="*70)
    print(f"Interface: {interface}")
    print(f"Duration: {duration} seconds")
    print("\nIf you see packets appearing below, capture is working!")
    print("Try browsing a website to generate traffic...")
    print("="*70 + "\n")
    
    packet_count = [0]  # Use list to modify in callback
    
    def count_callback(pkt):
        packet_count[0] += 1
        packet_callback(pkt)
    
    try:
        sniff(
            iface=interface,
            prn=count_callback,
            store=False,
            timeout=duration
        )
    except KeyboardInterrupt:
        print("\n\nStopped by user")
    except Exception as e:
        print(f"\n\nError: {e}")
    
    print("\n" + "="*70)
    print(f"TOTAL PACKETS CAPTURED: {packet_count[0]}")
    print("="*70)
    
    if packet_count[0] == 0:
        print("\n⚠️  No packets captured!")
        print("\nTroubleshooting:")
        print("1. This interface might not be active")
        print("2. Try a different interface:")
        print("\n   Available interfaces:")
        for i, iface in enumerate(get_if_list(), 1):
            print(f"   {i}. {iface}")
        print("\n3. While running, browse websites or use internet")
        print("4. Check if Npcap is installed correctly")
    else:
        print(f"\n✅ Capture working! Received {packet_count[0]} packets")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        interface = sys.argv[1]
    else:
        print("Usage: python test_packet_capture.py <interface>")
        print("\nAvailable interfaces:")
        for i, iface in enumerate(get_if_list(), 1):
            print(f"  {i}. {iface}")
        sys.exit(1)
    
    test_capture(interface, duration=30)
