"""
Run Mininet Authenticity Simulation
Executes the actual FL-DDoS python code within a virtual network.
"""

import sys
import time
from mininet.net import Mininet
from mininet.node import Controller, OVSController, RemoteController
from mininet.cli import CLI
from mininet.log import setLogLevel, info
from pathlib import Path

# Import our topology
sys.path.append(str(Path(__file__).parent))
from topology import FLTopology

def run_experiment():
    # 1. Create Network
    info('*** Creating Network\n')
    topo = FLTopology(n=3) # 1 Server, 3 Clients
    
    # Use controller=None to avoid dependency on 'controller' or 'ovs-testcontroller' binaries
    # We will rely on OVS standalone mode (L2 switching)
    net = Mininet(topo=topo, controller=None)
    
    info('*** Starting Network\n')
    net.start()
    
    # Force switches to standalone mode (act as normal L2 switches)
    info('*** Setting switches to standalone mode\n')
    for sw in net.switches:
        # This tells OVS to forward packets like a normal switch if no controller is present
        sw.cmd(f'ovs-vsctl set-fail-mode {sw.name} standalone')
    
    # 2. Setup Hosts
    server = net.get('h_server')
    h1 = net.get('h1')
    h2 = net.get('h2')
    h3 = net.get('h3')
    
    # Get project root to run scripts
    project_root = Path(__file__).parent.parent.parent.parent
    server_script = project_root / 'ddosdfl' / 'experiments' / 'mininet' / 'mininet_server.py'
    client_script = project_root / 'ddosdfl' / 'experiments' / 'mininet' / 'mininet_client.py'
    
    info('*** Verifying python availability\n')
    
    # Priority 1: Home directory venv (native Linux filesystem, avoids I/O errors)
    import os
    home_venv_python = Path(os.path.expanduser('~')) / 'mininet_venv' / 'bin' / 'python'
    
    # Priority 2: Dedicated Mininet Venv (Linux/WSL) - created in project root
    mininet_venv_python = project_root / 'mininet_venv' / 'bin' / 'python'
    
    # Priority 3: Standard venv (if Linux compatible)
    venv_python = project_root / 'venv' / 'bin' / 'python'
    if not venv_python.exists():
         venv_python = project_root / '.venv' / 'bin' / 'python'
    
    if home_venv_python.exists():
        python_cmd = str(home_venv_python)
        info(f"*** Using Home Directory Venv: {python_cmd}\n")
    elif mininet_venv_python.exists():
        python_cmd = str(mininet_venv_python)
        info(f"*** Using Dedicated Mininet Venv: {python_cmd}\n")
    elif venv_python.exists():
        python_cmd = str(venv_python)
        info(f"*** Using Standard venv: {python_cmd}\n")
    else:
        # Fallback to system python (might fail if deps are missing)
        python_cmd = sys.executable
        info(f"*** Warning: Using system python: {python_cmd}\n")
        info("*** If this fails, run 'bash ddosdfl/setup_wsl_env.sh' to fix dependencies.\n")

    
    # 3. Start Server
    info('*** Starting FL Server on h_server (10.0.0.254)...\n')
    # Run in background (&)
    # Quote paths to handle spaces in directory names (e.g. "Major Project")
    server.cmd(f'"{python_cmd}" "{server_script}" > server.log 2>&1 &')
    time.sleep(2) # Wait for server to bind
    
    # 4. Start Clients
    info('*** Starting FL Clients...\n')
    h1.cmd(f'"{python_cmd}" "{client_script}" h1 10.0.0.254 > h1.log 2>&1 &')
    h2.cmd(f'"{python_cmd}" "{client_script}" h2 10.0.0.254 > h2.log 2>&1 &')
    h3.cmd(f'"{python_cmd}" "{client_script}" h3 10.0.0.254 > h3.log 2>&1 &')
    
    info('*** Authentic Network Traffic Generation in Progress...\n')
    info('*** Open Wireshark on s1-eth1 to see FL Update Packets!\n')
    info('*** Press Ctrl+D/exit to stop simulation\n')
    
    # 5. Open CLI for manual inspection
    CLI(net)
    
    # 6. Stop
    info('*** Stopping Network\n')
    net.stop()

if __name__ == '__main__':
    setLogLevel('info')
    # Check for root (Mininet requirement)
    import os
    if os.geteuid() != 0:
        print("Error: Mininet must be run as root (sudo)")
        sys.exit(1)
        
    run_experiment()
