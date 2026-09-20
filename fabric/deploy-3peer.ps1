# Generate MSP crypto material for 3-peer Hyperledger Fabric network
# This creates self-signed certificates for dev/demo environment

$ErrorActionPreference = "Continue"
$fabricDir = "C:\Users\HP\Desktop\Major Project\Main File-Code\ddosdfl\fabric"

Write-Host "============================================================"
Write-Host "GENERATING MSP CERTIFICATES FOR 3-PEER BLOCKCHAIN"
Write-Host "============================================================"

# ============================================================
# Helper function to create MSP directory structure
# ============================================================
function New-MSPStructure {
    param([string]$BasePath, [string]$OrgName, [string]$CN)
    
    $mspDir = "$BasePath\msp"
    $dirs = @(
        "$mspDir\admincerts",
        "$mspDir\cacerts",
        "$mspDir\keystore",
        "$mspDir\signcerts",
        "$mspDir\tlscacerts"
    )
    foreach ($d in $dirs) {
        New-Item -ItemType Directory -Force -Path $d | Out-Null
    }

    # Generate private key using OpenSSL
    $keyFile = "$mspDir\keystore\key.pem"
    $certFile = "$mspDir\signcerts\cert.pem"
    $caFile = "$mspDir\cacerts\ca.pem"

    # Generate self-signed cert with OpenSSL
    $subject = "/C=US/ST=California/L=SanFrancisco/O=$OrgName/CN=$CN"
    
    # Try openssl from Docker if not available locally
    docker run --rm -v "${mspDir}:/certs" alpine/openssl req -x509 -newkey rsa:2048 -keyout /certs/keystore/key.pem -out /certs/signcerts/cert.pem -days 365 -nodes -subj $subject 2>$null
    
    if ($LASTEXITCODE -ne 0) {
        # Fallback: use openssl if installed
        openssl req -x509 -newkey rsa:2048 -keyout $keyFile -out $certFile -days 365 -nodes -subj $subject 2>$null
    }

    # Copy cert as CA cert and admin cert
    if (Test-Path $certFile) {
        Copy-Item $certFile $caFile -Force
        Copy-Item $certFile "$mspDir\admincerts\cert.pem" -Force
        Copy-Item $certFile "$mspDir\tlscacerts\ca.pem" -Force
        Write-Host "  [OK] MSP created for $CN"
    } else {
        Write-Host "  [WARN] OpenSSL not available, using Python fallback..."
        # Python fallback to generate certs
        python -c @"
from cryptography import x509
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import datetime, os

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
subject = issuer = x509.Name([
    x509.NameAttribute(NameOID.COUNTRY_NAME, 'US'),
    x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, 'California'),
    x509.NameAttribute(NameOID.ORGANIZATION_NAME, '$OrgName'),
    x509.NameAttribute(NameOID.COMMON_NAME, '$CN'),
])
cert = (x509.CertificateBuilder()
    .subject_name(subject).issuer_name(issuer)
    .public_key(key.public_key())
    .serial_number(x509.random_serial_number())
    .not_valid_before(datetime.datetime.utcnow())
    .not_valid_after(datetime.datetime.utcnow() + datetime.timedelta(days=365))
    .sign(key, hashes.SHA256()))

msp = r'$mspDir'
with open(os.path.join(msp, 'keystore', 'key.pem'), 'wb') as f:
    f.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
cert_pem = cert.public_bytes(serialization.Encoding.PEM)
for sub in ['signcerts/cert.pem', 'cacerts/ca.pem', 'admincerts/cert.pem', 'tlscacerts/ca.pem']:
    with open(os.path.join(msp, sub), 'wb') as f:
        f.write(cert_pem)
print(f'  [OK] MSP created for $CN (Python)')
"@
    }
}

# ============================================================
# Step 1: Stop existing containers
# ============================================================
Write-Host "`nStep 1: Stopping existing containers..."
docker-compose -f "$fabricDir\docker-compose-production.yml" down --remove-orphans 2>$null
Write-Host "  Done`n"

# ============================================================
# Step 2: Generate crypto material
# ============================================================
Write-Host "Step 2: Generating crypto material..."

