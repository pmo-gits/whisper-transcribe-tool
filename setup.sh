#!/bin/bash
echo "==================================================="
echo "Setting up Whisper Transcription Tool on macOS..."
echo "==================================================="

# 1. Check if python3 is available
if ! command -v python3 &> /dev/null; then
    echo "ERROR: python3 could not be found. Please install Python 3."
    exit 1
fi

# 2. Create virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

# 3. Install dependencies
echo "Installing libraries from requirements.txt..."
./.venv/bin/python -m pip install --upgrade pip
./.venv/bin/pip install -r requirements.txt

echo ""
echo "==================================================="
echo "SETUP COMPLETE! You are ready to transcribe."
echo ""
echo "To see your videos, run:"
echo "  ./.venv/bin/python transcribe.py --list"
echo ""
echo "To transcribe video #1, run:"
echo "  ./.venv/bin/python transcribe.py 1"
echo "==================================================="
