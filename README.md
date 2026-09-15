# Return Inventory — Portable Package

Copy this whole folder to any computer (Mac or Windows) and follow the
steps below once. After that, it's a double-click to launch.

## First-time setup on a new computer

You need Python 3 installed first. Check by opening Terminal (Mac) or
Command Prompt (Windows) and typing `python3 --version` (Mac) or
`python --version` (Windows). If nothing shows up, install it free from
https://python.org — on Windows, check "Add Python to PATH" during
install.

**On Mac:**
1. Double-click `setup.command`.
2. If macOS says it can't verify the developer: right-click
   `setup.command` → **Open** → click **Open** again in the dialog. You
   only need to do this once — after that, plain double-clicking works.
3. Wait for it to say "Setup complete."

**On Windows:**
1. Double-click `setup.bat`.
2. If Windows SmartScreen warns you, click **More info** → **Run anyway**.
3. Wait for it to say "Setup complete."

This creates a private `.venv` folder inside this package with everything
the app needs — it doesn't touch or affect any other Python software on
your computer.

## Launching the app (every time after setup)

- **Mac:** double-click `run.command`
- **Windows:** double-click `run.bat`

Your browser opens automatically to the app. To stop it, close that
Terminal/Command Prompt window (or press Ctrl+C inside it).

## Your data

Everything you enter is stored locally in this same folder:

- `inventory.db` — item details (SQLite database)
- `photos/` — the photos you upload

These are created automatically the first time you add an item. **They
are not automatically synced between computers** — if you set this up on
two machines, each one keeps its own separate inventory. To move your
data from one computer to another, copy `inventory.db` and the `photos/`
folder into the same package folder on the other machine (with the app
closed).

## Scanning barcodes

The **Add Inventory** section has two tabs:

- **📷 Scan Barcode** — opens your camera, decodes the barcode (UPC/EAN/Code128/
  QR all work), and fills in the Product Name automatically, trying each of
  these in order:
  1. **Remembered locally** — if you've scanned this barcode before, its name
     comes straight from this app's own memory.
  2. **Looked up online** — if not, it checks a free public UPC/EAN database
     over the internet. No signup needed for normal personal use.
  3. **Read from a photo (OCR)** — if that also comes up empty, you'll be
     asked to snap a photo of the product, and the app tries to read the
     name off the packaging. This needs Tesseract OCR installed (see below);
     without it, this step is skipped automatically.
  4. **Typed in by hand** — the final fallback, same as before. Whatever name
     you save with becomes the "remembered" answer for next time (step 1).

  The date is set to today automatically, and there's an optional photo
  capture built into the same flow either way.
- **✏️ Manual Entry** — the original form (photo, name, quantity, custom
  dates), with an optional barcode field if you want to link one by hand.

### Setting up OCR (optional)

Reading a product name off a photo needs the free Tesseract OCR engine
installed on your computer — separate from the Python packages, since it's
not something `pip` can install by itself.

**Mac:**
```
brew install tesseract
```

**Windows:** download and run the installer from
https://github.com/UB-Mannheim/tesseract/wiki, and make sure "Add to PATH"
is checked during install.

If Tesseract isn't installed, the app just skips straight to asking you to
type the name — nothing breaks.

### Using your phone's camera

Browsers only allow camera access on a page opened as `localhost`, or one
served over **HTTPS**. This matters because of *how* you open the app:

- **On the same computer running the app:** works out of the box — `run.command`
  / `run.bat` opens `http://localhost:8501`, which browsers treat as secure.
- **On your phone, pointed at your computer's app** (e.g.
  `http://192.168.1.23:8501`): the browser will block camera access, because
  that address is plain HTTP.

