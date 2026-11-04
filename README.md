# Bete Dires (ቤተ ድረስ) Marketplace Suite

Modern, full-stack, multilingual Telegram marketplace system rebranded from "Gonder Gebeya" to **Bete Dires (ቤተ ድረስ)**. Built for high reliability, low-resource hosting (single small VPS), and fast bilingual search (Amharic & English).

---

## 🏛 System Architecture

The system consists of three coordinated components sharing an atomic SQLite database (`betedires.db`):

```
                        ┌───────────────────────────────┐
                        │    Bete Dires Hub & 7 Channels│
                        │    Main, Cosmetics, Tech, etc.│
                        └───────────────▲───────────────┘
                                        │
           ┌────────────────────────────┼────────────────────────────┐
           │ (Dual Publish & Captions)  │ (Auto-Forward & Watermark) │ (Live Post Links)
           │                            │                            │
┌──────────┴──────────┐      ┌──────────┴──────────┐      ┌──────────┴──────────┐
│  FastAPI Dashboard  │      │  Telethon Forwarder │      │   aiogram 3 Bot     │
│  (main.py: 127.0.0.1)│     │(telegram_forwarder/)│      │ (bot.py - Buyers &  │
│  • Moderation queue │      │ • Monitors source grps│    │   Sellers)          │
│  • Inline editor    │      │ • SHA-256 deduplicat│      │ • FTS5 bilingual srch│
│  • Dual-channel pub │      │ • Confidence filter │      │ • Category browsing │
│  • Seller verify    │      │ • Watermark overlay │      │ • Search alerts     │
│  • Reports queue    │      │ • Atomic serial seq │      │ • Seller verify flow│
│  • Online DB backup │      │ • PARTIALLY_POSTED  │      │ • Self-sold marking │
└──────────┬──────────┘      └──────────┬──────────┘      └──────────┬──────────┘
           │                            │                            │
           └────────────────────────────┼────────────────────────────┘
                                        ▼
                         ┌─────────────────────────────┐
                         │      betedires.db (SQLite)  │
                         │  • items & items_fts (FTS5) │
                         │  • sellers & reports        │
                         │  • user_preferences         │
                         │  • search_alerts            │
                         └─────────────────────────────┘
```

### 1. FastAPI Admin Dashboard (`main.py`)
- **Authentication & Security:** Bound to `127.0.0.1` by default. Password verification using salted HMAC-SHA256, HTTP-only session cookies, and HMAC-signed CSRF tokens on all state-changing POST actions.
- **Moderation Workflow:** Pending, Scheduled, Posted, Partially Posted, and Sold queues.
- **Dual-Channel Publishing:** Automatically renders watermarked media albums and posts simultaneously to the main hub channel and the specific category channel.
- **Reliability & Retry Engine:** Exponential backoff on Telegram `FloodWait` (up to 60s cap). If category channel fails while main succeeds, item is safely flagged as `PARTIALLY_POSTED` with an instant "Retry" button.
- **Trust & Verification:** Integrated Seller Verification center (`/admin/verifications`) with encrypted/isolated ID document viewer (`/admin/id_photo/{filename}`) and Listing Report resolution (`/admin/reports`).
- **Real-time Analytics:** Category breakdown counts, conversion sold rate percentage, active sellers count, and buyer search alerts count.
- **Automated Backup & Cleanup:** Idempotent background expiry cleanup worker and online daily SQLite backup worker (`run_sqlite_backup()`).

