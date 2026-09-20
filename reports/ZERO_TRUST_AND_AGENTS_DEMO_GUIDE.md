# 🕵️ Zero Trust & Agent Interaction Demo Guide

**Goal:** Prove that your system implements **Zero Trust Security** (Encryption) and **Autonomous AI Agents** (Self-Healing).
**Method:** Trigger specific scenarios that force the system to react visibly in the logs and dashboard.

---

## 🔐 Part 1: Zero Trust Architecture (Encryption Demo)

**Concept:** "Never Trust, Always Verify." The server performs aggregation on _encrypted_ data without ever seeing the raw model weights.

### 🎬 How to Show It (The "Unreadable Data" Proof)

1.  **Start the Federated Learning Process:**

    ```bash
    # Run the secure FL script
    python experiments/extended/run_dp_fl.py
    ```

2.  **Highlight the Logs:**
    Watch the terminal output for the `[ZeroTrust]` tag. You will see lines like:

    ```
    [ZeroTrust] Client 1: Encrypting model updates...
    [ZeroTrust] Encrypted Payload Size: 1568 bytes
    [ZeroTrust] Server: Received Encrypted Gradients. Aggregating...
    [ZeroTrust] Server: Cannot decrypt payload (Missing Secret Key).
    ```

3.  **The "Gotcha" Moment:**
    - Open `ddosdfl/logs/fl_server.log` (or check terminal).
    - Show that the "weights" received by the server are just **random alphanumeric strings** ( ciphertext), not float arrays.
    - _Defense Point:_ "The server processes the math blindly. If a hacker compromises the server, they only see gibberish, not the intrusion patterns."

---

## 🤖 Part 2: Multi-Agent Interaction (Self-Healing Demo)

**Concept:** 4 AI Agents (Guardian, Strategist, Analyst, Coordinator) constantly monitor the system and "vote" on decisions.

### 🎬 How to Show It (The "Bad Actor" Scenario)

We will intentionally simulate a **Byzantine Attack** (a malicious node trying to poison the model) and watch the agents catch it.

1.  **Run the Multi-Agent Simulation:**

    ```bash
    # This script simulates a FL round with one malicious agent
    python tests/test_maml_deep_diagnosis.py
    ```

    _(Note: This test runs the MAML + Agent loop)_

2.  **Watch the "Agent Chat" Logs:**
    The system will output a conversation between the AI agents. Look for this sequence:
    - **Guardian Agent:**
      > "⚠️ ALERT: Node_3 accuracy dropped to 45% (others are 98%). Gradient variance is high. Suspicious activity detected."
    - **Analyst Agent:**
      > "📉 Analysis: Node_3's contribution is degrading the Global Model loss by 15%. This matches a 'Model Poisoning' signature."
    - **Strategist Agent:**
      > "🛡️ Recommendation: Slash Node_3's trust score to 0. Exclude from this round. Increase local epochs for Node_1 and Node_2 to compensate."
    - **Coordinator Agent:**
      > "✅ DECISION EXECUTED: Node_3 Rejected. Reputation updated. Proceeding with aggregation."

3.  **Defense Point:**
    "The system isn't just a static loop. It has autonomous agents that detected my simulated attack, discussed it, and banished the attacker without human intervention."

---

## 🖥️ Visualizing it on the Dashboard

If running the full `app.py` Dashboard:

1.  Go to the **"System Health"** or **"Agents"** tab.
2.  Look for the **"Trust Score"** table.
3.  You will see:
    - Node 1: 🟢 98% (Trusted)
    - Node 2: 🟢 99% (Trusted)
    - Node 3: 🔴 **0% (Banned)** regarding "Poisoning Attempt".

This visual confirmation proves the "Zero Trust" policy is active: a node lost trust instantly upon bad behavior.
