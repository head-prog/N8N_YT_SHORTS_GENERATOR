#!/bin/bash

# Set the current directory to the script's directory
cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "🔧 Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    echo "🔧 Installing dependencies..."
    pip install -r requirements.txt
else
    echo "✅ Using existing virtual environment"
    source venv/bin/activate
fi

# Run the main.py script
echo "🚀 Starting the server with virtual environment..."
python main.py

# If the server was stopped, deactivate the virtual environment
deactivate
