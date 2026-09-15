"""
Core storage + export logic for the Return Inventory Streamlit app.
Kept separate from app.py so it can be tested without launching Streamlit.

Works in two modes, picked automatically:
  - Local (default): a SQLite file in this folder. No setup needed.
  - Shared: set a DATABASE_URL (Postgres, e.g. a free Supabase project) in
    Streamlit secrets or the environment, and every user hitting the same
    deployed app shares one live database instead.
Photos are stored as blobs directly in the database (not local files), so
a single database file/connection is the whole app's data - nothing else
to keep in sync between computers.
"""

from __future__ import annotations

import os
import uuid
from datetime import date, datetime
from io import BytesIO
from pathlib import Path

from PIL import Image
import openpyxl
from openpyxl.drawing.image import Image as XLImage
from openpyxl.styles import Alignment, Font
from sqlalchemy import create_engine, text, inspect

from applog import get_logger

log = get_logger()

BASE_DIR = Path(__file__).parent
LOCAL_DB_PATH = BASE_DIR / "inventory.db"
# Old versions of this app stored photos as files here instead of in the
# database. Kept only so photos added before this upgrade keep displaying;
# every photo added from now on is stored as a blob in the database instead.
LEGACY_PHOTOS_DIR = BASE_DIR / "photos"

THUMB_MAX_DIM = 640  # px, stored photo size (kept sharp for hover-zoom + Excel)


def _redact_url(url: str) -> str:
    """Password-safe version of a connection string, for logging."""
    if "@" not in url or "://" not in url:
        return url
    scheme, rest = url.split("://", 1)
    creds_and_host = rest.split("@", 1)
    if len(creds_and_host) != 2:
        return url
    creds, host = creds_and_host
    user = creds.split(":", 1)[0] if ":" in creds else creds
    return f"{scheme}://{user}:***@{host}"


def _database_url() -> str:
    """
    Shared/cloud mode: read DATABASE_URL from Streamlit secrets (when
    deployed) or the environment (e.g. a local .env / shell export).
    Falls back to a local SQLite file when neither is set, so this keeps
    working unmodified for solo local use.
    """
    url = os.environ.get("DATABASE_URL")
    source = "environment variable" if url else None
    if not url:
        try:
            import streamlit as st
            url = st.secrets.get("DATABASE_URL")
            source = "Streamlit secrets" if url else None
        except Exception as e:
            log.warning(f"Could not read Streamlit secrets (this is normal for local runs): {e}")
            url = None
    if not url:
        log.warning(
            "No DATABASE_URL found in environment or Streamlit secrets - "
            f"falling back to local SQLite at {LOCAL_DB_PATH}. If this is the "
            "deployed app and that's unexpected, check the app's Secrets."
        )
        return f"sqlite:///{LOCAL_DB_PATH}"
    # Some providers (incl. Supabase) hand out "postgres://" URLs; SQLAlchemy
    # needs the "postgresql://" scheme.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    log.info(f"Using DATABASE_URL from {source}: {_redact_url(url)}")
    return url


engine = create_engine(_database_url(), pool_pre_ping=True)

try:
    with engine.connect() as _test_conn:
        pass
    log.info(f"Database connection OK (dialect: {engine.dialect.name})")
except Exception as e:
    log.error(f"Database connection FAILED at startup: {e}")


def is_shared_database() -> bool:
    """True when connected to the shared Postgres database (DATABASE_URL is
    set and valid), False when silently running on the local SQLite file."""
    return engine.dialect.name != "sqlite"