### 2. Buyer Search & Seller Bot (`bot.py`)
- **Bilingual Interface:** Full Amharic and English support with persistent language preference storage (`user_preferences` table).
- **SQLite FTS5 Free-Text Search:** Natural language search queries (e.g. `iphone xr 20000 Gondar`). Normalizes Amharic numerals (`20 ሺ` -> `20,000`), city variants (`ጎንደር` / `Gondar`), and cross-lingual synonyms.
- **Exact Serial Lookup:** Typing serial numbers like `050 EL 015` or `043 FU 14` retrieves the exact listing card with a direct link to the live Telegram post.
- **"Notify Me" Search Alerts:** Buyers can save any search to receive automated instant DM notifications when a matching listing is posted.
- **Seller Self-Service:** Sellers can mark their own items as SOLD directly from the bot (`mysold:<id>`), securely authenticated by Telegram User ID.
- **Stale Listing Prevention:** Pre-expiry availability alerts prompt sellers on Day 6 of 7 with "Still Available" / "Mark as Sold" buttons.

### 3. Telethon Userbot Forwarder (`telegram_forwarder/`)
- **Deduplication:** SHA-256 content hash of normalized Amharic text + raw image bytes prevents reposting identical listings.
- **Confidence Filter:** Missing price or phone flags listings as `PENDING` for dashboard review instead of auto-posting. Configurable `CONFIDENCE_MODE` (`strict` / `relaxed`).
- **Watermark Engine:** Applies a high-contrast scaled PNG watermark or crisp outlined text overlay.
- **Source Attribution:** Retains source chat ID, message ID, and clickable direct link (`source_link`) in the DB.
- **Catchup Recovery:** Replays missed messages on startup (`last_message_id.txt`) without double-posting.

---

## 🏷 Serial Number Format

Every item receives an atomic serial number adhering to the standard:

```
[Global ID] [Category Code] [Category Seq]
   050            EL              015
```

- **Global ID:** 3-digit padded primary key.
- **Category Codes:**
  - `CO` — Cosmetics (ኮስሞቲክስ)
  - `EL` — Electronics (ኤሌክትሮኒክስ)
  - `VE` — Vehicles (መኪና)
  - `FU` — Furniture (ፈርኒቸር)
  - `CL` — Clothing (ልብስ እና ጫማ)
  - `HR` — House/Rent (ቤት እና ኪራይ)
  - `OT` — Others (የተለያዩ እቃዎች)
- **Category Seq:** Guaranteed atomic `MAX(category_id_seq) + 1` inside an ACID transaction with a database `UNIQUE(category, category_id_seq)` constraint.

---

## 🚀 Quick Start & Installation

### Prerequisites
- Python 3.10+ (tested on Python 3.11 / 3.12)
- Virtual environment (`venv`)

### 1. Clone & Setup Virtual Environment
```bash
git clone <repository_url> betedires
cd betedires

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
.\venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables
Copy `.env.example` to `.env` in the root directory:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```ini
# Brand
BRAND_NAME=Bete Dires (ቤተ ድረስ)
BRAND_HASHTAG=#BeteDires
WATERMARK_TEXT=Bete Dires

# Telegram Bot
BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
ADMIN_USERNAME=@BeteDires_admin

# Channels (Use @username or -100xxxxxxxxxx chat IDs)
CHANNEL_ID=@BeteDires_Main
CHANNEL_COSMETICS=@BeteDires_Cosmetics
CHANNEL_ELECTRONICS=@BeteDires_Electronics
CHANNEL_FURNITURE=@BeteDires_Furniture
CHANNEL_CLOTHING=@BeteDires_Clothing
CHANNEL_VEHICLES=@BeteDires_Vehicles
CHANNEL_HOUSE=@BeteDires_House
CHANNEL_OTHERS=@BeteDires_Others