# Orderer MSP
Write-Host "  Generating Orderer certificates..."
New-MSPStructure -BasePath "$fabricDir\crypto-config\ordererOrganizations\ddos.com\orderers\orderer.ddos.com" -OrgName "OrdererOrg" -CN "orderer.ddos.com"

# Peer 0 MSP
Write-Host "  Generating Peer0 certificates..."
New-MSPStructure -BasePath "$fabricDir\crypto-config\peerOrganizations\fl.ddos.com\peers\peer0.fl.ddos.com" -OrgName "FLMSP" -CN "peer0.fl.ddos.com"

# Peer 1 MSP (reuse peer0 certs since same org)
Write-Host "  Generating Peer1 certificates..."
$peer1Dir = "$fabricDir\crypto-config\peerOrganizations\fl.ddos.com\peers\peer1.fl.ddos.com"
New-Item -ItemType Directory -Force -Path $peer1Dir | Out-Null
New-MSPStructure -BasePath $peer1Dir -OrgName "FLMSP" -CN "peer1.fl.ddos.com"

# Peer 2 MSP
Write-Host "  Generating Peer2 certificates..."
$peer2Dir = "$fabricDir\crypto-config\peerOrganizations\fl.ddos.com\peers\peer2.fl.ddos.com"
New-Item -ItemType Directory -Force -Path $peer2Dir | Out-Null
New-MSPStructure -BasePath $peer2Dir -OrgName "FLMSP" -CN "peer2.fl.ddos.com"

# Org-level MSP (needed for channel operations)
Write-Host "  Generating Org-level MSP..."
New-MSPStructure -BasePath "$fabricDir\crypto-config\peerOrganizations\fl.ddos.com" -OrgName "FLMSP" -CN "fl.ddos.com"
New-MSPStructure -BasePath "$fabricDir\crypto-config\ordererOrganizations\ddos.com" -OrgName "OrdererOrg" -CN "ddos.com"

Write-Host "  All certificates generated`n"

# ============================================================
# Step 3: Create channel artifacts directory
# ============================================================
Write-Host "Step 3: Creating channel artifacts..."
New-Item -ItemType Directory -Force -Path "$fabricDir\channel-artifacts" | Out-Null
# Create empty genesis block placeholder
[byte[]]$emptyBlock = @()
[System.IO.File]::WriteAllBytes("$fabricDir\channel-artifacts\genesis.block", $emptyBlock)
Write-Host "  Done`n"

# ============================================================
# Step 4: Deploy 3-peer blockchain
# ============================================================
Write-Host "Step 4: Deploying 3-peer blockchain network..."
docker-compose -f "$fabricDir\docker-compose-production.yml" up -d

Write-Host "`nStep 5: Waiting 10 seconds for containers to stabilize..."
Start-Sleep -Seconds 10

# ============================================================
# Step 5: Verify deployment
# ============================================================
Write-Host "`nStep 6: Verifying deployment..."
$containers = docker ps --format "{{.Names}} | {{.Status}}" --filter "name=fabric"
Write-Host $containers

$peerCount = (docker ps --filter "name=peer" --filter "status=running" -q).Count
$couchCount = (docker ps --filter "name=couchdb" --filter "status=running" -q).Count

Write-Host "`n============================================================"
Write-Host "DEPLOYMENT SUMMARY"
Write-Host "============================================================"
Write-Host "  Peers Running: $peerCount / 3"
Write-Host "  CouchDB Running: $couchCount / 3"
Write-Host "  Orderer: $(if (docker ps --filter 'name=orderer' --filter 'status=running' -q) { 'Running' } else { 'Not Running' })"
Write-Host "  CA: $(if (docker ps --filter 'name=ca' --filter 'status=running' -q) { 'Running' } else { 'Not Running' })"
Write-Host "============================================================"

if ($peerCount -ge 3) {
    Write-Host "`n  3-PEER BLOCKCHAIN DEPLOYED SUCCESSFULLY!" -ForegroundColor Green
} else {
    Write-Host "`n  Some peers may still be starting. Check with: docker ps" -ForegroundColor Yellow
}
