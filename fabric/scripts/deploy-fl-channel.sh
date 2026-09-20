#!/bin/bash
# Deploy FL Channel and Chaincode to Hyperledger Fabric
# This script creates the FL channel and deploys the audit chaincode

set -e

echo "======================================================================"
echo "DEPLOYING FL CHANNEL AND CHAINCODE"
echo "======================================================================"
echo ""

CHANNEL_NAME="flchannel"
CHAINCODE_NAME="fl-audit"
CHAINCODE_VERSION="1.0"
CHAINCODE_SEQUENCE="1"

# Set environment for peer CLI
export CORE_PEER_TLS_ENABLED=false
export CORE_PEER_LOCALMSPID="Client1MSP"
export CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/crypto-config/peerOrganizations/client1.fl-ddos.com/users/Admin@client1.fl-ddos.com/msp
export CORE_PEER_ADDRESS=peer0.client1.fl-ddos.com:7051

echo "Step 1: Creating FL Channel..."
echo "----------------------------------------------------------------------"

# Create channel using CLI container
docker exec cli peer channel create \
  -o orderer.fl-ddos.com:7050 \
  -c $CHANNEL_NAME \
  -f /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.tx \
  --outputBlock /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block \
  2>&1 || echo "Channel may already exist"

echo "✓ Channel creation complete"
echo ""

echo "Step 2: Joining Peers to Channel..."
echo "----------------------------------------------------------------------"

# Join peer0.client1 to channel
docker exec -e CORE_PEER_ADDRESS=peer0.client1.fl-ddos.com:7051 \
  -e CORE_PEER_LOCALMSPID=Client1MSP \
  cli peer channel join \
  -b /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block

echo "✓ Peer1 joined channel"

# Join peer0.client2 to channel
docker exec -e CORE_PEER_ADDRESS=peer0.client2.fl-ddos.com:8051 \
  -e CORE_PEER_LOCALMSPID=Client2MSP \
  cli peer channel join \
  -b /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block

echo "✓ Peer2 joined channel"

# Join peer0.client3 to channel  
docker exec -e CORE_PEER_ADDRESS=peer0.client3.fl-ddos.com:9051 \
  -e CORE_PEER_LOCALMSPID=Client3MSP \
  cli peer channel join \
  -b /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block

echo "✓ Peer3 joined channel"
echo ""

echo "Step 3: Packaging Chaincode..."
echo "----------------------------------------------------------------------"

# Package the chaincode
docker exec cli peer lifecycle chaincode package ${CHAINCODE_NAME}.tar.gz \
  --path /opt/gopath/src/github.com/chaincode/${CHAINCODE_NAME}/ \
  --lang golang \
  --label ${CHAINCODE_NAME}_${CHAINCODE_VERSION}

echo "✓ Chaincode packaged"
echo ""

echo "Step 4: Installing Chaincode on Peers..."
echo "----------------------------------------------------------------------"

# Install on peer0.client1
docker exec -e CORE_PEER_ADDRESS=peer0.client1.fl-ddos.com:7051 \
  -e CORE_PEER_LOCALMSPID=Client1MSP \
  cli peer lifecycle chaincode install ${CHAINCODE_NAME}.tar.gz

echo "✓ Installed on Peer1"

# Install on peer0.client2
docker exec -e CORE_PEER_ADDRESS=peer0.client2.fl-ddos.com:8051 \
  -e CORE_PEER_LOCALMSPID=Client2MSP \
  cli peer lifecycle chaincode install ${CHAINCODE_NAME}.tar.gz

echo "✓ Installed on Peer2"

# Install on peer0.client3
docker exec -e CORE_PEER_ADDRESS=peer0.client3.fl-ddos.com:9051 \
  -e CORE_PEER_LOCALMSPID=Client3MSP \
  cli peer lifecycle chaincode install ${CHAINCODE_NAME}.tar.gz

echo "✓ Installed on Peer3"
echo ""

echo "Step 5: Querying Installed Chaincode..."
echo "----------------------------------------------------------------------"

# Get package ID
PACKAGE_ID=$(docker exec cli peer lifecycle chaincode queryinstalled | grep ${CHAINCODE_NAME}_${CHAINCODE_VERSION} | awk '{print $3}' | cut -d',' -f1)

if [ -z "$PACKAGE_ID" ]; then
    echo "❌ Failed to get package ID"
    exit 1
fi

echo "Package ID: $PACKAGE_ID"
echo ""

echo "Step 6: Approving Chaincode..."
echo "----------------------------------------------------------------------"

# Approve for Client1
docker exec -e CORE_PEER_ADDRESS=peer0.client1.fl-ddos.com:7051 \
  -e CORE_PEER_LOCALMSPID=Client1MSP \
  cli peer lifecycle chaincode approveformyorg \
  -o orderer.fl-ddos.com:7050 \
  --channelID $CHANNEL_NAME \
  --name $CHAINCODE_NAME \
  --version $CHAINCODE_VERSION \
  --package-id $PACKAGE_ID \
  --sequence $CHAINCODE_SEQUENCE

echo "✓ Approved for Client1"

# Approve for Client2
docker exec -e CORE_PEER_ADDRESS=peer0.client2.fl-ddos.com:8051 \
  -e CORE_PEER_LOCALMSPID=Client2MSP \
  cli peer lifecycle chaincode approveformyorg \
  -o orderer.fl-ddos.com:7050 \
  --channelID $CHANNEL_NAME \
  --name $CHAINCODE_NAME \
  --version $CHAINCODE_VERSION \
  --package-id $PACKAGE_ID \
  --sequence $CHAINCODE_SEQUENCE

echo "✓ Approved for Client2"

# Approve for Client3
docker exec -e CORE_PEER_ADDRESS=peer0.client3.fl-ddos.com:9051 \
  -e CORE_PEER_LOCALMSPID=Client3MSP \
  cli peer lifecycle chaincode approveformyorg \
  -o orderer.fl-ddos.com:7050 \
  --channelID $CHANNEL_NAME \
  --name $CHAINCODE_NAME \
  --version $CHAINCODE_VERSION \
  --package-id $PACKAGE_ID \
  --sequence $CHAINCODE_SEQUENCE

echo "✓ Approved for Client3"
echo ""

echo "Step 7: Committing Chaincode..."
echo "----------------------------------------------------------------------"

# Commit chaincode definition
docker exec cli peer lifecycle chaincode commit \
  -o orderer.fl-ddos.com:7050 \
  --channelID $CHANNEL_NAME \
  --name $CHAINCODE_NAME \
  --version $CHAINCODE_VERSION \
  --sequence $CHAINCODE_SEQUENCE \
  --peerAddresses peer0.client1.fl-ddos.com:7051 \
  --peerAddresses peer0.client2.fl-ddos.com:8051 \
  --peerAddresses peer0.client3.fl-ddos.com:9051

echo "✓ Chaincode committed"
echo ""

echo "Step 8: Verifying Deployment..."
echo "----------------------------------------------------------------------"

# Query committed chaincode
docker exec cli peer lifecycle chaincode querycommitted \
  --channelID $CHANNEL_NAME \
  --name $CHAINCODE_NAME

echo ""
echo "======================================================================"
echo "✅ FL CHANNEL AND CHAINCODE DEPLOYMENT COMPLETE!"
echo "======================================================================"
echo ""
echo "Channel: $CHANNEL_NAME"
echo "Chaincode: $CHAINCODE_NAME:$CHAINCODE_VERSION"
echo "Package ID: $PACKAGE_ID"
echo ""
echo "You can now use the real blockchain for FL audit logging!"
echo ""
