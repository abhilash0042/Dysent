#!/bin/bash

# Hyperledger Fabric Network Setup Script for FL-DDoS
# This script initializes the blockchain network infrastructure

set -e

FABRIC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
echo "🔗 Initializing Hyperledger Fabric Network for FL-DDoS..."

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Step 1: Check prerequisites
echo -e "${YELLOW}📋 Checking prerequisites...${NC}"
command -v docker >/dev/null 2>&1 || { echo -e "${RED}❌ Docker is not installed${NC}"; exit 1; }
command -v docker-compose >/dev/null 2>&1 || { echo -e "${RED}❌ Docker Compose is not installed${NC}"; exit 1; }
echo -e "${GREEN}✓ Docker and Docker Compose found${NC}"

# Step 2: Download Fabric binaries (if not present)
if [ ! -d "$FABRIC_DIR/bin" ]; then
    echo -e "${YELLOW}📦 Downloading Hyperledger Fabric binaries...${NC}"
    curl -sSL https://bit.ly/2ysbOFE | bash -s -- 2.5.0 1.5.7
    echo -e "${GREEN}✓ Fabric binaries downloaded${NC}"
else
    echo -e "${GREEN}✓ Fabric binaries already present${NC}"
fi

# Add binaries to PATH for this session
if [ -d "$FABRIC_DIR/fabric-samples/bin" ]; then
    export PATH=$FABRIC_DIR/fabric-samples/bin:$PATH
    echo -e "${GREEN}✓ using binaries from fabric-samples/bin${NC}"
elif [ -d "$FABRIC_DIR/bin" ]; then
    export PATH=$FABRIC_DIR/bin:$PATH
    echo -e "${GREEN}✓ using binaries from bin${NC}"
else
    echo -e "${RED}❌ Could not find Fabric binaries in bin/ or fabric-samples/bin/${NC}"
    echo "Current directory content:"
    ls -F
    exit 1
fi

# Step 3: Generate crypto material
echo -e "${YELLOW}🔐 Generating cryptographic material...${NC}"
if [ -d "$FABRIC_DIR/crypto-config" ]; then
    echo "  Removing old crypto material..."
    rm -rf "$FABRIC_DIR/crypto-config"
fi

cryptogen generate --config=crypto-config.yaml --output="crypto-config"
echo -e "${GREEN}✓ Crypto material generated${NC}"

# Step 4: Create genesis block
echo -e "${YELLOW}📦 Creating genesis block...${NC}"
if [ ! -d "$FABRIC_DIR/channel-artifacts" ]; then
    mkdir -p "$FABRIC_DIR/channel-artifacts"
fi

# Create configtx.yaml file
cat > configtx.yaml <<EOF
Organizations:
  - &OrdererOrg
      Name: OrdererOrg
      ID: OrdererMSP
      MSPDir: crypto-config/ordererOrganizations/fl-ddos.com/msp
      Policies:
        Readers:
          Type: Signature
          Rule: "OR('OrdererMSP.member')"
        Writers:
          Type: Signature
          Rule: "OR('OrdererMSP.member')"
        Admins:
          Type: Signature
          Rule: "OR('OrdererMSP.admin')"

  - &Client1
      Name: Client1MSP
      ID: Client1MSP
      MSPDir: crypto-config/peerOrganizations/client1.fl-ddos.com/msp
      Policies:
        Readers:
          Type: Signature
          Rule: "OR('Client1MSP.admin', 'Client1MSP.peer', 'Client1MSP.client')"
        Writers:
          Type: Signature
          Rule: "OR('Client1MSP.admin', 'Client1MSP.client')"
        Admins:
          Type: Signature
          Rule: "OR('Client1MSP.admin')"
      AnchorPeers:
        - Host: peer0.client1.fl-ddos.com
          Port: 7051

  - &Client2
      Name: Client2MSP
      ID: Client2MSP
      MSPDir: crypto-config/peerOrganizations/client2.fl-ddos.com/msp
      Policies:
        Readers:
          Type: Signature
          Rule: "OR('Client2MSP.admin', 'Client2MSP.peer', 'Client2MSP.client')"
        Writers:
          Type: Signature
          Rule: "OR('Client2MSP.admin', 'Client2MSP.client')"
        Admins:
          Type: Signature
          Rule: "OR('Client2MSP.admin')"
      AnchorPeers:
        - Host: peer0.client2.fl-ddos.com
          Port: 8051

  - &Client3
      Name: Client3MSP
      ID: Client3MSP
      MSPDir: crypto-config/peerOrganizations/client3.fl-ddos.com/msp
      Policies:
        Readers:
          Type: Signature
          Rule: "OR('Client3MSP.admin', 'Client3MSP.peer', 'Client3MSP.client')"
        Writers:
          Type: Signature
          Rule: "OR('Client3MSP.admin', 'Client3MSP.client')"
        Admins:
          Type: Signature
          Rule: "OR('Client3MSP.admin')"
      AnchorPeers:
        - Host: peer0.client3.fl-ddos.com
          Port: 9051

