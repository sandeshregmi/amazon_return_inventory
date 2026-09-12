"""
Thin wrapper around a small, dependency-free Streamlit component that opens
the device camera and decodes barcodes/QR codes client-side (via html5-qrcode,
loaded from a CDN inside the component's static HTML — no extra pip installs).
"""

from __future__ import annotations

from pathlib import Path
import streamlit.components.v1 as components

_COMPONENT_DIR = Path(__file__).parent / "barcode_scanner_component"

_scan_component = components.declare_component(
    "barcode_scanner",
    path=str(_COMPONENT_DIR),
)


def scan_barcode(key: str | None = None):
    """
    Renders the camera scanner widget. Returns the decoded barcode string
    once a scan succeeds, otherwise None. Pass a changing `key` (e.g. a
    counter in st.session_state) to force the widget to remount and restart
    the camera for a fresh scan.
    """
    return _scan_component(key=key, default=None)
