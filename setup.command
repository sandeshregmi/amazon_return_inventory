#!/bin/bash
# One-time setup: creates a private Python environment in this folder
# and installs everything the app needs. Safe to run more than once.

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "Setting up Return Inventory..."
echo ""

if ! command -v python3 &> /dev/null; then
    echo "Python 3 was not found on this computer."
    echo "Install it from https://python.org (or via 'brew install python' on Mac), then run this script again."
    read -p "Press Enter to close..."
    exit 1
fi

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt --quiet

echo ""
echo "Setup complete."
echo "Double-click run.command to launch the app from now on."
read -p "Press Enter to close..."