# Dashboard Security
ADMIN_PASSWORD=your_secure_password_here
SESSION_SECRET=generate_a_random_32_character_hex_string_here
SERVER_HOST=127.0.0.1
SERVER_PORT=8000
```

Configure `telegram_forwarder/.env` for Telethon:
```ini
API_ID=your_telethon_api_id
API_HASH=your_telethon_api_hash
SOURCE_GROUPS=@source_group_1,@source_group_2
TARGET_GROUP=@BeteDires_Main
CONFIDENCE_MODE=strict
ENABLE_CATCHUP=true
```

---

## 🏃 Running the Applications

### 1. Start Admin Dashboard (FastAPI) & aiogram Bot
The aiogram bot runs concurrently inside the dashboard lifespan:
```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```
Open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your browser and log in with `ADMIN_PASSWORD`.

### 2. Start Telethon Forwarder (Optional / In Background)
```bash
python telegram_forwarder/run.py
```

---

## 💾 SQLite Backup & Disaster Recovery

### Automatic Backups
- The dashboard runs a background backup worker that takes a daily snapshot using the safe `sqlite3.backup` API (safe while database is open and processing transactions).
- Snapshots are saved to `backups/betedires_backup_YYYYMMDD_HHMMSS.db`.
- Automatic rotation maintains the newest 14 backups.

### 1-Click Dashboard Backup
Admins can click **"Create SQLite Backup"** in the dashboard maintenance bar to take an immediate snapshot before making major changes.

### CLI Backup
```bash
python backup.py --keep 14
```

### CLI Restore
```bash
# Restore from the latest available backup
python restore.py --latest

# Or restore from a specific file
python restore.py --from-file backups/betedires_backup_20261014_160713.db
```
*Note: `restore.py` automatically creates a safety `.pre_restore` copy of the current database before replacing it.*

---

## 🛡 Security & Privacy

1. **Dashboard Isolation:** Bound to `127.0.0.1` by default. Use an Nginx/Caddy reverse proxy with SSL (`https://`) when deploying remotely.
2. **Session Cookies:** Signed with HMAC-SHA256, HTTP-only, `SameSite=Lax`.
3. **CSRF Protection:** State-changing endpoints (`/action/*`) require a valid session-bound CSRF token.
4. **ID Document Security:** Seller ID verification photos are stored in `secure_uploads/ids/` (outside public web paths) and can only be viewed by authenticated admins via `/admin/id_photo/{filename}`.
5. **Magic Byte Validation:** File uploads are validated by header signature bytes (JPEG, PNG, WebP) rather than just file extensions.

---

## 📦 Single VPS Deployment (Linux / Ubuntu)

### Systemd Service for Dashboard (`/etc/systemd/system/betedires.service`)
```ini
[Unit]
Description=Bete Dires Dashboard & Bot
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/betedires
ExecStart=/var/www/betedires/venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=5
Environment=PATH=/var/www/betedires/venv/bin

[Install]
WantedBy=multi-user.target
```

### Systemd Service for Forwarder (`/etc/systemd/system/betedires-forwarder.service`)
```ini
[Unit]
Description=Bete Dires Telethon Forwarder
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/betedires/telegram_forwarder
ExecStart=/var/www/betedires/venv/bin/python run.py
Restart=always
RestartSec=10
Environment=PATH=/var/www/betedires/venv/bin

[Install]
WantedBy=multi-user.target
```

---

## 💳 Payment Gateway & Escrow (Telebirr / CBE Birr)

Payments and escrow are designed with a clean plug-in architecture in `payments.py`:
- `PaymentGateway.create_checkout_session()`
- `PaymentGateway.verify_payment_callback()`
- `PaymentGateway.release_escrow_to_seller()`
- `PaymentGateway.refund_buyer()`

When online payments are activated, insert provider API keys (`TELEBIRR_APP_ID`, `CBE_BIRR_API_KEY`) into `.env` and wire the callback endpoints in `payments.py`.

---

## 🧪 Testing Suite

Execute all verification test suites:
```bash
python test_step2.py   # Config, Rebrand, Auth, Cosmetics
python test_step3.py   # Reliability, Retries, Health, Expiry
python test_step4.py   # FTS5 Search, Bilingual Normalization
python test_step5.py   # Trust, Seller Verification, Reports
python test_step6.py   # Forwarder Deduplication & Quality
python test_step7.py   # Dashboard Security, Stats & Backups
```
