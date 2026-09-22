# Research 70% Implementation Status

This snapshot turns the existing Dysent codebase into the first integrated research milestone: Byzantine-robust FL + SDN mitigation + authenticated PCMI v1.

## Implemented in this milestone

- Reusable Byzantine attack suite: honest, label flip, sign flip, scale/model poisoning, Gaussian noise, random Byzantine, and backdoor-label primitive.
- Aggregation server dispatch for FedAvg, Krum, coordinate median, and trimmed mean.
- Research metrics harness for Precision, Recall, F1, PR-AUC, FPR, MCC and balanced accuracy.
- Reproducible malicious-client sweep scaffold across 0/10/20/30/40% Byzantine clients and multiple seeds.
- Two-domain Mininet topology with independent virtual network domains, FL nodes, legitimate traffic host and protected victim.
- PCMI v1 schema with canonical serialization, SHA-256 model-update commitment, public clipping check and Ed25519 signature verification.
- Ryu/OpenFlow 1.3 PCMI application skeleton and REST intent gate.
- OVS DROP and actual meter-based rate-limit installation when the local OVS build supports meters.
- Fast tests for attacks, aggregators and PCMI signature verification.

## Intentionally deferred

- P2P gossip FL replacing the central server.
- A real zero-knowledge proof implementation.
- Full closed-loop coupling of the trained detector's output to PCMI/Ryu in a single command.
- Large multi-seed GPU experiments and final publication figures.

These are the next 30% rather than blockers for the first integrated milestone.

## Quick checks

```bash
python -m pytest -q tests/test_research_core.py
python experiments/federated_learning/run_byzantine_sweep.py --seeds 3 --output results/byzantine_sweep.json
```

For Mininet/Ryu, run the topology and controller inside the isolated Linux/WSL lab environment, not on the college production network.
