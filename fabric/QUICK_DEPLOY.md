# Quick Start: FL Channel Deployment

## Choose Your Method

### Method 1: WSL (15 min) ⭐ RECOMMENDED

```bash
# 1. Open WSL
wsl

# 2. Navigate
cd /mnt/c/Users/HP/Desktop/Major\ Project/Main\ File-Code/ddosdfl/fabric/scripts

# 3. Check Go
go version
# If not installed: wget https://go.dev/dl/go1.21.6.linux-amd64.tar.gz && sudo tar -C /usr/local -xzf go1.21.6.linux-amd64.tar.gz

# 4. Run deployment
chmod +x deploy-fl-channel.sh
./deploy-fl-channel.sh

# 5. Verify
docker exec cli peer channel list
```

### Method 2: Windows Go (30 min)

```powershell
# 1. Download & Install Go
# Visit: https://go.dev/dl/
# Download: go1.21.6.windows-amd64.msi
# Run installer

# 2. Verify
go version

# 3. Install dependencies
cd "C:\Users\HP\Desktop\Major Project\Main File-Code\ddosdfl\fabric\chaincode\fl-audit"
go mod tidy

# 4. Deploy
cd ..\..\scripts
powershell -ExecutionPolicy Bypass -File .\deploy-fl-channel.ps1

# 5. Verify
docker exec cli peer channel list
```

## After Deployment

```powershell
# Test chaincode
python scripts/test_chaincode.py

# Run FL with blockchain
python experiments/federated_learning/run_realtime_fl.py

# Query blockchain
python scripts/query_blockchain.py --all
```

**Start with WSL for fastest results!**
