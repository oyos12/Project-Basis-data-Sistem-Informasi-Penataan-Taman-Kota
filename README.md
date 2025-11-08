# Sistem Informasi Perawatan Taman Kota #
A small full-stack project for managing city park maintenance data and generating a printable report (Word/PDF via “Print to PDF”).
It includes:
A Flask REST API backed by MySQL (app.py)
An optional SQLite Auth microservice (auth_sqlite.py)
A set of static HTML frontends (Start, Input, Output, Report) with a sticky sidebar, light/dark theme, and one-click report printing
A helper to start both services together and run the database initializer (run_both.py, init_db.py

✨ Features
CRUD for taman, petugas, kegiatan, tanaman, and laporan
Two report modes:
1. Client mode: browser assembles the report and opens a print dialog
2. Server mode: server returns prebuilt HTML (/api/report/html)
Robust report data loader (no more id_taman query param is required issues)
Clear all data endpoint (with confirmation) for a clean re-input cycle
Frontend goodies: sticky sidebar, theme toggle, consistent table layouts, and clear spacing between sections

🗂 Directory overview
project/
├─ app.py                # MySQL-backed API (port 5000)
├─ auth_sqlite.py        # Optional: SQLite auth API (port 5001)
├─ init_db.py            # Creates schema & seed data (MySQL)
├─ run_both.py           # Launches init_db + both APIs, manages output/teardown
├─ start_index.html      # Frontend: Start
├─ input_index.html      # Frontend: Input data
├─ output_index.html     # Frontend: Output tables
├─ report_index.html     # Frontend: Build/print reports, clear-all button
└─ README.md

🧰 Tech stack
Backend: Python 3.9+, Flask, flask-cors, mysql-connector-python
DB: MySQL (phpMyAdmin optional), SQLite for the auth microservice
Frontend: vanilla HTML/CSS/JS

⚙️ Setup
1) Install dependencies
python -m venv .venv
# Windows
. .venv/Scripts/activate
# macOS/Linux
source .venv/bin/activate
pip install flask flask-cors mysql-connector-python

2) Configure MySQL
Update credentials in app.py if needed:
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASS = ""          # set your password if any
DB_NAME = "tamankota"

3) Initialize the database
Either run init_db.py directly…
python init_db.py
…or let run_both.py run it automatically (default behavior).

Run
Option A — Run both services (recommended)
Starts init_db.py (once), app.py (5000) and auth_sqlite.py (5001).
It streams prefixed logs and shuts down both services together.
python run_both.py
Environment variables (optional):
INIT_DB_PATH — custom path to init_db.py
SKIP_INIT_DB=1 — skip running the DB initializer
AUTH_SQLITE_PATH — custom path to auth.sqlite3

Option B — Run services separate
# API (MySQL)
python app.py

# Auth (SQLite)
python auth_sqlite.py

🖥 Frontend
Open the HTML files with a static server (or place them under Apache/Nginx).
Buttons in the sidebar link the four pages:
1. start_index.html
2. input_index.html
3. output_index.html
4. report_index.html ← report builder & printer
CORS: app.py allows requests from http://127.0.0.1:8081 and http://localhost:8081 by default.
Adjust CORS(...) origins if your static server runs elsewhere.

🔌 API (high level)
Health
1. GET /api/health
Master data
1. GET /api/taman — list parks
2. POST /api/taman — create
3. GET /api/petugas — list staff
4. POST /api/petugas — create
5. GET /api/kegiatan — list activities
6. POST /api/kegiatan — create
Tanaman
1. GET /api/tanaman?id_taman=<int> — plants in a single park
2. POST /api/tanaman — create
3. GET /api/tanaman_all — all plants (no id_taman needed) ← used by report
Laporan
1. GET /api/laporan?limit=… — list joined report rows
2. POST /api/laporan — create
Report helpers
1. GET /api/report/all?limit=… — bundle of all data for the report (single call)
2. GET /api/report/html?limit=… — server-rendered printable HTML
Admin (danger)
1. POST /api/admin/clear_all — delete everything
Body example:
{ "confirm": true, "reset_auto_increment": true }
⚠️ Warning: clear_all wipes laporan, tanaman, petugas, kegiatan, taman. Use only in dev/testing.

📝 Report printing
In report_index.html:
1. Cetak (Mode Klien): Browser fetches /api/report/all (fallbacks to safe variants), builds HTML locally, and opens the print dialog.
2. Cetak (Mode Server): Opens /api/report/html in a new tab and prints from there.
Styling details:
1. Uniform table widths with a fixed narrow No. column
2. table-layout: fixed for consistent column sizing
3. Extra visual spacing between sections (five blank spacer rows)

🗄 Database model (simplified)
1. taman(id_taman, nama_taman, luas_taman, lokasi)
2. petugas(id_petugas, nama_petugas, jabatan)
3. kegiatan(id_kegiatan, jenis_kegiatan)
4. tanaman(id_tanaman, id_taman → taman, nama_umum, nama_ilmiah, jenis)
5. laporan(id_laporan, id_tanaman → tanaman, id_petugas → petugas, id_kegiatan → kegiatan, tanggal, isi_laporan)
init_db.py creates tables and (optionally) seed data.

🧪 Quick test
# Start
python run_both.py

# In a browser:
http://127.0.0.1:5000/api/health
# Open your static frontend (e.g., http://127.0.0.1:8081/report_index.html)

🛠 Troubleshooting
“id_taman query param is required”
Fixed by using /api/tanaman_all and /api/report/all in the report code. Make sure you’re on the latest files.
Both services blocking each other
Use run_both.py (handles both processes, output, and teardown).
Stopping processes
1. In VS Code Terminal: click the trash (Kill Terminal).
2. On Windows Git Bash: sometimes Ctrl+C is intercepted—close the terminal or use run_both.py which sends termination signals to both children.
CORS errors
Add your static server origin to the CORS config in app.py.

🔐 Security notes
This is a development/demo setup: no auth on the main API, and a destructive admin endpoint is exposed.
Lock down CORS, protect /api/admin/clear_all, and add authentication before production use.

📜 License
MIT (or your preferred license)

🙌 Acknowledgements
Thanks to everyone who tested, filed bugs, and suggested UX tweaks (sticky sidebar, theme toggle, table spacing).
