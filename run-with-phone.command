#!/bin/bash
# Launches Return Inventory AND exposes it over HTTPS via ngrok, so you can
# open the app on your phone and use its camera to scan barcodes.
#
# One-time requirement: ngrok installed and signed in.
#   brew install ngrok
#   ngrok config add-authtoken YOUR_TOKEN   (free account at ngrok.com)

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    echo "Setup hasn't been run yet."
    echo "Double-click setup.command first (one time only), then try this again."
    read -p "Press Enter to close..."
    exit 1
fi

if ! command -v ngrok >/dev/null 2>&1; then
    echo "ngrok isn't installed yet."
    echo ""
    echo "  1. Install it:      brew install ngrok"
    echo "     (no Homebrew? get it free at https://brew.sh)"
    echo "  2. Free account:    https://dashboard.ngrok.com/signup"
    echo "  3. Connect it:      ngrok config add-authtoken YOUR_TOKEN"
    echo "                      (token is on your ngrok dashboard)"
    echo ""
    echo "Then run this script again."
    read -p "Press Enter to close..."
    exit 1
fi

source .venv/bin/activate

echo "Starting Return Inventory..."
streamlit run app.py --server.headless true > /tmp/return-inventory-streamlit.log 2>&1 &
STREAMLIT_PID=$!

echo "Starting secure tunnel (ngrok)..."
ngrok http 8501 --log=stdout > /tmp/return-inventory-ngrok.log 2>&1 &
NGROK_PID=$!

cleanup() {
    echo ""
    echo "Shutting down..."
    kill "$STREAMLIT_PID" 2>/dev/null
    kill "$NGROK_PID" 2>/dev/null
    exit 0
}
trap cleanup INT TERM

echo "Waiting for the tunnel to come up..."
URL=""
for i in $(seq 1 25); do
    URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    https = [t['public_url'] for t in data.get('tunnels', []) if t['public_url'].startswith('https')]
    print(https[0] if https else '')
except Exception:
    print('')
" 2>/dev/null)
    if [ -n "$URL" ]; then
        break
    fi
    sleep 1
done

echo ""
echo "======================================================"
if [ -n "$URL" ]; then
    echo " Open this address in your phone's browser:"
    echo ""
    echo "   $URL"
    echo ""
    echo " Camera access will only work through this address —"
    echo " not through your Mac's plain local IP address."
else
    echo " Couldn't detect the tunnel URL — likely ngrok isn't"
    echo " signed in yet. Recent log lines:"
    echo ""
    tail -n 8 /tmp/return-inventory-ngrok.log
    echo ""
    echo " If you see an authentication error above, run:"
    echo "   ngrok config add-authtoken YOUR_TOKEN"
    echo " (free token from https://dashboard.ngrok.com)"
fi
echo "======================================================"
echo ""
echo "Leave this window open while you use the app on your phone."
echo "Close this window (or press Ctrl+C here) to stop everything."
echo ""

wait
