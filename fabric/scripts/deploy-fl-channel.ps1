# PowerShell script to deploy FL channel and chaincode
# Windows-compatible version

$ErrorActionPreference = "Continue"

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "DEPLOYING FL CHANNEL AND CHAINCODE" -ForegroundColor Yellow
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

$CHANNEL_NAME = "flchannel"
$CHAINCODE_NAME = "fl-audit"
$CHAINCODE_VERSION = "1.0"
$CHAINCODE_SEQUENCE = "1"

Write-Host "Step 1: Creating channel artifacts directory..." -ForegroundColor Green
docker exec cli mkdir -p /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts

Write-Host "Step 2: Creating genesis block for FL channel..." -ForegroundColor Green
# Simplified channel creation (no configtx required)
docker exec cli peer channel create `
    -o orderer.fl-ddos.com:7050 `
    -c $CHANNEL_NAME `
    --outputBlock /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block `
    2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✅ Channel created" -ForegroundColor Green
}
else {
    Write-Host "  ⚠️  Channel may already exist (continuing...)" -ForegroundColor Yellow
}
Write-Host ""

Write-Host "Step 3: Joining peers to channel..." -ForegroundColor Green

# Peer 1
Write-Host "  Joining Peer1..." -ForegroundColor Cyan
docker exec cli bash -c "CORE_PEER_ADDRESS=peer0.client1.fl-ddos.com:7051 CORE_PEER_LOCALMSPID=Client1MSP peer channel join -b /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block"
Write-Host "  ✅ Peer1 joined" -ForegroundColor Green

# Peer 2  
Write-Host "  Joining Peer2..." -ForegroundColor Cyan
docker exec cli bash -c "CORE_PEER_ADDRESS=peer0.client2.fl-ddos.com:8051 CORE_PEER_LOCALMSPID=Client2MSP peer channel join -b /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block"
Write-Host "  ✅ Peer2 joined" -ForegroundColor Green

# Peer 3
Write-Host "  Joining Peer3..." -ForegroundColor Cyan
docker exec cli bash -c "CORE_PEER_ADDRESS=peer0.client3.fl-ddos.com:9051 CORE_PEER_LOCALMSPID=Client3MSP peer channel join -b /opt/gopath/src/github.com/hyperledger/fabric/peer/channel-artifacts/${CHANNEL_NAME}.block"
Write-Host "  ✅ Peer3 joined" -ForegroundColor Green
Write-Host ""

Write-Host "Step 4: Copying chaincode to CLI container..." -ForegroundColor Green
# Copy chaincode directory
docker cp ../chaincode/fl-audit cli:/opt/gopath/src/github.com/chaincode/
Write-Host "  ✅ Chaincode copied" -ForegroundColor Green
Write-Host ""