def init_db():
    with engine.begin() as conn:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                qty INTEGER NOT NULL,
                initial_date TEXT NOT NULL,
                update_date TEXT NOT NULL,
                photo_path TEXT,
                created_at TEXT NOT NULL,
                barcode TEXT,
                photo_data BYTEA
            )
            """ if engine.dialect.name != "sqlite" else
            """
            CREATE TABLE IF NOT EXISTS items (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                qty INTEGER NOT NULL,
                initial_date TEXT NOT NULL,
                update_date TEXT NOT NULL,
                photo_path TEXT,
                created_at TEXT NOT NULL,
                barcode TEXT,
                photo_data BLOB
            )
            """
        ))
        # Remembers barcode -> product name, so a barcode only needs to be
        # typed in once; every scan after that auto-fills the name.
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS barcode_map (
                barcode TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        ))

    # Lightweight migration for databases created before barcode scanning /
    # in-database photos existed. Uses SQLAlchemy's inspector so this works
    # the same way on SQLite and Postgres.
    inspector = inspect(engine)
    existing_cols = {c["name"] for c in inspector.get_columns("items")}
    with engine.begin() as conn:
        if "barcode" not in existing_cols:
            log.info("Migrating: adding 'barcode' column to items table")
            conn.execute(text("ALTER TABLE items ADD COLUMN barcode TEXT"))
        if "photo_data" not in existing_cols:
            blob_type = "BYTEA" if engine.dialect.name != "sqlite" else "BLOB"
            log.info(f"Migrating: adding 'photo_data' ({blob_type}) column to items table")
            conn.execute(text(f"ALTER TABLE items ADD COLUMN photo_data {blob_type}"))
        if "notes" not in existing_cols:
            log.info("Migrating: adding 'notes' column to items table")
            conn.execute(text("ALTER TABLE items ADD COLUMN notes TEXT"))


def _process_photo(uploaded_file) -> bytes | None:
    """Resize an uploaded image and return it as JPEG bytes, ready to store."""
    if uploaded_file is None:
        return None
    img = Image.open(uploaded_file).convert("RGB")
    w, h = img.size
    if max(w, h) > THUMB_MAX_DIM:
        if w >= h:
            new_w, new_h = THUMB_MAX_DIM, round(h * THUMB_MAX_DIM / w)
        else:
            new_h, new_w = THUMB_MAX_DIM, round(w * THUMB_MAX_DIM / h)
        img = img.resize((new_w, new_h), Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


def add_item(
    name: str,
    qty: int,
    initial_date: str,
    update_date: str,
    uploaded_file,
    barcode: str | None = None,
    notes: str | None = None,
) -> str:
    item_id = str(uuid.uuid4())
    try:
        photo_bytes = _process_photo(uploaded_file)
    except Exception as e:
        log.error(f"Failed to process photo for new item '{name}': {e}")
        photo_bytes = None

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO items (id, name, qty, initial_date, update_date, "
                    "photo_data, created_at, barcode, notes) "
                    "VALUES (:id, :name, :qty, :initial_date, :update_date, "
                    ":photo_data, :created_at, :barcode, :notes)"
                ),
                {
                    "id": item_id,
                    "name": name,
                    "qty": qty,
                    "initial_date": initial_date,
                    "update_date": update_date,
                    "photo_data": photo_bytes,
                    "created_at": datetime.utcnow().isoformat(),
                    "barcode": barcode,
                    "notes": notes,
                },
            )
        log.info(
            f"Added item '{name}' (qty={qty}, barcode={barcode or 'none'}, "
            f"photo={'yes' if photo_bytes else 'no'}, notes={'yes' if notes else 'no'}) id={item_id}"
        )
    except Exception as e:
        log.error(f"Failed to save new item '{name}': {e}")
        raise
    return item_id


def lookup_barcode(barcode: str) -> str | None:
    """Return the remembered product name for a barcode, or None if it's new."""
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT name FROM barcode_map WHERE barcode = :barcode"),
            {"barcode": barcode},
        ).fetchone()
    return row[0] if row else None


def save_barcode_mapping(barcode: str, name: str):
    """Remember (or update) which product name a barcode corresponds to."""
    today = date.today().isoformat()
    try:
        with engine.begin() as conn:
            result = conn.execute(
                text("UPDATE barcode_map SET name = :name, updated_at = :today WHERE barcode = :barcode"),
                {"name": name, "today": today, "barcode": barcode},
            )
            if result.rowcount == 0:
                conn.execute(
                    text("INSERT INTO barcode_map (barcode, name, updated_at) VALUES (:barcode, :name, :today)"),
                    {"barcode": barcode, "name": name, "today": today},
                )
        log.info(f"Remembered barcode {barcode} -> '{name}'")
    except Exception as e:
        log.error(f"Failed to save barcode mapping {barcode} -> '{name}': {e}")
        raise


