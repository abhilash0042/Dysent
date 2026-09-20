#!/bin/bash
# Quick WSL Setup for FL Execution
# Creates WSL virtual environment and installs dependencies

echo "======================================================================"
echo "WSL ENVIRONMENT SETUP FOR FL"
echo "======================================================================"
echo ""

# Check Python
echo "Step 1: Checking Python..."
python3 --version || { echo "❌ Python3 not found. Install with: sudo apt install python3"; exit 1; }
echo "✅ Python3 found"
echo ""

# Check pip
echo "Step 2: Checking pip..."
python3 -m pip --version || { echo "Installing pip..."; sudo apt install python3-pip -y; }
echo "✅ pip ready"
echo ""

# Create WSL virtual environment
echo "Step 3: Creating WSL virtual environment..."
if [ -d ".venv-wsl" ]; then
    echo "⚠️  .venv-wsl already exists, using existing"
else
    python3 -m venv .venv-wsl
    echo "✅ Virtual environment created"
fi
echo ""

# Activate virtual environment
echo "Step 4: Activating virtual environment..."
source .venv-wsl/bin/activate
echo "✅ Virtual environment activated"
echo ""

# Upgrade pip
echo "Step 5: Upgrading pip..."
pip install --upgrade pip
echo ""

# Install core dependencies
echo "Step 6: Installing core dependencies..."
pip install tensorflow==2.18.0
pip install numpy pandas scikit-learn
pip install python-dotenv requests
pip install matplotlib seaborn
echo "✅ Core dependencies installed"
echo ""

# Install additional dependencies from requirements.txt if it exists
if [ -f "requirements.txt" ]; then
    echo "Step 7: Installing from requirements.txt..."
    pip install -r requirements.txt
    echo "✅ Additional dependencies installed"
else
    echo "Step 7: No requirements.txt found, skipping"
fi
echo ""

echo "======================================================================"
echo "✅ WSL ENVIRONMENT READY!"
echo "======================================================================"
echo ""
echo "To activate in future sessions:"
echo "  source .venv-wsl/bin/activate"
echo ""
echo "To run FL training:"
echo "  python experiments/federated_learning/run_realtime_fl.py"
echo ""
