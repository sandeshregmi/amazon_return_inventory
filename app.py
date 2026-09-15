import streamlit as st
from datetime import date

import inventory_core as core
import scan_flow
import data_cache
from applog import get_logger, recent_logs

log = get_logger()

st.set_page_config(page_title="Return Inventory", page_icon="📦", layout="wide")

try:
    core.init_db()
except Exception as e:
    log.error(f"init_db() failed at startup: {e}")
    st.error(
        "⚠️ Couldn't set up the database on startup. Open the Diagnostics "
        "panel at the bottom of the page for details."
    )

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    /* ---- Header banner ---- */
    .app-header {
        display: flex;
        align-items: center;
        gap: 14px;
        padding: 4px 0 18px 0;
        margin-bottom: 6px;
        border-bottom: 1px solid #E2E8F0;
    }
    .app-header-icon {
        font-size: 34px;
        line-height: 1;
    }
    .app-header-title {
        font-size: 26px;
        font-weight: 700;
        color: #0F172A;
        margin: 0;
        line-height: 1.15;
    }
    .app-header-subtitle {
        font-size: 14px;
        color: #64748B;
        margin: 2px 0 0 0;
    }

    /* ---- Section labels ---- */
    .section-label {
        font-size: 13px;
        font-weight: 600;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        color: #64748B;
        margin: 4px 0 10px 0;
    }

    /* ---- Buttons ---- */
    .stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {
        border-radius: 8px;
        font-weight: 600;
        transition: box-shadow 0.15s ease, transform 0.05s ease;
    }
    .stButton > button:hover, .stDownloadButton > button:hover, .stFormSubmitButton > button:hover {
        box-shadow: 0 2px 8px rgba(37, 99, 235, 0.18);
    }

    /* ---- Bordered containers (add-item box, item cards) ---- */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 12px !important;
    }

    /* ---- Metrics ---- */
    [data-testid="stMetricValue"] {
        font-weight: 700;
        color: #0F172A;
    }
    [data-testid="stMetricLabel"] {
        color: #64748B;
    }

    /* ---- Photo thumbnails ---- */
    .inv-thumb-wrap {
        position: relative;
        display: inline-block;
        line-height: 0;
    }
    .inv-thumb-small {
        width: 56px;
        height: 56px;
        max-width: none !important;
        object-fit: cover !important;
        border-radius: 8px;
        cursor: zoom-in;
        display: block;
        border: 1px solid #E2E8F0;
    }
    .inv-thumb-zoom {
        display: none;
        position: absolute;
        top: 0;
        left: 0;
        width: 320px;
        height: 320px;
        max-width: none !important;
        object-fit: cover !important;
        border-radius: 10px;
        box-shadow: 0 12px 32px rgba(15, 23, 42, 0.28);
        z-index: 9999;
        border: 2px solid #FFFFFF;
    }
    .inv-thumb-wrap:hover .inv-thumb-zoom {
        display: block;
    }

    /* ---- Barcode pill ---- */
    .barcode-pill {
        display: inline-block;
        font-family: 'SF Mono', 'Menlo', monospace;
        font-size: 12px;
        color: #475569;
        background: #F1F5F9;
        border-radius: 6px;
        padding: 3px 8px;
    }
    </style>

    <div class="app-header">
        <div class="app-header-icon">📦</div>
        <div>
            <p class="app-header-title">Return Inventory</p>
            <p class="app-header-subtitle">Track Amazon returns and re-sell what's still sellable.</p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

if not core.is_shared_database():
    st.warning(
        "⚠️ **Not connected to the shared database.** This session is using its own "
        "local storage instead — anything added here won't be visible to anyone else, "
        "and may not be saved permanently. If this is the deployed app, check that "
        "`DATABASE_URL` is still set correctly in the app's Secrets.",
        icon="⚠️",
    )

# ---------- Add item ----------
if "confirm_no_photo_manual" not in st.session_state:
    st.session_state.confirm_no_photo_manual = False

