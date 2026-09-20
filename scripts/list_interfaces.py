"""
Helper script to list network interfaces
"""

from scapy.all import get_if_list

def list_interfaces_detailed():
    """List all network interfaces"""
    
    print("\n" + "="*70)
    print("AVAILABLE NETWORK INTERFACES")
    print("="*70 + "\n")
    
    interfaces = get_if_list()
    
    print(f"Found {len(interfaces)} interfaces:\n")
    
    for i, iface in enumerate(interfaces, 1):
        print(f"{i}. {iface}")
    
    print("\n" + "="*70)
    print("HOW TO USE:")
    print("="*70)
    print("\n1. Copy one of the device names above")
    print("2. Run with that interface:")
    print('   python ddosdfl/scripts/live_wifi_detector.py --interface "\\Device\\NPF_{YOUR-GUID}"')
    print("\n3. Usually the FIRST non-Loopback interface is your WiFi/Ethernet")
    print(f"   Try: python ddosdfl/scripts/live_wifi_detector.py --interface \"{interfaces[0]}\"")
    print("="*70 + "\n")

if __name__ == "__main__":
    list_interfaces_detailed()
    
    print()

if __name__ == "__main__":
    list_interfaces_detailed()
