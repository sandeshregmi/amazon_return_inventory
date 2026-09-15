"""
Thin wrapper around a small, dependency-free Streamlit component for taking
photos. Replaces Streamlit's built-in st.camera_input, which has no way to
force the rear camera or request a higher resolution - both real problems
on phones. This component forces the rear camera (with graceful fallbacks)
and requests 1920x1080, giving a noticeably sharper, correctly-facing photo.
"""

from __future__ import annotations

import base64
import io
from pathlib import Path

import streamlit.components.v1 as components

from applog import get_logger

log = get_logger()

_COMPONENT_DIR = Path(__file__).parent / "photo_capture_component"

_capture_component = components.declare_component(
    "photo_capture",
    path=str(_COMPONENT_DIR),
)


def capture_photo(key: str | None = None):
    """
    Renders the photo capture widget. Returns a BytesIO of JPEG bytes once
    a photo has been taken (compatible anywhere the rest of the app expects
    an uploaded-file-like object, e.g. PIL.Image.open), or None if nothing
    has been captured yet.
    """
    data_url = _capture_component(key=key, default=None)
    if not data_url:
        return None
    try:
        _, b64data = data_url.split(",", 1)
        raw = base64.b64decode(b64data)
        buf = io.BytesIO(raw)
        buf.seek(0)
        return buf
    except Exception as e:
        log.warning(f"Failed to decode captured photo: {e}")
        return None
