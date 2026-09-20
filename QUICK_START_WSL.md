# Quick Start: FL with Blockchain in WSL

## 3-Step Execution

```bash
# 1. Start WSL & Navigate
wsl
cd /mnt/c/Users/HP/Desktop/Major\ Project/Main\ File-Code/ddosdfl

# 2. Activate Environment
source .venv/bin/activate

# 3. Run FL
python experiments/federated_learning/run_realtime_fl.py
```

## Pre-Flight Check

```bash
# Verify blockchain running
docker ps | grep fabric
# Should show 5 containers

# Check .env configuration
cat .env | grep BLOCKCHAIN
# Should show ENABLE_BLOCKCHAIN=true
```

## Monitor Progress

**Terminal 1 (WSL)**: FL Training

```bash
python experiments/federated_learning/run_realtime_fl.py
```

**Terminal 2 (PowerShell)**: Blockchain

```powershell
docker logs -f peer0.client1.fl-ddos.com
```

## Expected Duration

- **Training**: ~45 minutes
- **Accuracy**: ~92.77%
- **Transactions**: 50 blockchain logs

## After Completion

```bash
# Verify results
ls -lh fl_checkpoints/

# Check blockchain
python scripts/verify_blockchain.py
```

---

**See full guide in WSL_FL_BLOCKCHAIN_EXECUTION.md**
