"""
Centralized logging for the Return Inventory app.

Two destinations for every log line:
  1. stdout - shows up in Streamlit Community Cloud's own log viewer
     (Manage app -> logs), which persists even if the app crashes.
  2. An in-memory ring buffer - lets the app show recent activity directly
     in its own Diagnostics panel, without needing to leave the app at all.

Note: since this is module-level state, the in-memory buffer is shared
across every user currently using a given running app instance (not
per-browser-session) - which is actually useful here, since it means you
can see what your partner's been doing too, not just your own actions.
"""

from __future__ import annotations

import logging
from collections import deque

_MAX_BUFFERED_LINES = 300
_LOG_BUFFER: deque[str] = deque(maxlen=_MAX_BUFFERED_LINES)


class _BufferHandler(logging.Handler):
    def emit(self, record):
        try:
            _LOG_BUFFER.append(self.format(record))
        except Exception:
            pass  # logging itself must never crash the app


def get_logger() -> logging.Logger:
    logger = logging.getLogger("return_inventory")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(fmt)
        logger.addHandler(stream_handler)

        buffer_handler = _BufferHandler()
        buffer_handler.setFormatter(fmt)
        logger.addHandler(buffer_handler)

        logger.propagate = False
    return logger


def recent_logs(n: int = _MAX_BUFFERED_LINES) -> list[str]:
    """Most recent log lines, oldest first."""
    return list(_LOG_BUFFER)[-n:]
