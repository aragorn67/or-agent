#!/bin/bash

# Setup script for Optimization Agent
echo "Setting up Optimization Agent..."

# Create virtual environment
echo "Creating virtual environment 'Tolis_Env'..."
python3 -m venv Tolis_Env

# Activate and install dependencies
echo "Installing Python packages..."
source Tolis_Env/bin/activate
pip install -r requirements.txt

echo "Setup complete!"
echo ""
echo "To run the application:"
echo "1. Activate environment: source Tolis_Env/bin/activate"
echo "2. Start server: uvicorn api:app --reload --host 0.0.0.0 --port 8000"
echo "3. Open browser: http://localhost:8000"
echo ""
echo "Note: Make sure GLPK is installed on your system:"
echo "Ubuntu/Debian: sudo apt install glpk-utils"
echo "macOS: brew install glpk"