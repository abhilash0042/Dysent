# 🌐 Project Authenticity & Third-Party Integration Demo

**Goal:** Prove your FL-DDoS system is a REAL working product, not just a script.
**Method:** Integrate and showcase industry-standard "Third Party" tools during your demo.

---

## 🛠️ The "Authenticity Stack"

| Component            | Authenticity Tool             | Why It Matters                                          |
| :------------------- | :---------------------------- | :------------------------------------------------------ |
| **Network Traffic**  | **Wireshark**                 | Proves packets are real (not just arrays in RAM).       |
| **Network Topology** | **Mininet (Linux)**           | Proves distributed routing nodes are strictly isolated. |
| **System Status**    | **Web Browser (Chrome/Edge)** | Shows the system has a polished, deployable UI.         |
| **API Interaction**  | **Postman / cURL**            | Proves the model exposes a standard REST API.           |

---

## 🎬 The "Live Proof" Demo Flow

### Step 1: Prove the Network is Real (Mininet + Wireshark)

**Action:** Start the Mininet simulation and capture traffic.

1.  **Open Terminal 1 (Mininet Controller):**

    ```bash
    sudo python ddosdfl/projects/mininet/topology.py
    ```

    _Authenticity Signal:_ You see `*** Creating network`, `*** Adding hosts`, `*** Starting controller`. This is real network virtualization.

2.  **Open Wireshark (Third Party App):**
    - Start Wireshark.
    - Select Interface: `s1-eth1` (The switch port connected to Host 1).
    - **Filter:** `tcp.port == 8080`.
    - _Show:_ Empty screen (waiting for traffic).

3.  **Generate Traffic:**
    - In Mininet CLI: `h1 curl h2:8080`
    - **Look at Wireshark:** You will see **REAL TCP packets** (SYN, ACK, PSH) appearing.
    - _Defense Point:_ "This isn't a simulation script. These are actual TCP/IP packets traversing a virtual kernel switch, captured by Wireshark."

### Step 2: Prove the Interface is Real (Web Browser)

**Action:** Interact with the Dashboard.

1.  Open **Google Chrome** or **Edge**.
2.  Navigate to `http://localhost:5000`.
3.  **Trigger an Attack:**
    - Run the attack script: `python tests/test_30gb_attack_replay.py`
4.  **Watch Browser:**
    - Charts update in real-time.
    - Alerts appear instantly via WebSockets.
    - _Defense Point:_ "The system uses standard WebSockets for real-time alerts, just like a production SIEM tool."

### Step 3: Prove the AI is Accessible (Postman/API)

**Action:** Query the model manually.

1.  Open **Postman** (or use Terminal `curl`).
2.  **Send a Request:**
    - POST `http://localhost:5000/predict`
    - Body: `{"features": [0.1, 55, 1000, ...]}`
3.  **Receive Response:**
    - `{"class": "Benign", "confidence": 0.999}`
    - _Defense Point:_ "The AI is deployed as a microservice. Any third-party firewall can query it via this standard REST API."

---

## 📦 How We Implemented It

### 1. Network Layer (Mininet)

We use the **Linux Kernel Namespace** feature (via Mininet) to create isolated nodes.

- **Authenticity:** Each node (`h1`, `h2`) has its own IP stack and routing table. They cannot cheat; they must communicate over the virtual wire.

### 2. Monitoring Layer (Wireshark)

We integrated `tcpdump` hooks.

- **Authenticity:** The traffic follows standard PCAP formats. You can export the attack log and open it in any industry tool (Wireshark, Snort, Zeek).

### 3. Application Layer (Flask + React)

We built a standard REST + WebSocket architecture.

- **Authenticity:** It's not a Jupyter notebook. It's a server (Flask) pushing data to a client (Browser), simulating a real Security Operations Center (SOC).

---

## 🗣️ Defense Script

**Examiner:** "Is this just a simulation?"

**You:**

> "No, it's a high-fidelity emulation.
>
> 1.  **Network:** I'm using **Mininet**, which runs real kernel network stacks.
> 2.  **Verification:** I can show you the packets in **Wireshark** (Third Party Tool) right now.
> 3.  **Operations:** We monitor it via a **Web Dashboard**, just like a commercial Anycast or Cloudflare interface.
>
> The system generates, transmits, analyzes, and visualizes real data packets in real-time."