**On Mac, the easiest fix is `run-with-phone.command`** — double-click it
instead of `run.command`. It starts the app *and* a secure [ngrok](https://ngrok.com)
tunnel together, then prints an `https://...` address to open on your phone.

One-time setup for that script:
```
brew install ngrok
```
Then sign up free at https://dashboard.ngrok.com/signup, copy your authtoken
from the dashboard, and run once:
```
ngrok config add-authtoken YOUR_TOKEN
```
After that, `run-with-phone.command` just works every time — no separate
`run.command` needed on days you want to scan from your phone.

(On Windows, or if you'd rather not use ngrok: Tailscale Serve/Funnel is
another good option, or a self-signed cert with Streamlit's
`--server.sslCertFile` / `--server.sslKeyFile` flags — your phone's browser
will show a one-time "not secure" warning to click through with that route.)

If the camera tab shows a "couldn't start the camera" message, this is
almost always the cause. The **Manual Entry** tab always works regardless,
including typing in a barcode by hand.

## Exporting to Excel

Click **Export to Excel (photos embedded)** at the top of the Inventory
list — it downloads a `.xlsx` file with every photo embedded directly in
its row.

## Moving this package to another computer

Copy the whole folder — **except** the `.venv` folder, which is specific
to each computer and gets recreated by running setup again. Everything
else (including your data, if you want to bring it along) can travel
with the folder.

## Sharing this with someone else (free, real-time shared inventory)

By default, this app runs entirely on your own computer with its own
private data — great for solo use, but your partner running their own copy
would see a completely separate, empty inventory.

To actually share one live inventory with someone else, for free:

### 1. Put the code on GitHub (you've likely already done this)

### 2. Create a free database (Supabase)

1. Sign up free at https://supabase.com
2. Create a new project (pick any name/password — save the password
   somewhere, you'll need it once)
3. Go to **Project Settings → Database → Connection string**, choose the
   **URI** tab, and copy it. It looks like:
   `postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxxxxx.supabase.co:5432/postgres`
4. Paste in your actual password where it says `[YOUR-PASSWORD]`

Supabase's free tier comfortably holds a couple hundred inventory rows with
photos.

### 3. Deploy the app (Streamlit Community Cloud)

1. Sign up free at https://share.streamlit.io with your GitHub account
2. Click **New app**, pick your `amazon_return_inventory` repo, branch
   `main`, main file `app.py`
3. Before clicking Deploy, open **Advanced settings → Secrets** and paste:
   ```
   DATABASE_URL = "postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxxxxxxx.supabase.co:5432/postgres"
   ```
   (your actual connection string from step 2 — keep the quotes)
4. Click **Deploy**

You'll get a URL like `https://your-app-name.streamlit.app` — that's the
one address you and your partner both use from now on, including on phones
(it's HTTPS automatically, so barcode/photo camera scanning works there
too — no ngrok needed for the shared version).

### 4. (Recommended) Make it private to just the two of you

By default anyone with the link can open a Community Cloud app. To
restrict it: on your app's page on share.streamlit.io, go to **Settings →
Sharing**, switch it to **Only specific people can view this app**, and
add your email and your partner's. You'll each sign in with that email
(via a free Streamlit/Google login prompt) the first time you visit.

### Notes on the shared setup

- Both of you will see the same items, quantities, and photos update in
  real time — there's one shared database now, not two separate ones.
- Barcode scanning and photo capture work the same as locally — actually
  more reliably, since the deployed URL is HTTPS by default (no ngrok
  needed for the shared version, on either of your phones).
- OCR (reading names off photos) also works on the deployed version with
  no extra steps — this package includes a `packages.txt` file that tells
  Streamlit Community Cloud to install Tesseract automatically during
  deployment. You don't need to `brew install` anything for the shared app.
- Your local copy on this iMac still works exactly as before if you ever
  run it standalone (`run.command`) — it just uses its own local file
  instead of the shared database, since `DATABASE_URL` is only set for the
  deployed version.
- If you ever want to see the raw shared data outside the app, Supabase's
  dashboard has a **Table Editor** where you can browse everything.

