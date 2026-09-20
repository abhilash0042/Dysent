#!/bin/bash

# Docker Deployment Script for FL-DDoS Detection System
# Starts complete real-time infrastructure

set -e

echo "=========================================="
echo "FL-DDoS Real-Time Docker Deployment"
echo "=========================================="
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "✓ Docker is running"

# Check if Hyperledger Fabric is initialized
if [ ! -d "fabric/crypto-config" ]; then
    echo ""
    echo "⚠ Hyperledger Fabric not initialized"
    echo "Initializing blockchain network..."
    cd fabric
    ./setup-network.sh
    cd ..
fi

echo "✓ Blockchain initialized"

# Load environment variables
if [ -f ".env" ]; then
    echo "✓ Loading environment variables from .env"
    export $(cat .env | grep -v '#' | xargs)
else
    echo "⚠ No .env file found - using defaults"
fi

# Build Docker images
echo ""
echo "Building Docker images..."
docker-compose build

# Start infrastructure
echo ""
echo "Starting FL-DDoS infrastructure..."
echo ""

# Start blockchain first
echo "1. Starting Hyperledger Fabric blockchain..."
docker-compose up -d orderer.fl-ddos.com \
                     peer0.client1.fl-ddos.com \
                     peer0.client2.fl-ddos.com \
                     peer0.client3.fl-ddos.com

echo "   Waiting for blockchain to stabilize..."
sleep 10

# Start application layer
echo ""
echo "2. Starting dashboard and FL server..."
docker-compose up -d dashboard fl_server

sleep 5

# Start FL nodes
echo ""
echo "3. Starting FL nodes for real-time data collection..."
docker-compose up -d fl_node_1 fl_node_2

# Start real-time detector
echo ""
echo "4. Starting real-time DDoS detector..."
docker-compose up -d realtime_detector

# Optional: Start monitoring
echo ""
read -p "Start Portainer for monitoring? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker-compose up -d portainer
    echo "✓ Portainer started at https://localhost:9443"
fi

# Show status
echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Services:"
echo "  ✓ Blockchain:      Running (4 containers)"
echo "  ✓ Dashboard:       http://localhost:5000"
echo "  ✓ FL Server:       Running on port 8000"
echo "  ✓ FL Nodes:        2 nodes capturing live traffic"
echo "  ✓ Real-Time Detector: Active"
echo ""
echo "Commands:"
echo "  View logs:    docker-compose logs -f [service_name]"
echo "  Stop all:     docker-compose down"
echo "  Restart:      docker-compose restart [service_name]"
echo ""
echo "Check status: docker-compose ps"
echo "=========================================="

# Show running containers
docker-compose ps
