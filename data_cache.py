"""
Short-term caching for the shared inventory list, so rapid repeated
interactions (typing in search, clicking buttons elsewhere on the page)
don't each trigger a fresh network round-trip to the shared database.

Every add/update/delete calls invalidate() right after it, so your OWN
changes always show up immediately. Someone else's changes (e.g. your
partner adding an item) may take up to CACHE_TTL_SECONDS to show up on
your screen, since there's no way to instantly know about a change made
somewhere else without polling.
"""

from __future__ import annotations

import streamlit as st

import inventory_core as core

CACHE_TTL_SECONDS = 5


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def get_items_cached():
    return core.get_items()


def invalidate():
    """Call this right after any add/update/delete."""
    get_items_cached.clear()
