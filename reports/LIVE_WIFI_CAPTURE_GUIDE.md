# 📡 Live WiFi Traffic Capture for Real-Time Testing

## Prerequisites

### Windows Setup

```bash
# Install Npcap (WinPcap replacement)
# Download from: https://npcap.com/#download
# During installation, check "Install Npcap in WinPcap API-compatible Mode"

# Install Scapy
pip install scapy
```

### Required Permissions

- **Windows:** Run Python as Administrator
- **Linux:** Run with `sudo`

---

## Method 1: Basic Packet Capture (Scapy)

### Step 1: Install Dependencies

```bash
pip install scapy pandas numpy
```

### Step 2: Find Your WiFi Interface

```python
# File: scripts/find_interfaces.py
from scapy.all import get_if_list

print("Available network interfaces:")
for i, iface in enumerate(get_if_list(), 1):
    print(f"  {i}. {iface}")
```

**Run it:**

```bash
python scripts/find_interfaces.py
```

**Example Output:**

```
Available network interfaces:
  1. \Device\NPF_{12345678-ABCD-...}  # This is your WiFi
  2. Loopback Pseudo-Interface 1
  3. Ethernet
```

### Step 3: Capture Live Packets

```python
# File: scripts/capture_live_wifi.py
from scapy.all import sniff, IP, TCP, UDP
import time

def packet_callback(packet):
    """Process each captured packet"""

    if packet.haslayer(IP):
        src_ip = packet[IP].src
        dst_ip = packet[IP].dst
        protocol = packet[IP].proto

        # Get transport layer info
        src_port = packet.sport if hasattr(packet, 'sport') else 0
        dst_port = packet.dport if hasattr(packet, 'dport') else 0

        print(f"[{time.strftime('%H:%M:%S')}] {src_ip}:{src_port} -> {dst_ip}:{dst_port} (Proto: {protocol})")

# Capture on WiFi interface
print("Starting packet capture... (Ctrl+C to stop)")
sniff(
    iface="Wi-Fi",  # Use your WiFi interface name
    prn=packet_callback,
    store=False,
    count=100  # Capture 100 packets then stop
)
```

**Run as Administrator:**

```powershell
# PowerShell (Run as Admin)
python scripts/capture_live_wifi.py
```

---

## Method 2: Feature Extraction for DDoS Detection

### Implementation

```python
# File: scripts/live_wifi_detector.py
"""
Capture live WiFi traffic and detect DDoS attacks with explanations
"""

import sys
from pathlib import Path
from scapy.all import sniff, IP, TCP, UDP
from collections import defaultdict
import time
import numpy as np
import requests

# Setup paths
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from ddosdfl.projects.shared_libs import CNNBiLSTMModel
from ddosdfl.projects.shared_libs.explainable_ai import create_explainer
from tensorflow import keras

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
        if model_path and Path(model_path).exists():
            self.model = keras.models.load_model(model_path)
        else:
            # Use pre-initialized model
            model_wrapper = CNNBiLSTMModel(input_shape=(10, 4), num_classes=2)
            self.model = model_wrapper.get_model()

        # Initialize explainer
        feature_names = ['packet_rate', 'packet_size', 'syn_ratio', 'flow_duration']
        self.explainer = create_explainer(self.model, feature_names)

        print(f"✅ Detector initialized on interface: {interface}")

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

        src_port =packet.sport if hasattr(packet, 'sport') else 0
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
            print(f"\n⚠️  ATTACK DETECTED!")
            print(f"Flow: {flow_key[0]}:{flow_key[2]} -> {flow_key[1]}:{flow_key[3]}")
            print(f"Confidence: {result['confidence']*100:.1f}%")
            print(f"Explanation: {result['explanation_text']}")

            if result['top_features']:
                print("Top Features:")
                for feat, contrib in result['top_features'].items():
                    print(f"  - {feat}: {contrib*100:.1f}%")

            # Send to dashboard (if running)
            try:
                requests.post('http://localhost:5000/api/attack_detected', json={
                    'prediction': result['prediction_label'],
                    'confidence': result['confidence'],
                    'explanation': result['explanation_text'],
                    'top_features': result['top_features']
                }, timeout=0.5)
            except:
                pass  # Dashboard not running

    def start_monitoring(self, duration=60):
        """Start live monitoring"""

        print(f"\n{'='*70}")
        print(f"🔴 LIVE WiFi MONITORING ACTIVE")
        print(f"Interface: {self.interface}")
        print(f"Duration: {duration}s (or Ctrl+C to stop)")
        print(f"{'='*70}\n")

        try:
            sniff(
                iface=self.interface,
                prn=self.process_packet,
                store=False,
                timeout=duration
            )
        except KeyboardInterrupt:
            print("\n\n✅ Monitoring stopped by user")
        except Exception as e:
            print(f"\n❌ Error: {e}")
            print("\nTroubleshooting:")
            print("  1. Run as Administrator (Windows) or with sudo (Linux)")
            print("  2. Install Npcap: https://npcap.com/")
            print("  3. Check interface name with: scapy.get_if_list()")

        print(f"\n{'='*70}")
        print(f"Monitoring complete. Analyzed {len(self.flows)} flows.")
        print(f"{'='*70}\n")

def main():
    """Run live WiFi detector"""

    # Initialize detector
    detector = LiveWiFiDetector(
        interface="Wi-Fi",  # Change to your WiFi interface
        model_path="models/best_model.keras"
    )

    # Start monitoring
    detector.start_monitoring(duration=300)  # Monitor for 5 minutes

if __name__ == "__main__":
    import sys
    if not sys.platform.startswith('win'):
        # Linux/Mac: Check for root
        import os
        if os.geteuid() != 0:
            print("❌ Please run with sudo")
            sys.exit(1)

    main()
```