def lookup_product_name_online(barcode: str) -> str | None:
    """
    Look up a barcode against a free public UPC/EAN database (no API key
    required for light personal use). Returns a product name, or None if
    there's no match, no internet, or anything else goes wrong - callers
    should treat None as "fall through to the next option", not an error.
    """
    try:
        import requests
    except ImportError:
        log.warning("'requests' package not available - skipping online barcode lookup")
        return None

    try:
        resp = requests.get(
            "https://api.upcitemdb.com/prod/trial/lookup",
            params={"upc": barcode},
            timeout=5,
        )
        if resp.status_code != 200:
            log.warning(
                f"Online lookup for {barcode} returned HTTP {resp.status_code} "
                f"(often a rate limit on the free trial endpoint)"
            )
            return None
        data = resp.json()
        items = data.get("items") or []
        if not items:
            log.info(f"Online lookup for {barcode}: no match found")
            return None
        title = (items[0].get("title") or "").strip()
        if title:
            log.info(f"Online lookup for {barcode}: found '{title}'")
        return title or None
    except Exception as e:
        log.warning(f"Online lookup for {barcode} failed: {e}")
        return None


def tesseract_available() -> bool:
    """Whether the Tesseract OCR engine is installed and reachable."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception as e:
        log.info(f"Tesseract OCR not available: {e}")
        return False


def read_name_from_photo(uploaded_file) -> str | None:
    """
    Best-effort OCR guess at a product name from a photo. This is a
    starting suggestion for the user to confirm/edit, not a reliable
    reader - packaging fonts and angles vary a lot. Returns None if
    Tesseract isn't installed or nothing readable was found.
    Leaves the file's read position reset to 0 so it can be reused
    afterwards (e.g. saved as the item's photo).
    """
    try:
        import pytesseract
    except ImportError:
        return None

    try:
        uploaded_file.seek(0)
        img = Image.open(uploaded_file)
        text_out = pytesseract.image_to_string(img)
    except Exception as e:
        log.warning(f"OCR failed to read photo: {e}")
        return None
    finally:
        try:
            uploaded_file.seek(0)
        except Exception:
            pass

    lines = [ln.strip() for ln in text_out.splitlines() if ln.strip()]
    # Heuristic: the longest mostly-alphabetic line is usually the
    # brand/product name printed largest on the packaging.
    candidates = [ln for ln in lines if sum(c.isalpha() for c in ln) >= 3]
    if not candidates:
        log.info("OCR found no readable text on photo")
        return None
    best = max(candidates, key=len)
    log.info(f"OCR guessed product name: '{best[:80]}'")
    return best[:80]


def _normalize_row(row: dict) -> dict:
    """
    Postgres (via psycopg2) returns BYTEA columns as memoryview objects,
    not plain bytes - SQLite returns plain bytes already. memoryview isn't
    picklable, which breaks st.cache_data, and is generally less convenient
    to work with than bytes everywhere else in the app. Normalize once,
    here, rather than scattering bytes(...) conversions at every call site.
    """
    if row.get("photo_data") is not None:
        row["photo_data"] = bytes(row["photo_data"])
    return row


def get_items():
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM items ORDER BY created_at DESC")
        ).mappings().all()
    return [_normalize_row(dict(r)) for r in rows]


def find_items_by_barcode(barcode: str):
    """All existing inventory rows that share this barcode, most recent first."""
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM items WHERE barcode = :barcode ORDER BY created_at DESC"),
            {"barcode": barcode},
        ).mappings().all()
    return [_normalize_row(dict(r)) for r in rows]


def update_item(item_id: str, qty: int = None, update_date: str = None, uploaded_file=None, notes: str = None):
    """Update an existing item's quantity, update_date, photo, and/or notes."""
    fields, values = [], {"id": item_id}
    if qty is not None:
        fields.append("qty = :qty")
        values["qty"] = qty
    if update_date is not None:
        fields.append("update_date = :update_date")
        values["update_date"] = update_date
    if uploaded_file is not None:
        try:
            photo_bytes = _process_photo(uploaded_file)
        except Exception as e:
            log.error(f"Failed to process photo while updating item {item_id}: {e}")
            photo_bytes = None
        if photo_bytes is not None:
            fields.append("photo_data = :photo_data")
            values["photo_data"] = photo_bytes
    if notes is not None:
        fields.append("notes = :notes")
        values["notes"] = notes
    if not fields:
        return

    try:
        with engine.begin() as conn:
            conn.execute(text(f"UPDATE items SET {', '.join(fields)} WHERE id = :id"), values)
        log.info(f"Updated item {item_id}: {', '.join(fields)}")
    except Exception as e:
        log.error(f"Failed to update item {item_id}: {e}")
        raise


def delete_item(item_id: str):
    try:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM items WHERE id = :id"), {"id": item_id})
        log.info(f"Deleted item {item_id}")
    except Exception as e:
        log.error(f"Failed to delete item {item_id}: {e}")
        raise


def photo_base64(item: dict) -> str | None:
    """Return a data: URI for a stored photo, for embedding in custom HTML."""
    import base64
    data = item.get("photo_data")
    if data:
        return "data:image/jpeg;base64," + base64.b64encode(bytes(data)).decode()
    # Fall back to a pre-upgrade, file-based photo if this item has one.
    legacy_path = item.get("photo_path")
    if legacy_path:
        full_path = LEGACY_PHOTOS_DIR / legacy_path
        if full_path.exists():
            return "data:image/jpeg;base64," + base64.b64encode(full_path.read_bytes()).decode()
    return None


HEADERS = ["Photo", "Product Name", "Quantity", "Initial Entry Date", "Update Date", "Barcode", "Notes"]
COL_WIDTHS = {"A": 9, "B": 42, "C": 11, "D": 19, "E": 15, "F": 16, "G": 36}
ROW_HEIGHT = 42
IMG_PX = 55


def build_excel_bytes(items) -> bytes:
    """Build an .xlsx (as bytes) with each item's photo embedded in its row."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Return Inventory"

    ws.append(HEADERS)
    for cell in ws[1]:
        cell.font = Font(bold=True, name="Arial")
        cell.alignment = Alignment(vertical="center")
    for col, width in COL_WIDTHS.items():
        ws.column_dimensions[col].width = width

    row = 2
    for item in items:
        ws.row_dimensions[row].height = ROW_HEIGHT

        if item.get("photo_data"):
            xl_img = XLImage(BytesIO(bytes(item["photo_data"])))
            xl_img.width = IMG_PX
            xl_img.height = IMG_PX
            ws.add_image(xl_img, f"A{row}")
        elif item.get("photo_path"):
            legacy_path = LEGACY_PHOTOS_DIR / item["photo_path"]
            if legacy_path.exists():
                xl_img = XLImage(str(legacy_path))
                xl_img.width = IMG_PX
                xl_img.height = IMG_PX
                ws.add_image(xl_img, f"A{row}")

        ws.cell(row=row, column=2, value=item.get("name", ""))
        ws.cell(row=row, column=3, value=item.get("qty", 0))
        ws.cell(row=row, column=4, value=item.get("initial_date", ""))
        ws.cell(row=row, column=5, value=item.get("update_date", ""))
        ws.cell(row=row, column=6, value=item.get("barcode") or "")
        ws.cell(row=row, column=7, value=item.get("notes") or "")

        for col in range(2, 8):
            cell = ws.cell(row=row, column=col)
            cell.font = Font(name="Arial")
            cell.alignment = Alignment(vertical="center", wrap_text=(col == 7))

        row += 1

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