Capabilities:
  Channel: &ChannelCapabilities
    V2_0: true
  Orderer: &OrdererCapabilities
    V2_0: true
  Application: &ApplicationCapabilities
    V2_0: true

Application: &ApplicationDefaults
  Organizations:
  Policies:
    Readers:
      Type: ImplicitMeta
      Rule: "ANY Readers"
    Writers:
      Type: ImplicitMeta
      Rule: "ANY Writers"
    Admins:
      Type: ImplicitMeta
      Rule: "MAJORITY Admins"
  Capabilities:
    <<: *ApplicationCapabilities

Orderer: &OrdererDefaults
  OrdererType: solo
  Addresses:
    - orderer.fl-ddos.com:7050
  BatchTimeout: 2s
  BatchSize:
    MaxMessageCount: 10
    AbsoluteMaxBytes: 99 MB
    PreferredMaxBytes: 512 KB
  Organizations:
  Policies:
    Readers:
      Type: ImplicitMeta
      Rule: "ANY Readers"
    Writers:
      Type: ImplicitMeta
      Rule: "ANY Writers"
    Admins:
      Type: ImplicitMeta
      Rule: "MAJORITY Admins"
    BlockValidation:
      Type: ImplicitMeta
      Rule: "ANY Writers"
  Capabilities:
    <<: *OrdererCapabilities

Channel: &ChannelDefaults
  Policies:
    Readers:
      Type: ImplicitMeta
      Rule: "ANY Readers"
    Writers:
      Type: ImplicitMeta
      Rule: "ANY Writers"
    Admins:
      Type: ImplicitMeta
      Rule: "MAJORITY Admins"
  Capabilities:
    <<: *ChannelCapabilities

Profiles:
  FLOrdererGenesis:
    <<: *ChannelDefaults
    Orderer:
      <<: *OrdererDefaults
      Organizations:
        - *OrdererOrg
    Consortiums:
      FLConsortium:
        Organizations:
          - *Client1
          - *Client2
          - *Client3

  FLChannel:
    Consortium: FLConsortium
    <<: *ChannelDefaults
    Application:
      <<: *ApplicationDefaults
      Organizations:
        - *Client1
        - *Client2
        - *Client3
EOF

configtxgen -profile FLOrdererGenesis -channelID system-channel -outputBlock ./channel-artifacts/genesis.block
echo -e "${GREEN}✓ Genesis block created${NC}"

# Step 5: Create channel configuration
echo -e "${YELLOW}📝 Creating channel configuration...${NC}"
export CHANNEL_NAME=fl-audit-channel
configtxgen -profile FLChannel -outputCreateChannelTx ./channel-artifacts/channel.tx -channelID $CHANNEL_NAME
echo -e "${GREEN}✓ Channel configuration created${NC}"
# Step 6: Skip anchor peer updates (using dynamic discovery)
echo -e "${GREEN}✓ Anchor peer configuration skipped${NC}"
echo "  1. Start the network: docker-compose up -d"
echo "  2. Create channel: ./scripts/create-channel.sh"
echo "  3. Deploy chaincode: ./scripts/deploy-chaincode.sh"
echo ""
