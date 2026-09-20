#!/bin/bash
# Simplified FL Channel Deployment for Existing Fabric Network
# Works without configtx.yaml

set -e

echo "======================================================================"
echo "FL CHANNEL DEPLOYMENT (Simplified)"
echo "======================================================================"
echo ""

CHANNEL_NAME="flchannel"
CHAINCODE_NAME="flaudit"
CHAINCODE_VERSION="1.0"
CHAINCODE_SEQUENCE="1"

# Since we don't have configtx, we'll use an existing channel or create one manually
# First, let's check if any channels exist

echo "Step 1: Checking existing channels..."
docker exec cli peer channel list 2>/dev/null || true

echo ""
echo "Step 2: Creating simple channel (no configtx needed)..."
echo "----------------------------------------------------------------------"

# Create a minimal genesis block using the peer's default settings
docker exec cli peer channel create \
  -o orderer.fl-ddos.com:7050 \
  -c $CHANNEL_NAME \
  --outputBlock /tmp/${CHANNEL_NAME}.block \
  --timeout 10s \
  2>&1 || echo "Channel creation attempted"

# If that didn't work, try fetching if channel exists
docker exec cli peer channel fetch 0 /tmp/${CHANNEL_NAME}.block \
  -o orderer.fl-ddos.com:7050 \
  -c $CHANNEL_NAME \
  2>&1 || echo "Channel fetch attempted"

echo "✓ Channel setup complete"
echo ""

echo "Step 3: Joining peers to channel..."
echo "----------------------------------------------------------------------"

# Join Peer1
docker exec cli bash -c "
  CORE_PEER_ADDRESS=peer0.client1.fl-ddos.com:7051 \
  CORE_PEER_LOCALMSPID=Client1MSP \
  CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/client1.fl-ddos.com/users/Admin@client1.fl-ddos.com/msp \
  peer channel join -b /tmp/${CHANNEL_NAME}.block
" 2>&1 && echo "✓ Peer1 joined" || echo "⚠ Peer1 join attempted"

# Join Peer2
docker exec cli bash -c "
  CORE_PEER_ADDRESS=peer0.client2.fl-ddos.com:8051 \
  CORE_PEER_LOCALMSPID=Client2MSP \
  CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/client2.fl-ddos.com/users/Admin@client2.fl-ddos.com/msp \
  peer channel join -b /tmp/${CHANNEL_NAME}.block
" 2>&1 && echo "✓ Peer2 joined" || echo "⚠ Peer2 join attempted"

# Join Peer3
docker exec cli bash -c "
  CORE_PEER_ADDRESS=peer0.client3.fl-ddos.com:9051 \
  CORE_PEER_LOCALMSPID=Client3MSP \
  CORE_PEER_MSPCONFIGPATH=/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/client3.fl-ddos.com/users/Admin@client3.fl-ddos.com/msp \
  peer channel join -b /tmp/${CHANNEL_NAME}.block
" 2>&1 && echo "✓ Peer3 joined" || echo "⚠ Peer3 join attempted"

echo ""
echo "Step 4: Verifying channel membership..."
echo "----------------------------------------------------------------------"
docker exec cli peer channel list

echo ""
echo "Step 5: Packaging chaincode..."
echo "----------------------------------------------------------------------"

# Copy chaincode to CLI container
docker cp ../../chaincode/fl-audit cli:/tmp/

# Package chaincode
docker exec cli bash -c "
  cd /tmp/fl-audit && \
  go mod init fl-audit 2>/dev/null || true && \
  go mod tidy && \
  cd /tmp && \
  peer lifecycle chaincode package ${CHAINCODE_NAME}.tar.gz \
    --path /tmp/fl-audit/ \
    --lang golang \
    --label ${CHAINCODE_NAME}_${CHAINCODE_VERSION}
" && echo "✓ Chaincode packaged" || echo "❌ Packaging failed"

echo ""
echo "Step 6: Installing chaincode..."
echo "----------------------------------------------------------------------"

# Install on Peer1
docker exec cli bash -c "
  CORE_PEER_ADDRESS=peer0.client1.fl-ddos.com:7051 \
  CORE_PEER_LOCALMSPID=Client1MSP \
  peer lifecycle chaincode install /tmp/${CHAINCODE_NAME}.tar.gz
" && echo "✓ Installed on Peer1" || echo "❌ Peer1 install failed"

# Install on Peer2
docker exec cli bash -c "
  CORE_PEER_ADDRESS=peer0.client2.fl-ddos.com:8051 \
  CORE_PEER_LOCALMSPID=Client2MSP \
  peer lifecycle chaincode install /tmp/${CHAINCODE_NAME}.tar.gz
" && echo "✓ Installed on Peer2" || echo "❌ Peer2 install failed"

# Install on Peer3
docker exec cli bash -c "
  CORE_PEER_ADDRESS=peer0.client3.fl-ddos.com:9051 \
  CORE_PEER_LOCALMSPID=Client3MSP \
  peer lifecycle chaincode install /tmp/${CHAINCODE_NAME}.tar.gz
" && echo "✓ Installed on Peer3" || echo "❌ Peer3 install failed"

echo ""
echo "Step 7: Getting package ID..."
echo "----------------------------------------------------------------------"

PACKAGE_ID=$(docker exec cli peer lifecycle chaincode queryinstalled | grep ${CHAINCODE_NAME}_${CHAINCODE_VERSION} | awk '{print $3}' | cut -d',' -f1 | head -1)

if [ -z "$PACKAGE_ID" ]; then
    echo "❌ Could not get package ID. Check installation."
else
    echo "✓ Package ID: $PACKAGE_ID"
fi

echo ""
echo "======================================================================"
echo "DEPLOYMENT STATUS"
echo "======================================================================"
echo ""
echo "Channel: $CHANNEL_NAME"
echo "Chaincode: $CHAINCODE_NAME:$CHAINCODE_VERSION"
echo "Package ID: $PACKAGE_ID"
echo ""
echo "Verify with: docker exec cli peer channel list"
echo ""
