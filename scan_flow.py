"""
The "Scan Barcode" flow, as a strict 3-step wizard:

  1) Scan the barcode (camera, or type it in by hand)
  2) Take a photo of the product (explicitly confirms if you skip this)
  3) Confirm the product name/quantity, and save

Kept in its own module, separate from app.py's general page layout and the
Manual Entry tab, so each step is easy to find, read, and change on its own
without wading through unrelated code.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

import inventory_core as core
import data_cache
from barcode_scanner import scan_barcode
from photo_capture import capture_photo
from applog import get_logger

log = get_logger()

# All state for this flow lives under these keys, namespaced with "sf_" so
# nothing here can collide with session state used elsewhere in the app.
_DEFAULTS = {
    "sf_stage": "scan",  # "scan" -> "photo" -> "confirm"
    "sf_scanner_key": 0,  # bumped to force the camera components to remount fresh
    "sf_barcode": None,
    "sf_suggested_name": None,
    "sf_suggested_source": None,  # "known" | "online" | "ocr" | None
    "sf_photo": None,  # the captured photo (file-like), or None
    "sf_confirm_no_photo": False,  # whether the "did you forget?" prompt is showing
    "sf_ocr_attempted": False,
}


def _init_state():
    for k, v in _DEFAULTS.items():
        if k not in st.session_state:
            st.session_state[k] = v


def _reset_to_scan():
    """Back to step 1, with a fresh camera component instance."""
    next_scanner_key = st.session_state.get("sf_scanner_key", 0) + 1
    for k, v in _DEFAULTS.items():
        st.session_state[k] = v
    st.session_state.sf_scanner_key = next_scanner_key


def render_scan_tab():
    """Entry point called from app.py inside the Scan Barcode tab."""
    _init_state()
    stage = st.session_state.sf_stage
    if stage == "scan":
        _render_scan_step()
    elif stage == "photo":
        _render_photo_step()
    elif stage == "confirm":
        _render_confirm_step()


# ---------------------------------------------------------------- Step 1 --

def _render_scan_step():
    st.caption(
        "**Step 1 of 3 — Scan the barcode.** Needs the page opened as "
        "localhost or over HTTPS to work at all; see the README if it "
        "won't start on your phone."
    )
    scanned = scan_barcode(key=f"scanner_{st.session_state.sf_scanner_key}")
    if scanned:
        _on_barcode_captured(scanned)
        st.rerun()

    with st.expander("Camera won't pick up this barcode? Type it in instead"):
        with st.form("sf_manual_barcode_form", clear_on_submit=True):
            typed = st.text_input("Barcode number", placeholder="e.g. 827854027195")
            if st.form_submit_button("Use this barcode"):
                cleaned = typed.strip()
                if cleaned:
                    _on_barcode_captured(cleaned)
                    st.rerun()


def _on_barcode_captured(barcode: str):
    """
    Barcode is in hand: try the two lookups that don't need a photo right
    away (locally remembered, then the online UPC database). Move to the
    photo step either way — if neither found a name, OCR against the photo
    is tried automatically once it's taken, in the confirm step.
    """
    log.info(f"Scanned barcode {barcode}")
    st.session_state.sf_barcode = barcode

    known_name = core.lookup_barcode(barcode)
    if known_name:
        st.session_state.sf_suggested_name = known_name
        st.session_state.sf_suggested_source = "known"
    else:
        online_name = core.lookup_product_name_online(barcode)
        if online_name:
            st.session_state.sf_suggested_name = online_name
            st.session_state.sf_suggested_source = "online"

    st.session_state.sf_stage = "photo"


# ---------------------------------------------------------------- Step 2 --

def _render_photo_step():
    barcode = st.session_state.sf_barcode
    source = st.session_state.sf_suggested_source
    name = st.session_state.sf_suggested_name

    if source == "known":
        st.success(f"Recognized barcode **{barcode}** → {name}")
    elif source == "online":
        st.success(f"Found online: **{name}**")
    else:
        st.info(f"New barcode **{barcode}** — no match found yet. We'll try reading the name off the photo.")

    st.caption("**Step 2 of 3 — Take a photo of the product.**")
    photo = capture_photo(key=f"sf_photo_{st.session_state.sf_scanner_key}_{barcode}")
    if photo is not None:
        st.session_state.sf_photo = photo

    has_photo = st.session_state.sf_photo is not None

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Continue →", type="primary", key="sf_photo_continue"):
            if has_photo or st.session_state.sf_confirm_no_photo:
                st.session_state.sf_stage = "confirm"
                st.session_state.sf_confirm_no_photo = False
                st.rerun()
            else:
                st.session_state.sf_confirm_no_photo = True
    with col2:
        if st.button("Cancel", key="sf_photo_cancel"):
            _reset_to_scan()
            st.rerun()

    if st.session_state.sf_confirm_no_photo and not has_photo:
        st.warning("📷 **Did you forget to take a picture?**")
        c1, c2 = st.columns(2)
        with c1:
            if st.button("↺ Go back and take a photo", key="sf_photo_goback"):
                st.session_state.sf_confirm_no_photo = False
        with c2:
            if st.button("Continue without a photo", key="sf_photo_skip"):
                st.session_state.sf_stage = "confirm"
                st.session_state.sf_confirm_no_photo = False
                st.rerun()


# ---------------------------------------------------------------- Step 3 --

def _render_confirm_step():
    barcode = st.session_state.sf_barcode
    photo = st.session_state.sf_photo

    # Still no name from memory or the online lookup: try OCR against the
    # photo just taken, once per scan (not on every rerun of this step).
    if (
        st.session_state.sf_suggested_source is None
        and photo is not None
        and not st.session_state.sf_ocr_attempted
    ):
        st.session_state.sf_ocr_attempted = True
        if core.tesseract_available():
            with st.spinner("Reading text from photo…"):
                ocr_name = core.read_name_from_photo(photo)
            if ocr_name:
                st.session_state.sf_suggested_name = ocr_name
                st.session_state.sf_suggested_source = "ocr"

    if st.session_state.sf_suggested_source == "ocr":
        st.success(f"Read from photo: **{st.session_state.sf_suggested_name}** (double-check this)")

    st.caption("**Step 3 of 3 — Confirm and save.**")

    if photo is not None:
        st.image(photo, caption="Photo to save with this item", width=160)
    else:
        st.caption("No photo attached to this item.")

    existing_items = core.find_items_by_barcode(barcode)
    add_to_existing = False
    merge_target = None
    if existing_items:
        existing_total = sum(i["qty"] for i in existing_items)
        line_word = "line" if len(existing_items) == 1 else "lines"
        st.info(f"Already in inventory: **{existing_total}** unit(s) across {len(existing_items)} {line_word}.")
        choice = st.radio(
            "What would you like to do?",
            ["Add to the most recent existing line", "Log as a new separate line"],
            key=f"sf_merge_choice_{barcode}",
        )
        add_to_existing = choice.startswith("Add to")
        merge_target = existing_items[0]

    with st.form("sf_confirm_form", clear_on_submit=False):
        name = st.text_input("Product Name", value=st.session_state.sf_suggested_name or "")
        qty = st.number_input(
            "Quantity to add" if add_to_existing else "Quantity",
            min_value=1, step=1, value=1,
        )
        notes_default = (merge_target.get("notes") or "") if (add_to_existing and merge_target) else ""
        notes = st.text_input(
            "Notes (optional)",
            value=notes_default,
            placeholder="e.g. Package shows qty 2, only 1 sellable",
            help="Anything worth flagging about this specific item — condition, "
                 "missing parts, quantity discrepancies, etc.",
        )
        c1, c2 = st.columns(2)
        with c1:
            save = st.form_submit_button("Save item", type="primary")
        with c2:
            cancel = st.form_submit_button("Cancel / Start over")

    if save:
        if not name.strip():
            st.error("Product name is required.")
        else:
            today = date.today().isoformat()
            if add_to_existing and merge_target:
                # Always write whatever's in the box for a merge (including
                # blank, if the user intentionally cleared an old note) -
                # update_item treats notes=None as "leave unchanged", so an
                # empty string (not None) is what actually clears it.
                core.update_item(
                    merge_target["id"],
                    qty=merge_target["qty"] + int(qty),
                    update_date=today,
                    uploaded_file=photo,
                    notes=notes.strip(),
                )
                st.success(
                    f"Added {int(qty)} — {merge_target['name']} now at "
                    f"{merge_target['qty'] + int(qty)} units."
                )
            else:
                core.add_item(name.strip(), int(qty), today, today, photo, barcode=barcode, notes=notes.strip() or None)
                st.success(f"Saved {int(qty)} × {name.strip()} as a new line.")
            core.save_barcode_mapping(barcode, name.strip())
            data_cache.invalidate()
            _reset_to_scan()
            st.rerun()

    if cancel:
        _reset_to_scan()
        st.rerun()
