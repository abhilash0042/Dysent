# PowerShell Deployment Script for FL-DDoS Detection System
# Windows Docker Desktop deployment

Write-Host "=========================================="  -ForegroundColor Cyan
Write-Host "FL-DDoS Real-Time Docker Deployment"  -ForegroundColor Cyan
Write-Host "=========================================="  -ForegroundColor Cyan
Write-Host ""

# Check if Docker is running
try {
    docker info | Out-Null
    Write-Host "✓ Docker is running" -ForegroundColor Green
}
catch {
    Write-Host "❌ Docker is not running. Please start Docker Desktop." -ForegroundColor Red
    exit 1
}

# Check if Hyperledger Fabric is initialized
if (!(Test-Path "fabric\crypto-config")) {
    Write-Host ""
    Write-Host "⚠ Hyperledger Fabric not initialized" -ForegroundColor Yellow
    Write-Host "Initializing blockchain network..."
    Push-Location fabric
    & .\setup-network.ps1
    Pop-Location
}

Write-Host "✓ Blockchain initialized" -ForegroundColor Green

# Load .env if exists
if (Test-Path ".env") {
    Write-Host "✓ Loading environment variables from .env" -ForegroundColor Green
    Get-Content .env | ForEach-Object {
        if ($_ -match '^([^#][^=]+)=(.*)$') {
            [Environment]::SetEnvironmentVariable($matches[1], $matches[2], "Process")
        }
    }
}
else {
    Write-Host "⚠ No .env file found - using defaults" -ForegroundColor Yellow
}

# Build images
Write-Host ""
Write-Host "Building Docker images..." -ForegroundColor Cyan
docker-compose build

# Start infrastructure
Write-Host ""
Write-Host "Starting FL-DDoS infrastructure..." -ForegroundColor Cyan
Write-Host ""

# Start blockchain
Write-Host "1. Starting Hyperledger Fabric blockchain..." -ForegroundColor Yellow
docker-compose up -d orderer.fl-ddos.com `
    peer0.client1.fl-ddos.com `
    peer0.client2.fl-ddos.com `
    peer0.client3.fl-ddos.com

Write-Host "   Waiting for blockchain to stabilize..."
Start-Sleep -Seconds 10

# Start application layer
Write-Host ""
Write-Host "2. Starting dashboard and FL server..." -ForegroundColor Yellow
docker-compose up -d dashboard fl_server

Start-Sleep -Seconds 5

# Start FL nodes
Write-Host ""
Write-Host "3. Starting FL nodes for real-time data collection..." -ForegroundColor Yellow
docker-compose up -d fl_node_1 fl_node_2

# Start detector
Write-Host ""
Write-Host "4. Starting real-time DDoS detector..." -ForegroundColor Yellow
docker-compose up -d realtime_detector

# Optional monitoring
Write-Host ""
$monitor = Read-Host "Start Portainer for monitoring? (y/n)"
if ($monitor -eq 'y' -or $monitor -eq 'Y') {
    docker-compose up -d portainer
    Write-Host "✓ Portainer started at https://localhost:9443" -ForegroundColor Green
}

# Show status
Write-Host ""
Write-Host "=========================================="  -ForegroundColor Cyan
Write-Host "Deployment Complete!"  -ForegroundColor Green
Write-Host "=========================================="  -ForegroundColor Cyan
Write-Host ""
Write-Host "Services:" -ForegroundColor White
Write-Host "  ✓ Blockchain:      Running (4 containers)" -ForegroundColor Green
Write-Host "  ✓ Dashboard:       http://localhost:5000" -ForegroundColor Green
Write-Host "  ✓ FL Server:       Running on port 8000" -ForegroundColor Green
Write-Host "  ✓ FL Nodes:        2 nodes capturing live traffic" -ForegroundColor Green
Write-Host "  ✓ Real-Time Detector: Active" -ForegroundColor Green
Write-Host ""
Write-Host "Commands:" -ForegroundColor White
Write-Host "  View logs:    docker-compose logs -f [service_name]"
Write-Host "  Stop all:     docker-compose down"
Write-Host "  Restart:      docker-compose restart [service_name]"
Write-Host ""
Write-Host "Check status: docker-compose ps" -ForegroundColor Cyan
Write-Host "=========================================="  -ForegroundColor Cyan

# Show running containers
docker-compose ps