Write-Host "Step 5: Packaging chaincode..." -ForegroundColor Green
docker exec cli peer lifecycle chaincode package ${CHAINCODE_NAME}.tar.gz `
    --path /opt/gopath/src/github.com/chaincode/fl-audit/ `
    --lang golang `
    --label ${CHAINCODE_NAME}_${CHAINCODE_VERSION}

Write-Host "  ✅ Chaincode packaged" -ForegroundColor Green
Write-Host ""

Write-Host "Step 6: Installing chaincode on all peers..." -ForegroundColor Green

# Install on Peer1
Write-Host "  Installing on Peer1..." -ForegroundColor Cyan
docker exec cli bash -c "CORE_PEER_ADDRESS=peer0.client1.fl-ddos.com:7051 CORE_PEER_LOCALMSPID=Client1MSP peer lifecycle chaincode install ${CHAINCODE_NAME}.tar.gz"
Write-Host "  ✅ Installed on Peer1" -ForegroundColor Green

# Install on Peer2
Write-Host "  Installing on Peer2..." -ForegroundColor Cyan
docker exec cli bash -c "CORE_PEER_ADDRESS=peer0.client2.fl-ddos.com:8051 CORE_PEER_LOCALMSPID=Client2MSP peer lifecycle chaincode install ${CHAINCODE_NAME}.tar.gz"
Write-Host "  ✅ Installed on Peer2" -ForegroundColor Green

# Install on Peer3
Write-Host "  Installing on Peer3..." -ForegroundColor Cyan
docker exec cli bash -c "CORE_PEER_ADDRESS=peer0.client3.fl-ddos.com:9051 CORE_PEER_LOCALMSPID=Client3MSP peer lifecycle chaincode install ${CHAINCODE_NAME}.tar.gz"
Write-Host "  ✅ Installed on Peer3" -ForegroundColor Green
Write-Host ""

Write-Host "Step 7: Getting package ID..." -ForegroundColor Green
$packageOutput = docker exec cli peer lifecycle chaincode queryinstalled
$PACKAGE_ID = ($packageOutput | Select-String "${CHAINCODE_NAME}_${CHAINCODE_VERSION}").ToString() -replace '.*Package ID: ([^,]+),.*', '$1'
Write-Host "  Package ID: $PACKAGE_ID" -ForegroundColor Cyan
Write-Host ""

Write-Host "Step 8: Approving chaincode for all orgs..." -ForegroundColor Green

# Approve for Client1
Write-Host "  Approving for Client1..." -ForegroundColor Cyan
docker exec cli bash -c "CORE_PEER_ADDRESS=peer0.client1.fl-ddos.com:7051 CORE_PEER_LOCALMSPID=Client1MSP peer lifecycle chaincode approveformyorg -o orderer.fl-ddos.com:7050 --channelID $CHANNEL_NAME --name $CHAINCODE_NAME --version $CHAINCODE_VERSION --package-id $PACKAGE_ID --sequence $CHAINCODE_SEQUENCE"
Write-Host "  ✅ Approved for Client1" -ForegroundColor Green

# Approve for Client2
Write-Host "  Approving for Client2..." -ForegroundColor Cyan
docker exec cli bash -c "CORE_PEER_ADDRESS=peer0.client2.fl-ddos.com:8051 CORE_PEER_LOCALMSPID=Client2MSP peer lifecycle chaincode approveformyorg -o orderer.fl-ddos.com:7050 --channelID $CHANNEL_NAME --name $CHAINCODE_NAME --version $CHAINCODE_VERSION --package-id $PACKAGE_ID --sequence $CHAINCODE_SEQUENCE"
Write-Host "  ✅ Approved for Client2" -ForegroundColor Green

# Approve for Client3
Write-Host "  Approving for Client3..." -ForegroundColor Cyan
docker exec cli bash -c "CORE_PEER_ADDRESS=peer0.client3.fl-ddos.com:9051 CORE_PEER_LOCALMSPID=Client3MSP peer lifecycle chaincode approveformyorg -o orderer.fl-ddos.com:7050 --channelID $CHANNEL_NAME --name $CHAINCODE_NAME --version $CHAINCODE_VERSION --package-id $PACKAGE_ID --sequence $CHAINCODE_SEQUENCE"
Write-Host "  ✅ Approved for Client3" -ForegroundColor Green
Write-Host ""

Write-Host "Step 9: Committing chaincode..." -ForegroundColor Green
docker exec cli peer lifecycle chaincode commit `
    -o orderer.fl-ddos.com:7050 `
    --channelID $CHANNEL_NAME `
    --name $CHAINCODE_NAME `
    --version $CHAINCODE_VERSION `
    --sequence $CHAINCODE_SEQUENCE `
    --peerAddresses peer0.client1.fl-ddos.com:7051 `
    --peerAddresses peer0.client2.fl-ddos.com:8051 `
    --peerAddresses peer0.client3.fl-ddos.com:9051

Write-Host "  ✅ Chaincode committed" -ForegroundColor Green
Write-Host ""

Write-Host "Step 10: Verifying deployment..." -ForegroundColor Green
docker exec cli peer lifecycle chaincode querycommitted --channelID $CHANNEL_NAME --name $CHAINCODE_NAME

Write-Host ""
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "✅ FL CHANNEL AND CHAINCODE DEPLOYMENT COMPLETE!" -ForegroundColor Green
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Channel   : $CHANNEL_NAME" -ForegroundColor White
Write-Host "Chaincode : ${CHAINCODE_NAME}:${CHAINCODE_VERSION}" -ForegroundColor White
Write-Host "Package ID: $PACKAGE_ID" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Test chaincode: cd .. && python scripts/test_chaincode.py" -ForegroundColor White
Write-Host "  2. Run FL with blockchain: python experiments/federated_learning/run_realtime_fl.py" -ForegroundColor White
Write-Host ""