with st.container(border=True):
    st.markdown('<p class="section-label">Add Inventory</p>', unsafe_allow_html=True)
    tab_scan, tab_manual = st.tabs(["📷 Scan Barcode", "✏️ Manual Entry"])

    # ---- Scan Barcode tab ----
    with tab_scan:
        scan_flow.render_scan_tab()

    # ---- Manual Entry tab ----
    with tab_manual:
        with st.form("add_item_form", clear_on_submit=False):
            col_photo, col_fields = st.columns([1, 2])

            with col_photo:
                uploaded_file = st.file_uploader(
                    "Photo", type=["jpg", "jpeg", "png", "webp"],
                    label_visibility="visible", key="manual_photo",
                )
                if uploaded_file is not None:
                    st.image(uploaded_file, width=140)

            with col_fields:
                name = st.text_input("Product Name", key="manual_name")
                barcode_manual = st.text_input(
                    "Barcode (optional)",
                    help="Fill this in if you want this item linked to a barcode for future scans.",
                    key="manual_barcode",
                )
                qty = st.number_input("Quantity", min_value=1, step=1, value=1, key="manual_qty")
                notes_manual = st.text_input(
                    "Notes (optional)",
                    placeholder="e.g. Package shows qty 2, only 1 sellable",
                    key="manual_notes",
                )
                c1, c2 = st.columns(2)
                with c1:
                    initial_date = st.date_input("Initial Entry Date", value=date.today(), key="manual_initial_date")
                with c2:
                    update_date = st.date_input("Update Date", value=date.today(), key="manual_update_date")

            submitted = st.form_submit_button("Save item", type="primary")
            if submitted:
                if not name.strip():
                    st.error("Product name is required.")
                    st.session_state.confirm_no_photo_manual = False
                elif uploaded_file is None and not st.session_state.confirm_no_photo_manual:
                    st.session_state.confirm_no_photo_manual = True
                    st.warning(
                        "📷 No photo attached. Click **Save item** again to save "
                        "without one, or add a photo above first."
                    )
                else:
                    clean_barcode = barcode_manual.strip() or None
                    core.add_item(
                        name.strip(),
                        int(qty),
                        initial_date.isoformat(),
                        update_date.isoformat(),
                        uploaded_file,
                        barcode=clean_barcode,
                        notes=notes_manual.strip() or None,
                    )
                    if clean_barcode:
                        core.save_barcode_mapping(clean_barcode, name.strip())
                    st.success(f"Saved '{name.strip()}'.")
                    st.session_state.confirm_no_photo_manual = False
                    data_cache.invalidate()
                    for k in ["manual_name", "manual_barcode", "manual_photo", "manual_notes"]:
                        st.session_state.pop(k, None)
                    st.rerun()

st.write("")

# ---------- Inventory list + export ----------
items = data_cache.get_items_cached()
total_units = sum(it["qty"] for it in items)

st.write("")
st.markdown('<p class="section-label">Inventory</p>', unsafe_allow_html=True)

header_col1, header_col2, header_col3 = st.columns([1, 1, 2])
with header_col1:
    st.metric("Lines", len(items))
with header_col2:
    st.metric("Units on hand", total_units)
with header_col3:
    st.write("")
    if items:
        if "excel_export_bytes" not in st.session_state:
            st.session_state.excel_export_bytes = None
        if st.session_state.excel_export_bytes is None:
            if st.button("⬇️ Prepare Excel Export (photos embedded)", type="primary"):
                with st.spinner("Building Excel file…"):
                    st.session_state.excel_export_bytes = core.build_excel_bytes(items)
                st.rerun()
        else:
            st.download_button(
                "✅ Download Excel file",
                data=st.session_state.excel_export_bytes,
                file_name=f"return-inventory-{date.today().isoformat()}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                type="primary",
                on_click=lambda: st.session_state.update(excel_export_bytes=None),
            )
    else:
        st.button("⬇️ Prepare Excel Export (photos embedded)", disabled=True)

st.write("")

