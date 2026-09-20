"""
Advanced Network Traffic Generator
Generates various types of network traffic for real-time capture testing
"""

import socket
import time
import subprocess
import threading
import sys
from concurrent.futures import ThreadPoolExecutor

class TrafficGenerator:
    """Generate various types of network traffic"""
    
    def __init__(self):
        self.active = False
        self.stats = {
            'dns': 0,
            'icmp': 0,
            'http': 0
        }
    
    def start(self, duration=120):
        """
        Start generating traffic
        
        Args:
            duration: How long to generate traffic (seconds)
        """
        print(f"\n{'='*60}")
        print(f"Starting traffic generation for {duration} seconds...")
        print(f"{'='*60}\n")
        self.active = True
        
        # Create threads for different traffic types
        threads = [
            threading.Thread(target=self.generate_dns_traffic, args=(duration,), name="DNS"),
            threading.Thread(target=self.generate_icmp_traffic, args=(duration,), name="ICMP"),
            threading.Thread(target=self.generate_http_traffic, args=(duration,), name="HTTP")
        ]
        
        # Start all threads
        for t in threads:
            t.daemon = True
            t.start()
        
        # Wait for completion
        try:
            for t in threads:
                t.join()
        except KeyboardInterrupt:
            print("\n\nStopping traffic generation...")
            self.active = False
        
        self.active = False
        self.print_stats()
    
    def generate_dns_traffic(self, duration):
        """Generate DNS queries"""
        domains = [
            "google.com", "github.com", "python.org", 
            "stackoverflow.com", "wikipedia.org", "reddit.com"
        ]
        end_time = time.time() + duration
        
        while time.time() < end_time and self.active:
            domain = domains[self.stats['dns'] % len(domains)]
            try:
                ip = socket.gethostbyname(domain)
                print(f"[DNS] Resolved {domain} → {ip}")
                self.stats['dns'] += 1
            except Exception as e:
                print(f"[DNS] Error resolving {domain}: {e}")
            time.sleep(2)
    
    def generate_icmp_traffic(self, duration):
        """Generate ICMP (ping) traffic"""
        targets = ["8.8.8.8", "1.1.1.1", "8.8.4.4"]
        end_time = time.time() + duration
        
        while time.time() < end_time and self.active:
            target = targets[self.stats['icmp'] % len(targets)]
            try:
                # Windows ping syntax
                result = subprocess.run(
                    ["ping", "-n", "1", "-w", "2000", target],
                    capture_output=True,
                    timeout=3,
                    text=True
                )
                if result.returncode == 0:
                    print(f"[ICMP] Pinged {target} ✓")
                    self.stats['icmp'] += 1
                else:
                    print(f"[ICMP] Ping {target} failed")
            except Exception as e:
                print(f"[ICMP] Error pinging {target}: {e}")
            time.sleep(2)
    
    def generate_http_traffic(self, duration):
        """Generate HTTP traffic"""
        try:
            import requests
        except ImportError:
            print("[HTTP] requests library not available - skipping HTTP traffic")
            return
        
        urls = [
            "https://www.google.com",
            "https://github.com",
            "https://www.python.org",
            "https://stackoverflow.com",
            "https://www.wikipedia.org"
        ]
        
        end_time = time.time() + duration
        
        while time.time() < end_time and self.active:
            url = urls[self.stats['http'] % len(urls)]
            try:
                response = requests.get(url, timeout=5)
                print(f"[HTTP] {url[:30]}... → {response.status_code}")
                self.stats['http'] += 1
            except Exception as e:
                print(f"[HTTP] Error fetching {url[:30]}...: {e}")
            time.sleep(3)
    
    def print_stats(self):
        """Print final statistics"""
        total = sum(self.stats.values())
        print(f"\n{'='*60}")
        print("TRAFFIC GENERATION COMPLETE")
        print(f"{'='*60}")
        print(f"Total requests: {total}")
        print(f"  DNS queries: {self.stats['dns']}")
        print(f"  ICMP pings: {self.stats['icmp']}")
        print(f"  HTTP requests: {self.stats['http']}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    print("="*60)
    print("ADVANCED NETWORK TRAFFIC GENERATOR")
    print("="*60)
    print("\nThis will generate:")
    print("  ✓ DNS queries (every 2s)")
    print("  ✓ ICMP pings (every 2s)")
    print("  ✓ HTTP requests (every 3s)")
    print("\nDefault duration: 120 seconds")
    print("\nPress Ctrl+C to stop early\n")
    
    # Allow custom duration
    if len(sys.argv) > 1:
        try:
            duration = int(sys.argv[1])
        except:
            duration = 120
    else:
        duration = 120
    
    print(f"Run your FL experiment in another terminal NOW!")
    print("The experiment should start IMMEDIATELY after traffic begins\n")
    
    input("Press Enter to start generating traffic...")
    
    generator = TrafficGenerator()
    generator.start(duration=duration)
    
    print("✓ You can now run another test or experiment")
