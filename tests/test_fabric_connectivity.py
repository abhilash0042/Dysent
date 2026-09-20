"""
Quick test to verify Fabric network connectivity from Windows
"""

import socket

def test_fabric_connectivity():
    """Test if Fabric orderer is reachable from Windows"""
    
    print("Testing Hyperledger Fabric Network Connectivity...")
    print("=" * 60)
    
    # Test orderer
    services = [
        ("Orderer", "localhost", 7050),
        ("Peer Client1", "localhost", 7051),
        ("Peer Client2", "localhost", 8051),
        ("Peer Client3", "localhost", 9051),
    ]
    
    results = {}
    
    for name, host, port in services:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            
            if result == 0:
                print(f"✅ {name:20s} ({host}:{port}) - REACHABLE")
                results[name] = True
            else:
                print(f"❌ {name:20s} ({host}:{port}) - NOT REACHABLE")
                results[name] = False
        except Exception as e:
            print(f"❌ {name:20s} ({host}:{port}) - ERROR: {e}")
            results[name] = False
    
    print("=" * 60)
    
    reachable = sum(results.values())
    total = len(results)
    
    print(f"\nReachability: {reachable}/{total} services")
    
    if reachable == total:
        print("\n🎉 All Fabric services are accessible from Windows!")
        print("You can now connect Python to the real blockchain.")
    elif reachable > 0:
        print("\n⚠️  Some services reachable. Check Docker port mapping.")
    else:
        print("\n❌ No services reachable. Docker network not exposed to Windows.")
        print("\nTo fix:")
        print("1. Check docker-compose.yaml has correct port mappings")
        print("2. Ensure Docker Desktop is running with WSL integration")
        print("3. Restart Docker network: docker compose restart")
    
    return reachable == total

if __name__ == "__main__":
    test_fabric_connectivity()
