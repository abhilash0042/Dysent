# Mininet Simulation Plan covering "Authenticity"

## Goal

Prove project authenticity by running the FL-DDoS system inside **Mininet**, a standard network emulator. This demonstrates that the code works on a realistic network topology, not just as a standalone Python script.

## 1. Prerequisites (User-Side)

- **Mininet VM** or **WSL2** (since Host is Windows).
- **Python 3** installed in the Mininet environment.

## 2. New Components to Create

**Directory**: `ddosdfl/experiments/mininet/`

### A. `topology.py` (The Network Map)

- **Central Switch (s1)**: Connects all nodes.
- **Server Host (h_server)**: Runs the Global Aggregator.
- **Client Hosts (h1...hN)**: Represent IoT edges running Local Models.
- **Attacker Host (h_attack)**: Injects real packet traffic (optional, for Wireshark visibility).

### B. `run_simulation.py` (The Orchestrator)

1.  **Setup**: Starts Mininet network.
2.  **Launch Server**: Executes `federated_server.py` on `h_server`.
3.  **Launch Clients**: Executes `federated_client.py` on `h1...hN`.
4.  **Traffic Gen**: Triggers `generate_data.py` on hosts to simulate data flow.
5.  **Monitoring**: Instructions to open XTerm or logs.

## 3. "Authenticity" Validation Steps

1.  **Wireshark**: Capture packets on `s1-eth1` to show model updates being transferred (real TCP/IP traffic).
2.  **CLI**: Show distinct processes on different virtual IPs (e.g., `10.0.0.1` vs `10.0.0.2`).
3.  **Logs**: Separate log files for each "device".

## 4. Execution Flow

```bash
sudo python experiments/mininet/run_simulation.py
```

## Why this proves authenticity

It moves the executable from "Localhost simulation" to "Distributed Network Simulation", proving the networking stack, socket communication, and distributed logic are real and functional.