search_query = st.text_input(
    "🔍 Search inventory", placeholder="Search by product name or barcode…", key="inventory_search"
)

if search_query.strip():
    q = search_query.strip().lower()
    display_items = [
        it for it in items
        if q in it["name"].lower() or q in (it.get("barcode") or "").lower()
    ]
    st.caption(f"Showing {len(display_items)} of {len(items)} lines matching \"{search_query.strip()}\"")
else:
    display_items = items

if not items:
    st.info("No returns logged yet. Add your first item above.")
elif not display_items:
    st.info(f"No items match \"{search_query.strip()}\".")
else:
    for item in display_items:
        with st.container(border=True):
            c_photo, c_name, c_qty, c_save, c_init, c_upd, c_del = st.columns(
                [0.7, 2.6, 1.1, 0.9, 1.5, 1.5, 0.6]
            )
            with c_photo:
                b64 = core.photo_base64(item)
                if b64:
                    st.markdown(
                        f'''
                        <div class="inv-thumb-wrap">
                            <img class="inv-thumb-small" src="{b64}">
                            <img class="inv-thumb-zoom" src="{b64}">
                        </div>
                        ''',
                        unsafe_allow_html=True,
                    )
                else:
                    st.write("—")
            with c_name:
                st.markdown(f"**{item['name']}**")
                if item.get("barcode"):
                    st.markdown(
                        f'<span class="barcode-pill">{item["barcode"]}</span>',
                        unsafe_allow_html=True,
                    )
                if item.get("notes"):
                    st.caption(f"📝 {item['notes']}")
            with c_qty:
                new_qty = st.number_input(
                    "Qty",
                    min_value=0,
                    step=1,
                    value=item["qty"],
                    key=f"qty_{item['id']}_{item['qty']}",
                    label_visibility="collapsed",
                )
            with c_save:
                if st.button("Update", key=f"upd_{item['id']}"):
                    if int(new_qty) != item["qty"]:
                        core.update_item(
                            item["id"],
                            qty=int(new_qty),
                            update_date=date.today().isoformat(),
                        )
                        data_cache.invalidate()
                        st.rerun()
            with c_init:
                st.caption("Initial Entry")
                st.write(item["initial_date"])
            with c_upd:
                st.caption("Updated")
                st.write(item["update_date"])
            with c_del:
                if st.button("🗑️", key=f"del_{item['id']}", help="Delete this item"):
                    core.delete_item(item["id"])
                    data_cache.invalidate()
                    st.rerun()

            with st.expander("📝 Add/edit note" if not item.get("notes") else "📝 Edit note"):
                note_key = f"note_edit_{item['id']}"
                edited_note = st.text_input(
                    "Note", value=item.get("notes") or "", key=note_key, label_visibility="collapsed",
                    placeholder="e.g. Package shows qty 2, only 1 sellable",
                )
                if st.button("Save note", key=f"save_note_{item['id']}"):
                    core.update_item(item["id"], notes=edited_note.strip())
                    data_cache.invalidate()
                    st.rerun()

# ---------- Diagnostics ----------
st.write("")
with st.expander("🔧 Diagnostics"):
    st.caption(
        "Self-service checks for when something's not working — check this "
        "before digging through Streamlit Cloud's separate log viewer."
    )

    d1, d2, d3 = st.columns(3)
    with d1:
        st.metric("Database", "Shared" if core.is_shared_database() else "⚠️ Local only")
    with d2:
        st.metric("OCR (Tesseract)", "Available" if core.tesseract_available() else "Not installed")
    with d3:
        st.metric("Items in database", len(items))

    if not core.is_shared_database():
        st.warning(
            "Running on local storage, not the shared database — see the warning "
            "banner at the top of the page for how to fix this."
        )

    st.caption(
        "Recent activity log (shared across everyone currently using this app — "
        "resets when the app restarts):"
    )
    logs = recent_logs(100)
    if logs:
        st.code("\n".join(logs), language=None)
    else:
        st.caption("No log activity yet this session.")
