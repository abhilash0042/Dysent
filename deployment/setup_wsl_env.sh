#!/bin/bash
# Setup dedicated Mininet Environment in WSL (Native Linux filesystem to avoid I/O errors)

echo "🚀 Setting up Mininet Python Environment in HOME directory..."
echo "(This avoids WSL /mnt/c I/O errors)"

# 1. Create in HOME directory (native Linux filesystem)
VENV_PATH="$HOME/mininet_venv"

if [ ! -d "$VENV_PATH" ]; then
    echo "📦 Creating virtual environment at $VENV_PATH..."
    python3 -m venv "$VENV_PATH"
else
    echo "✅ Virtual environment already exists at $VENV_PATH"
fi

# 2. Activate and Install
echo "⬇️ Installing lightweight dependencies for Mininet..."
source "$VENV_PATH/bin/activate"

# Upgrade pip
pip install --upgrade pip

# Install LIGHTWEIGHT dependencies (CPU-only TensorFlow)
pip install -r ddosdfl/mininet_requirements.txt

echo " "
echo "✅ SETUP COMPLETE!"
echo "Virtual environment created at: $VENV_PATH"
echo "The simulation script will automatically detect and use this environment."
echo " "
echo "You can verify by running:"
echo "  $VENV_PATH/bin/python3 -c 'import numpy, yaml, tensorflow; print(\"All modules OK!\")'"
