import streamlit as st
from datetime import date

import inventory_core as core
from barcode_scanner import scan_barcode

st.set_page_config(page_title="Return Inventory", page_icon="📦", layout="wide")
core.init_db()

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

# ---------- Add item ----------
if "scan_key" not in st.session_state:
    st.session_state.scan_key = 0
if "pending_barcode" not in st.session_state:
    st.session_state.pending_barcode = None
if "camera_active" not in st.session_state:
    st.session_state.camera_active = False

with st.container(border=True):
    st.markdown('<p class="section-label">Add Inventory</p>', unsafe_allow_html=True)
    tab_scan, tab_manual = st.tabs(["📷 Scan Barcode", "✏️ Manual Entry"])

    # ---- Scan Barcode tab ----
    with tab_scan:
        if st.session_state.pending_barcode is None:
            if not st.session_state.camera_active:
                st.caption(
                    "Camera stays off until you tap below — it needs the page opened as "
                    "**localhost** or over **HTTPS** to work at all; see the README if it "
                    "won't start on your phone."
                )
                if st.button("📷 Start Scanning", type="primary"):
                    st.session_state.camera_active = True
                    st.rerun()
            else:
                if st.button("Stop Camera"):
                    st.session_state.camera_active = False
                    st.session_state.scan_key += 1
                    st.rerun()
                scanned = scan_barcode(key=f"scanner_{st.session_state.scan_key}")
                if scanned:
                    st.session_state.pending_barcode = scanned
                    st.session_state.camera_active = False
                    st.rerun()

                with st.expander("Camera won't pick up this barcode? Type it in instead"):
                    with st.form("manual_barcode_form", clear_on_submit=True):
                        typed_barcode = st.text_input(
                            "Barcode number", placeholder="e.g. 827854027195"
                        )
                        if st.form_submit_button("Use this barcode"):
                            cleaned = typed_barcode.strip()
                            if cleaned:
                                st.session_state.pending_barcode = cleaned
                                st.session_state.camera_active = False
                                st.session_state.scan_key += 1
                                st.rerun()
        else:
            barcode = st.session_state.pending_barcode

            # Resolve a suggested name once per newly-scanned barcode, trying
            # each source in order: remembered locally -> online UPC lookup.
            # OCR (below) only kicks in if neither of those finds anything,
            # since it needs a photo the user hasn't taken yet.
            if st.session_state.get("resolved_barcode") != barcode:
                st.session_state.resolved_barcode = barcode
                st.session_state.suggested_name = None
                st.session_state.suggested_source = None
                st.session_state.ocr_photo = None

                known_name = core.lookup_barcode(barcode)
                if known_name:
                    st.session_state.suggested_name = known_name
                    st.session_state.suggested_source = "known"
                else:
                    with st.spinner("Looking up product online…"):
                        online_name = core.lookup_product_name_online(barcode)
                    if online_name:
                        st.session_state.suggested_name = online_name
                        st.session_state.suggested_source = "online"

            source = st.session_state.suggested_source
            suggested_name = st.session_state.suggested_name

            if source == "known":
                st.success(f"Recognized barcode **{barcode}** → {suggested_name}")
            elif source == "online":
                st.success(f"Found online: **{suggested_name}**")
            else:
                st.info(f"New barcode **{barcode}** — no online match found.")

            # No name yet from memory or the online lookup: offer to read it
            # off a photo before falling back to typing it in by hand.
            if source is None and st.session_state.ocr_photo is None:
                if core.tesseract_available():
                    st.caption("Take a photo of the product and I'll try to read the name off it.")
                    ocr_photo = st.camera_input("Photo for name lookup", key=f"ocr_photo_{barcode}")
                    if ocr_photo is not None:
                        st.session_state.ocr_photo = ocr_photo
                        with st.spinner("Reading text from photo…"):
                            ocr_name = core.read_name_from_photo(ocr_photo)
                        if ocr_name:
                            st.session_state.suggested_name = ocr_name
                            st.session_state.suggested_source = "ocr"
                        st.rerun()
                    st.caption("Or just type the name below and skip the photo.")
                else:
                    st.caption(
                        "Reading the name off a photo needs Tesseract OCR installed — "
                        "see the README. You can still type the name below."
                    )

            if st.session_state.suggested_source == "ocr":
                st.success(f"Read from photo: **{st.session_state.suggested_name}** (double-check this)")

            existing_items = core.find_items_by_barcode(barcode)
            merge_target = None
            add_to_existing = False
            if existing_items:
                existing_total = sum(i["qty"] for i in existing_items)
                line_word = "line" if len(existing_items) == 1 else "lines"
                st.info(
                    f"Already in inventory: **{existing_total}** unit(s) across "
                    f"{len(existing_items)} {line_word}."
                )
                merge_choice = st.radio(
                    "What would you like to do?",
                    ["Add to the most recent existing line", "Log as a new separate line"],
                    key=f"merge_choice_{barcode}",
                )
                add_to_existing = merge_choice.startswith("Add to")
                merge_target = existing_items[0]  # most recently created

            with st.form("scan_save_form", clear_on_submit=False):
                scan_name = st.text_input("Product Name", value=st.session_state.suggested_name or "")
                scan_qty = st.number_input(
                    "Quantity to add" if add_to_existing else "Quantity",
                    min_value=1, step=1, value=1,
                )
                if st.session_state.ocr_photo is not None:
                    st.image(st.session_state.ocr_photo, caption="Photo captured above", width=140)
                    scan_photo = st.session_state.ocr_photo
                else:
                    scan_photo = st.camera_input("Take a photo (optional)")
                sc1, sc2 = st.columns(2)
                with sc1:
                    save_scan = st.form_submit_button("Save item", type="primary")
                with sc2:
                    cancel_scan = st.form_submit_button("Cancel / Scan again")

            if save_scan:
                if not scan_name.strip():
                    st.error("Product name is required.")
                else:
                    today = date.today().isoformat()
                    if add_to_existing and merge_target:
                        core.update_item(
                            merge_target["id"],
                            qty=merge_target["qty"] + int(scan_qty),
                            update_date=today,
                            uploaded_file=scan_photo,
                        )
                        st.success(
                            f"Added {int(scan_qty)} — {merge_target['name']} now at "
                            f"{merge_target['qty'] + int(scan_qty)} units."
                        )
                    else:
                        core.add_item(
                            scan_name.strip(),
                            int(scan_qty),
                            today,
                            today,
                            scan_photo,
                            barcode=barcode,
                        )
                        st.success(f"Saved {int(scan_qty)} × {scan_name.strip()} as a new line.")
                    core.save_barcode_mapping(barcode, scan_name.strip())
                    st.session_state.pending_barcode = None
                    st.session_state.resolved_barcode = None
                    st.session_state.suggested_name = None
                    st.session_state.suggested_source = None
                    st.session_state.ocr_photo = None
                    st.session_state.scan_key += 1
                    st.rerun()

            if cancel_scan:
                st.session_state.pending_barcode = None
                st.session_state.resolved_barcode = None
                st.session_state.suggested_name = None
                st.session_state.suggested_source = None
                st.session_state.ocr_photo = None
                st.session_state.scan_key += 1
                st.rerun()

    # ---- Manual Entry tab ----
    with tab_manual:
        with st.form("add_item_form", clear_on_submit=True):
            col_photo, col_fields = st.columns([1, 2])

            with col_photo:
                uploaded_file = st.file_uploader(
                    "Photo", type=["jpg", "jpeg", "png", "webp"], label_visibility="visible"
                )
                if uploaded_file is not None:
                    st.image(uploaded_file, width=140)

            with col_fields:
                name = st.text_input("Product Name")
                barcode_manual = st.text_input(
                    "Barcode (optional)",
                    help="Fill this in if you want this item linked to a barcode for future scans.",
                )
                qty = st.number_input("Quantity", min_value=1, step=1, value=1)
                c1, c2 = st.columns(2)
                with c1:
                    initial_date = st.date_input("Initial Entry Date", value=date.today())
                with c2:
                    update_date = st.date_input("Update Date", value=date.today())

            submitted = st.form_submit_button("Save item", type="primary")
            if submitted:
                if not name.strip():
                    st.error("Product name is required.")
                else:
                    clean_barcode = barcode_manual.strip() or None
                    core.add_item(
                        name.strip(),
                        int(qty),
                        initial_date.isoformat(),
                        update_date.isoformat(),
                        uploaded_file,
                        barcode=clean_barcode,
                    )
                    if clean_barcode:
                        core.save_barcode_mapping(clean_barcode, name.strip())
                    st.success(f"Saved '{name.strip()}'.")
                    st.rerun()

st.write("")

# ---------- Inventory list + export ----------
items = core.get_items()
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
        excel_bytes = core.build_excel_bytes(items)
        st.download_button(
            "⬇️ Export to Excel (photos embedded)",
            data=excel_bytes,
            file_name=f"return-inventory-{date.today().isoformat()}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
        )
    else:
        st.button("⬇️ Export to Excel (photos embedded)", disabled=True)

st.write("")

if not items:
    st.info("No returns logged yet. Add your first item above.")
else:
    for item in items:
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
                    st.rerun()
