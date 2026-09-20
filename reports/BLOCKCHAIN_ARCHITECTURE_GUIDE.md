# 🔗 Blockchain Architecture for FL Audit Logging

**User Question:** "What kind of Blockchain system are we using?"
**Short Answer:** A **Permissioned (Private) Consortium Blockchain**.

---

## 1. Why Not Bitcoin or Ethereum?

Public blockchains (Bitcoin/Ethereum) are **unsuitable** for cybersecurity audit logs because:

1.  **Privacy:** We cannot publish sensitive model updates or node IPs to a public ledger.
2.  **Speed:** 10-minute block times (BTC) are too slow for real-time FL rounds.
3.  **Cost:** Gas fees for thousands of audit logs would be prohibitive.

## 2. Our Solution: A Private Permissioned Ledger

We implemented a lightweight, Python-based simulation of **Hyperledger Fabric**.

### Key Characteristics:

- **Permissioned:** Only authorized FL Nodes (checked by `TrustManager`) can write to the chain.
- **Latency:** Instant block confirmation (Proof of Authority).
- **Privacy:** The ledger is shared only among the Aggregation Server and Trusted Clients.

---

## 3. The "Audit Block" Structure

Every critical event in the FL process creates a permanent, immutable record.

```json
{
  "index": 142,
  "timestamp": "2026-01-24T22:50:00Z",
  "event_type": "FL_MODEL_UPDATE",
  "node_id": "Client_03",
  "data_hash": "sha256:a7f9...", // Hash of the encrypted weights (NOT the weights themselves)
  "prev_hash": "sha256:b8c1..."
}
```

### What We Log:

1.  **Node Registration:** When a new client joins (Identity Management).
2.  **Model Updates:** The _hash_ of the update sent by a client (Proof of Submission).
3.  **Aggregation Events:** When the server updates the Global Model (Version Control).
4.  **Security Alerts:** When a node is banned by the Guardian Agent (Incident Response).

---

## 4. How to Explain It (Presentation Script)

**Examiner:** "Why do you need a Blockchain?"

**You:**

> "In a Federated Learning system, malicious nodes might deny sending bad updates, or a compromised server might alter the global model silently.
>
> We use a **Permissioned Blockchain** as an immutable **Audit Trail**.
>
> 1.  Every time a node sends an update, we record its **Cryptographic Hash** on the chain.
> 2.  This prevents 'repudiation'—a node cannot deny its actions later.
> 3.  If the model is poisoned, we can traverse the blockchain to find exactly which node introduced the malicious update, rolling back the system to the last known good state."

---

## 5. Technical Implementation

- **File:** `ddosdfl/projects/shared_libs/blockchain_interface.py`
- **Consensus:** Proof of Authority (PoA) - efficient and fast.
- **Storage:** Local append-only ledger (simulating a distributed ledger).
