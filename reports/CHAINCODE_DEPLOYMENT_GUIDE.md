# 🚀 Deploy Smart Contracts to Your Blockchain - Quick Guide

**Time Required:** 30 minutes  
**Result:** Production-grade blockchain with smart contracts

---

## Step 1: Create the Smart Contract (Chaincode)

**In Ubuntu Terminal:**

```bash
cd "/mnt/c/Users/HP/Desktop/Major Project/Main File-Code/ddosdfl/fabric"
```

**Create chaincode directory:**

```bash
mkdir -p chaincode/fl-audit
cd chaincode/fl-audit
```

**Create the Go smart contract (`fl-audit.go`):**

```bash
cat > fl-audit.go << 'EOF'
package main

import (
    "encoding/json"
    "fmt"
    "github.com/hyperledger/fabric-contract-api-go/contractapi"
)

type SmartContract struct {
    contractapi.Contract
}

type ModelUpdate struct {
    NodeID      string `json:"node_id"`
    Round       int    `json:"round"`
    ModelHash   string `json:"model_hash"`
    Timestamp   string `json:"timestamp"`
}

type Aggregation struct {
    Round       int      `json:"round"`
    GlobalHash  string   `json:"global_hash"`
    Nodes       []string `json:"nodes"`
    Timestamp   string   `json:"timestamp"`
}

// LogModelUpdate records FL model update
func (s *SmartContract) LogModelUpdate(ctx contractapi.TransactionContextInterface,
    nodeID string, round int, modelHash string, timestamp string) error {

    update := ModelUpdate{
        NodeID:    nodeID,
        Round:     round,
        ModelHash: modelHash,
        Timestamp: timestamp,
    }

    updateJSON, err := json.Marshal(update)
    if err != nil {
        return err
    }

    key := fmt.Sprintf("UPDATE_%s_%d", nodeID, round)
    return ctx.GetStub().PutState(key, updateJSON)
}

// LogAggregation records global aggregation
func (s *SmartContract) LogAggregation(ctx contractapi.TransactionContextInterface,
    round int, globalHash string, nodes []string, timestamp string) error {

    agg := Aggregation{
        Round:      round,
        GlobalHash: globalHash,
        Nodes:      nodes,
        Timestamp:  timestamp,
    }

    aggJSON, err := json.Marshal(agg)
    if err != nil {
        return err
    }

    key := fmt.Sprintf("AGG_%d", round)
    return ctx.GetStub().PutState(key, aggJSON)
}

// QueryModelUpdate retrieves model update
func (s *SmartContract) QueryModelUpdate(ctx contractapi.TransactionContextInterface,
    nodeID string, round int) (*ModelUpdate, error) {

    key := fmt.Sprintf("UPDATE_%s_%d", nodeID, round)
    updateJSON, err := ctx.GetStub().GetState(key)
    if err != nil {
        return nil, err
    }

    var update ModelUpdate
    err = json.Unmarshal(updateJSON, &update)
    return &update, err
}

func main() {
    chaincode, err := contractapi.NewChaincode(&SmartContract{})
    if err != nil {
        fmt.Printf("Error creating chaincode: %s", err)
        return
    }

    if err := chaincode.Start(); err != nil {
        fmt.Printf("Error starting chaincode: %s", err)
    }
}
EOF
```

**Create Go module:**

```bash
cat > go.mod << 'EOF'
module fl-audit

go 1.20

require github.com/hyperledger/fabric-contract-api-go v1.2.1
EOF
```

---

## Step 2: Package the Chaincode

```bash
cd ../..  # Back to fabric directory

# Install dependencies
cd chaincode/fl-audit
go mod tidy
cd ../..

# Package chaincode
docker exec cli peer lifecycle chaincode package fl-audit.tar.gz \
    --path /opt/gopath/src/github.com/chaincode/fl-audit \
    --lang golang \
    --label fl-audit_1
```

---

## Step 3: Install on All Peers

```bash
# Install on peer0.client1
docker exec cli peer lifecycle chaincode install fl-audit.tar.gz \
    --peerAddresses peer0.client1.fl-ddos.com:7051

# Install on peer0.client2
docker exec -e CORE_PEER_ADDRESS=peer0.client2.fl-ddos.com:8051 \
    cli peer lifecycle chaincode install fl-audit.tar.gz

# Install on peer0.client3
docker exec -e CORE_PEER_ADDRESS=peer0.client3.fl-ddos.com:9051 \
    cli peer lifecycle chaincode install fl-audit.tar.gz
```

**Get Package ID:**

```bash
docker exec cli peer lifecycle chaincode queryinstalled
```

_Copy the Package ID (e.g., `fl-audit_1:abc123...`)_

---

## Step 4: Approve and Commit

**Set Package ID (replace with yours):**

```bash
export PACKAGE_ID="fl-audit_1:YOUR_PACKAGE_ID_HERE"

# Approve for Org1
docker exec cli peer lifecycle chaincode approveformyorg -o orderer.fl-ddos.com:7050 \
    --channelID fl-audit-channel \
    --name fl-audit \
    --version 1.0 \
    --package-id $PACKAGE_ID \
    --sequence 1

# Check approval status
docker exec cli peer lifecycle chaincode checkcommitreadiness \
    --channelID fl-audit-channel \
    --name fl-audit \
    --version 1.0 \
    --sequence 1

# Commit chaincode
docker exec cli peer lifecycle chaincode commit -o orderer.fl-ddos.com:7050 \
    --channelID fl-audit-channel \
    --name fl-audit \
    --version 1.0 \
    --sequence 1 \
    --peerAddresses peer0.client1.fl-ddos.com:7051
```

---

## Step 5: Test the Smart Contract

**Invoke chaincode:**

```bash
docker exec cli peer chaincode invoke -o orderer.fl-ddos.com:7050 \
    -C fl-audit-channel \
    -n fl-audit \
    --peerAddresses peer0.client1.fl-ddos.com:7051 \
    -c '{"function":"LogModelUpdate","Args":["node_1","5","abc123hash","2026-01-26T12:00:00Z"]}'
```

**Query chaincode:**

```bash
docker exec cli peer chaincode query \
    -C fl-audit-channel \
    -n fl-audit \
    -c '{"function":"QueryModelUpdate","Args":["node_1","5"]}'
```

**Expected Output:**

```json
{
  "node_id": "node_1",
  "round": 5,
  "model_hash": "abc123hash",
  "timestamp": "2026-01-26T12:00:00Z"
}
```

---

## Troubleshooting

**If channel doesn't exist:**

```bash
# Create channel first
docker exec cli peer channel create -o orderer.fl-ddos.com:7050 \
    -c fl-audit-channel \
    -f /opt/gopath/src/github.com/channel-artifacts/channel.tx

# Join peers
docker exec cli peer channel join -b fl-audit-channel.block
```

**If package ID not found:**

```bash
# Query installed chaincodes
docker exec cli peer lifecycle chaincode queryinstalled

# Use the full Package ID from output
```

---

## ✅ Success Criteria

You've successfully deployed when you see:

1. ✅ **Chaincode installed** on all 3 peers
2. ✅ **Chaincode committed** to channel
3. ✅ **Invoke succeeds** without errors
4. ✅ **Query returns** the stored data

---

## Next: Update Python to Use Smart Contracts

Once deployed, update `simple_fabric_client.py` to invoke chaincode instead of local logging.

**You now have production-grade blockchain with smart contracts!** 🎉