---

## Method 3: Using Wireshark + Python

### Step 1: Capture with Wireshark

1. Open Wireshark
2. Select WiFi interface
3. Start capture
4. Save as `.pcap` file

### Step 2: Analyze PCAP with Python

```python
# File: scripts/analyze_pcap.py
from scapy.all import rdpcap
from ddosdfl.tests.test_realtime_detection import RealTimeExplainableDetector

def analyze_pcap(pcap_file):
    """Analyze saved PCAP file"""

    print(f"Loading {pcap_file}...")
    packets = rdpcap(pcap_file)
    print(f"Loaded {len(packets)} packets")

    # Process packets
    for packet in packets[:100]:  # First 100 packets
        if packet.haslayer('IP'):
            print(f"{packet['IP'].src} -> {packet['IP'].dst}")

# Usage
analyze_pcap("capture.pcap")
```

---

## Quick Start Commands

### Windows (PowerShell as Admin)

```powershell
# Find interface
python scripts/find_interfaces.py

# Start live monitoring
python scripts/live_wifi_detector.py

# With dashboard integration
# Terminal 1:
python projects/dashboard/app.py

# Terminal 2 (as Admin):
python scripts/live_wifi_detector.py
```

### Linux/WSL

```bash
# Install Scapy
sudo apt-get install python3-scapy

# Start monitoring
sudo python3 scripts/live_wifi_detector.py
```

---

## Expected Output

```
🔴 LIVE WiFi MONITORING ACTIVE
Interface: Wi-Fi
Duration: 300s (or Ctrl+C to stop)
======================================================================

[12:45:01] 192.168.1.100:443 -> 192.168.1.5:52134 (Proto: 6)
[12:45:01] 192.168.1.5:52134 -> 192.168.1.100:443 (Proto: 6)

⚠️  ATTACK DETECTED!
Flow: 10.0.0.5:0 -> 192.168.1.100:80
Confidence: 94.3%
Explanation: ⚠️ DDoS Attack detected with 94.3% confidence. Primary indicator: packet_rate (45.2% contribution).
Top Features:
  - packet_rate: 45.2%
  - syn_ratio: 32.1%
  - packet_size: 22.7%

======================================================================
```

---

## Troubleshooting

### Issue 1: "Permission denied"

**Solution:** Run as Administrator (Windows) or with `sudo` (Linux)

### Issue 2: "No such device"

**Solution:** Check interface name

```python
from scapy.all import get_if_list
print(get_if_list())
```

### Issue 3: Npcap not installed

**Solution:** Download and install from https://npcap.com/

### Issue 4: Too many packets

**Solution:** Add BPF filter

```python
sniff(iface="Wi-Fi", filter="tcp port 80", prn=callback)
```

---

## Safety & Legal

⚠️ **IMPORTANT:**

- Only monitor YOUR OWN network
- Get permission before capturing traffic
- Don't capture sensitive data (HTTPS is encrypted anyway)
- Comply with local laws

---

## Performance Tips

### 1. Filter Traffic

```python
# Only capture HTTP/HTTPS
sniff(iface="Wi-Fi", filter="tcp port 80 or tcp port 443", ...)
```

### 2. Batch Processing

```python
# Process every 100 packets
packet_buffer = []
def callback(packet):
    packet_buffer.append(packet)
    if len(packet_buffer) >= 100:
        process_batch(packet_buffer)
        packet_buffer.clear()
```

### 3. Threading

```python
import threading

def capture_thread():
    sniff(iface="Wi-Fi", prn=callback, store=False)

t = threading.Thread(target=capture_thread, daemon=True)
t.start()
```

---

## Integration with Dashboard

### Complete Workflow

```
Live WiFi Traffic
    ↓
[Scapy Capture]
    ↓
[Feature Extraction]
    ↓
[Model Prediction + Explanation]
    ↓
[HTTP POST to Dashboard]
    ↓
[Dashboard Shows Live Alerts]
    ↓
Security Analyst sees:
"SYN Flood detected on 192.168.1.100
 - packet_rate contributed 45%"
```

---

## Demo Script

```bash
# Complete demo setup

# Terminal 1: Dashboard
cd projects/dashboard
python app.py

# Terminal 2: Live WiFi Monitor (as Admin)
python scripts/live_wifi_detector.py

# Terminal 3: Open Browser
start http://localhost:5000

# Now:
# 1. Browse websites (generate traffic)
# 2. Watch live detections appear
# 3. See explanations in real-time
```

---

**You now have LIVE WiFi traffic analysis with Explainable AI!** 🎯
