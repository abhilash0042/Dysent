# 🔗 Hyperledger Execution Guide

This guide explains how to run the **Hyperledger Fabric** blockchain integration for your FL-DDoS system.

> **✅ Current Status:** Your system is configured for **Simulation Mode**, which works perfectly on Windows without Docker.

---

## 1. Quick Start (Recommended Demo)

The best way to demonstrate the blockchain integration is to run the **Comprehensive Integration Test**. This runs a full Federated Learning scenario with the blockchain active.

### Run the Command:

```bash
python ddosdfl/tests/test_comprehensive_integration.py
```

### What You Will See:

1. **Blockchain Initialization:**
   ```
   INFO:projects.shared_libs.hyperledger_fabric_client:[SIMULATION] Blockchain client initialized
   ```
2. **Transaction Logging:**
   ```
   INFO:projects.shared_libs.hyperledger_fabric_client:[SIMULATION] MODEL_UPDATE logged: 9a86c534...
   ```
3. **Audit Trail Verification:**
   ```
   INFO:  ✓ All updates logged to blockchain
   INFO:  ✓ Audit trail: 6 records
   ```

---

## 2. Understanding the Modes

Your system is smart—it automatically detects which mode to run in:

| Feature         | **Mode A: Simulation (Current)** | **Mode B: Real Fabric**   |
| :-------------- | :------------------------------- | :------------------------ |
| **Requirement** | Python only (Works on Windows)   | Docker + WSL + Linux      |
| **Storage**     | In-Memory (Persistent per run)   | Distributed Ledger (Disk) |
| **Performance** | Ultra-fast (ms)                  | Production latency (sec)  |
| **API**         | `FabricBlockchainClient`         | `FabricBlockchainClient`  |
| **Code Change** | **None** (Auto-detected)         | **None** (Auto-detected)  |

**For your presentation:** You are using **Mode A**, which simulates the exact API and behavior of Hyperledger Fabric.

---

## 3. Detailed Walkthrough of the Code

### The Integration Point

The magic happens in `ddosdfl/projects/shared_libs/hyperledger_fabric_client.py`.

```python
class FabricBlockchainClient:
    def __init__(self):
        # Tries to import real Fabric SDK
        try:
            from hfc.fabric import Client
            self.mode = "REAL"
        except ImportError:
            # Falls back to simulation if missing
            self.mode = "SIMULATION"
```

### Key Functions You Are Using

1. **Log Model Update:**
   Records when a node sends new weights.

   ```python
   tx_id = blockchain.log_model_update(
       node_id="node_1",
       model_weights=weights,
       round_number=5
   )
   ```

2. **Log Aggregation:**
   Records the server's global model update.

   ```python
   tx_id = blockchain.log_aggregation(
       round_number=5,
       global_model_hash="abc123hash...",
       participating_nodes=["node_1", "node_2"]
   )
   ```

3. **Query Audit Trail:**
   Retrieves the immutable history.
   ```python
   history = blockchain.query_records_by_round(5)
   ```

---

## 4. How to Deploy "Real" Fabric (Optional)

If you move to a Linux machine or fix your Docker WSL setup, here is how to switch to "Real Mode":

1. **Install Prerequisites:**
   ```bash
   pip install fabric-sdk-py
   ```
2. **Start the Network:**
   ```bash
   cd ddosdfl/fabric
   ./setup-network.sh
   docker-compose up -d
   ```
3. **Run the Same Code:**
   The specific file `test_comprehensive_integration.py` will _automatically_ switch to sending transactions to the local Docker peers.

---

## 5. Verification Checklist

When you run the test, verify these lines appear in the output to confirm it's working:

- [ ] `[SIMULATION] Blockchain client initialized`
- [ ] `✓ All updates logged to blockchain`
- [ ] `✓ Audit trail: X records`
- [ ] `PASSED: Blockchain + Agents Integration`

🚀 **You are ready to present usage of enterprise-grade blockchain concepts!**
