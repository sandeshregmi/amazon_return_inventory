#!/bin/bash
# Launches the Return Inventory app in your browser.

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

if [ ! -d ".venv" ]; then
    echo "Setup hasn't been run yet."
    echo "Double-click setup.command first (one time only), then try this again."
    read -p "Press Enter to close..."
    exit 1
fi

source .venv/bin/activate
streamlit run app.py
