# Hyperledger Fabric Network Setup Script for Windows
# This script initializes the blockchain network infrastructure

$FABRIC_DIR = Get-Location
Write-Host "🔗 Initializing Hyperledger Fabric Network for FL-DDoS..." -ForegroundColor Cyan

# Step 1: Check prerequisites
Write-Host "📋 Checking prerequisites..." -ForegroundColor Yellow
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker is not installed" -ForegroundColor Red
    exit 1
}
if (-not (Get-Command docker-compose -ErrorAction SilentlyContinue)) {
    Write-Host "❌ Docker Compose is not installed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker and Docker Compose found" -ForegroundColor Green

# Step 2: Download Fabric binaries (if not present)
if (-not (Test-Path "$FABRIC_DIR\bin")) {
    Write-Host "📦 Downloading Hyperledger Fabric binaries..." -ForegroundColor Yellow
    Write-Host "⚠️  Please download manually from: https://hyperledger-fabric.readthedocs.io/en/release-2.5/install.html" -ForegroundColor Yellow
    Write-Host "   Extract to: $FABRIC_DIR\bin" -ForegroundColor Yellow
    Read-Host "Press Enter after downloading..."
} else {
    Write-Host "✓ Fabric binaries already present" -ForegroundColor Green
}

# Add binaries to PATH
$env:PATH = "$FABRIC_DIR\bin;$env:PATH"

# Step 3: Generate crypto material
Write-Host "🔐 Generating cryptographic material..." -ForegroundColor Yellow
if (Test-Path "$FABRIC_DIR\crypto-config") {
    Write-Host "  Removing old crypto material..." -ForegroundColor Gray
    Remove-Item -Recurse -Force "$FABRIC_DIR\crypto-config"
}

& "$FABRIC_DIR\bin\cryptogen" generate --config=crypto-config.yaml --output="crypto-config"
Write-Host "✓ Crypto material generated" -ForegroundColor Green

# Step 4: Ensure channel-artifacts directory exists
if (-not (Test-Path "$FABRIC_DIR\channel-artifacts")) {
    New-Item -ItemType Directory -Path "$FABRIC_DIR\channel-artifacts" | Out-Null
}

Write-Host ""
Write-Host "🎉 Initial setup complete!" -ForegroundColor Green
Write-Host ""
Write-Host "⚠️  WARNING: Full Hyperledger Fabric is designed for Linux." -ForegroundColor Yellow
Write-Host "   For Windows, consider using:" -ForegroundColor Yellow
Write-Host "   1. WSL2 (Windows Subsystem for Linux)" -ForegroundColor Cyan
Write-Host "   2. Docker Desktop with Linux containers" -ForegroundColor Cyan
Write-Host "   3. Python SDK simulation mode (already implemented)" -ForegroundColor Cyan
Write-Host ""
Write-Host "For this project, the Python client will use SIMULATION MODE by default." -ForegroundColor Green
Write-Host "The simulation provides the same API and audit logging without Docker." -ForegroundColor Green
Write-Host ""
