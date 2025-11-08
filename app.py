from flask import Flask, request, jsonify
from flask_cors import CORS
import mysql.connector
from datetime import datetime

# ---- DB config ----
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASS = ""           # set if you have a password
DB_NAME = "tamankota"

def get_conn():
    return mysql.connector.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME
    )

app = Flask(__name__)
# Allow Apache (127.0.0.1:8081 or localhost:8081) to call this API
CORS(
    app,
    resources={r"/api/*": {"origins": ["http://127.0.0.1:8081", "http://localhost:8081"]}},
    supports_credentials=False,
    methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"]
)

# ---- Helpers ----
def rows(query, params=None):
    conn = get_conn()
    try:
        with conn.cursor(dictionary=True) as cur:
            cur.execute(query, params or ())
            return cur.fetchall()
    finally:
        conn.close()

def execute(query, params=None):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(query, params or ())
            conn.commit()
            return cur.lastrowid
    finally:
        conn.close()

# ---- Health ----
@app.get("/api/health")
def health():
    try:
        rows("SELECT 1 AS ok")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}, 500

# ---- Taman ----
@app.get("/api/taman")
def list_taman():
    data = rows("""SELECT id_taman, nama_taman, luas_taman, lokasi
                   FROM taman ORDER BY nama_taman ASC""")
    return jsonify(data)

@app.post("/api/taman")
def create_taman():
    payload = request.get_json(force=True)
    nama = payload.get("nama_taman")
    luas = payload.get("luas_taman")
    lokasi = payload.get("lokasi")
    if not nama:
        return {"error": "nama_taman is required"}, 400
    try:
        new_id = execute(
            "INSERT INTO taman (nama_taman, luas_taman, lokasi) VALUES (%s, %s, %s)",
            (nama, int(luas) if luas not in (None, "") else None, lokasi),
        )
        return {"id_taman": new_id}, 201
    except mysql.connector.Error as e:
        return {"error": str(e)}, 400

# ---- Petugas ----
@app.get("/api/petugas")
def list_petugas():
    return jsonify(rows("SELECT id_petugas, nama_petugas, jabatan FROM petugas ORDER BY nama_petugas"))

@app.post("/api/petugas")
def create_petugas():
    payload = request.get_json(force=True)
    nama = payload.get("nama_petugas")
    jabatan = payload.get("jabatan")
    if not nama:
        return {"error": "nama_petugas is required"}, 400
    try:
        new_id = execute("INSERT INTO petugas (nama_petugas, jabatan) VALUES (%s, %s)", (nama, jabatan))
        return {"id_petugas": new_id}, 201
    except mysql.connector.Error as e:
        return {"error": str(e)}, 400

# ---- Kegiatan ----
@app.get("/api/kegiatan")
def list_kegiatan():
    return jsonify(rows("SELECT id_kegiatan, jenis_kegiatan FROM kegiatan ORDER BY jenis_kegiatan"))

@app.post("/api/kegiatan")
def create_kegiatan():
    payload = request.get_json(force=True)
    jenis = payload.get("jenis_kegiatan")
    if not jenis:
        return {"error": "jenis_kegiatan is required"}, 400
    try:
        new_id = execute("INSERT INTO kegiatan (jenis_kegiatan) VALUES (%s)", (jenis,))
        return {"id_kegiatan": new_id}, 201
    except mysql.connector.Error as e:
        return {"error": str(e)}, 400

# ---- Tanaman ----
@app.get("/api/tanaman")
def list_tanaman():
    id_taman = request.args.get("id_taman", type=int)
    if not id_taman:
        return {"error": "id_taman query param is required"}, 400
    data = rows("""SELECT id_tanaman, id_taman, nama_umum, nama_ilmiah, jenis
                   FROM tanaman WHERE id_taman = %s ORDER BY id_tanaman DESC""",
                (id_taman,))
    return jsonify(data)

@app.post("/api/tanaman")
def create_tanaman():
    payload = request.get_json(force=True)
    try:
        id_taman = int(payload["id_taman"])
    except Exception:
        return {"error": "id_taman is required (int)"}, 400
    nama_umum   = payload.get("nama_umum")
    nama_ilmiah = payload.get("nama_ilmiah")
    jenis       = payload.get("jenis")
    if not nama_umum:
        return {"error": "nama_umum is required"}, 400
    try:
        new_id = execute(
            "INSERT INTO tanaman (id_taman, nama_umum, nama_ilmiah, jenis) VALUES (%s, %s, %s, %s)",
            (id_taman, nama_umum, nama_ilmiah, jenis)
        )
        return {"id_tanaman": new_id}, 201
    except mysql.connector.Error as e:
        return {"error": str(e)}, 400

# ---- Laporan (join for a nice view) ----
@app.get("/api/laporan")
def list_laporan():
    limit = request.args.get("limit", default=20, type=int)
    data = rows("""
        SELECT l.id_laporan, l.id_tanaman, l.id_petugas, l.id_kegiatan, l.tanggal, l.isi_laporan,
               t.nama_umum AS tanaman, p.nama_petugas AS petugas, k.jenis_kegiatan AS kegiatan
        FROM laporan l
        JOIN tanaman t   ON t.id_tanaman = l.id_tanaman
        JOIN petugas p   ON p.id_petugas = l.id_petugas
        JOIN kegiatan k  ON k.id_kegiatan = l.id_kegiatan
        ORDER BY l.tanggal DESC
        LIMIT %s
    """, (limit,))
    for r in data:
        if isinstance(r["tanggal"], datetime):
            r["tanggal"] = r["tanggal"].isoformat(sep=" ", timespec="seconds")
    return jsonify(data)

@app.post("/api/laporan")
def create_laporan():
    payload = request.get_json(force=True)
    try:
        id_tanaman  = int(payload["id_tanaman"])
        id_petugas  = int(payload["id_petugas"])
        id_kegiatan = int(payload["id_kegiatan"])
    except Exception:
        return {"error": "id_tanaman, id_petugas, id_kegiatan are required (ints)"}, 400

    tanggal = payload.get("tanggal")
    isi     = payload.get("isi_laporan", "")

    if not tanggal:
        q = """INSERT INTO laporan (id_tanaman, id_petugas, id_kegiatan, tanggal, isi_laporan)
               VALUES (%s, %s, %s, NOW(), %s)"""
        params = (id_tanaman, id_petugas, id_kegiatan, isi)
    else:
        q = """INSERT INTO laporan (id_tanaman, id_petugas, id_kegiatan, tanggal, isi_laporan)
               VALUES (%s, %s, %s, %s, %s)"""
        params = (id_tanaman, id_petugas, id_kegiatan, tanggal, isi)

    try:
        new_id = execute(q, params)
        return {"id_laporan": new_id}, 201
    except mysql.connector.Error as e:
        return {"error": str(e)}, 400


# ============================================================
# NEW: Report helpers and routes (added without changing above)
# ============================================================

def _fmt_date(v):
    return v.isoformat(sep=" ", timespec="seconds") if isinstance(v, datetime) else v

def _escape_html(s):
    s = "" if s is None else str(s)
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&#39;"))

def _build_table(headers, rows_):
    thead = "<thead><tr>" + "".join(f"<th>{_escape_html(h)}</th>" for h in headers) + "</tr></thead>"
    tbody_rows = []
    for r in rows_:
        tds = "".join(f"<td>{_escape_html(c)}</td>" for c in r)
        tbody_rows.append(f"<tr>{tds}</tr>")
    tbody = "<tbody>" + "".join(tbody_rows) + "</tbody>"
    return f"<table>{thead}{tbody}</table>"

def _build_report_html(bundle):
    taman    = bundle.get("taman")    or []
    petugas  = bundle.get("petugas")  or []
    kegiatan = bundle.get("kegiatan") or []
    tanaman_ = bundle.get("tanaman")  or []
    laporan  = bundle.get("laporan")  or []

    # maps
    map_taman_name_by_id = {int(t["id_taman"]): t["nama_taman"] for t in taman if t.get("id_taman") is not None}
    map_taman_name_by_tanaman_id = {}
    for x in tanaman_:
        try:
            id_tanaman = int(x.get("id_tanaman"))
            id_taman = int(x.get("id_taman")) if x.get("id_taman") is not None else None
            if id_tanaman is not None and id_taman is not None:
                map_taman_name_by_tanaman_id[id_tanaman] = map_taman_name_by_id.get(id_taman, "-")
        except Exception:
            pass
    map_tanaman_by_name = {str(x.get("nama_umum","")).lower(): x for x in tanaman_}

    # sections
    sec1 = _build_table(
        ["No.", "Nama", "Luas (m²)", "Lokasi"],
        [[i+1, t.get("nama_taman",""), t.get("luas_taman","-"), t.get("lokasi","-")] for i, t in enumerate(taman)]
    )

    sec2 = _build_table(
        ["No.", "Nama Petugas", "Jabatan"],
        [[i+1, p.get("nama_petugas",""), p.get("jabatan","-")] for i, p in enumerate(petugas)]
    )

    sec3 = _build_table(
        ["No.", "Jenis Kegiatan"],
        [[i+1, k.get("jenis_kegiatan","")] for i, k in enumerate(kegiatan)]
    )

    sec4 = _build_table(
        ["No.", "Nama Taman", "Nama Tanaman", "Nama Ilmiah", "Jenis"],
        [[
            i+1,
            map_taman_name_by_id.get(int(x.get("id_taman") or 0), "-"),
            x.get("nama_umum",""),
            x.get("nama_ilmiah","-"),
            x.get("jenis","-")
        ] for i, x in enumerate(tanaman_)]
    )

    rows5 = []
    for i, L in enumerate(laporan):
        nama_taman = "-"
        try:
            if L.get("id_tanaman") is not None:
                nama_taman = map_taman_name_by_tanaman_id.get(int(L["id_tanaman"]), "-")
            elif L.get("tanaman"):
                t_ = map_tanaman_by_name.get(str(L["tanaman"]).lower())
                if t_ and t_.get("id_taman") is not None:
                    nama_taman = map_taman_name_by_id.get(int(t_["id_taman"]), "-")
        except Exception:
            pass

        rows5.append([
            i+1,
            _fmt_date(L.get("tanggal")) or "",
            nama_taman,
            L.get("tanaman",""),
            L.get("kegiatan",""),
            L.get("isi_laporan","")
        ])

    sec5 = _build_table(
        ["No.", "Tanggal", "Nama Taman", "Nama Tanaman", "Kegiatan", "Isi Laporan"],
        rows5
    )

    tgl_str = datetime.now().strftime("%d %B %Y")
    html = f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Laporan Kegiatan Penataan Taman Kota</title>
<style>
  body{{ font-family:Inter, Arial, sans-serif; color:#111827; margin:24px; }}
  h1{{ margin:0 0 8px; font-size:22px }}
  h2{{ margin:22px 0 8px; font-size:16px }}
  .muted{{ color:#374151; font-size:12px; margin-bottom:16px }}
  table{{ width:100%; border-collapse:collapse; margin:8px 0 18px }}
  th,td{{ border:1px solid #d1d5db; padding:8px 10px; font-size:12px; vertical-align:top }}
  thead th{{ background:#f3f4f6; font-weight:700 }}
  .header{{ display:flex; justify-content:space-between; align-items:flex-end; margin-bottom:8px }}
  @media print{{ @page{{ size:A4; margin:15mm }} body{{ margin:0 }} .noprint{{ display:none !important }} }}
</style>
</head>
<body>
  <div class="header">
    <h1>Laporan Kegiatan Penataan Taman Kota</h1>
    <div class="muted">Tanggal cetak: {_escape_html(tgl_str)}</div>
  </div>

  <h2>I. Identitas Taman</h2>
  {sec1}

  <h2>II. Susunan Petugas Taman</h2>
  {sec2}

  <h2>III. Kegiatan yang Dilakukan</h2>
  {sec3}

  <h2>IV. Data Tanaman di Taman</h2>
  {sec4}

  <h2>V. Laporan Pendataan Penataan Taman Kota</h2>
  {sec5}

  <div class="muted">Sumber: Sistem Informasi Perawatan Taman Kota</div>
</body>
</html>"""
    return html

@app.get("/api/tanaman_all")
def list_tanaman_all():
    """
    Return ALL tanaman (no id_taman required). Safe for report builders.
    """
    data = rows("""
        SELECT id_tanaman, id_taman, nama_umum, nama_ilmiah, jenis
        FROM tanaman
        ORDER BY id_taman, id_tanaman
    """)
    return jsonify(data)

@app.get("/api/report/all")
def report_all():
    """
    Return everything the report page needs in ONE JSON.
    Optional: ?limit= (default 100000) to cap laporan rows.
    """
    limit = request.args.get("limit", default=100000, type=int)

    bundle = {
        "taman": rows("""
            SELECT id_taman, nama_taman, luas_taman, lokasi
            FROM taman
            ORDER BY nama_taman
        """),
        "petugas": rows("""
            SELECT id_petugas, nama_petugas, jabatan
            FROM petugas
            ORDER BY nama_petugas
        """),
        "kegiatan": rows("""
            SELECT id_kegiatan, jenis_kegiatan
            FROM kegiatan
            ORDER BY jenis_kegiatan
        """),
        "tanaman": rows("""
            SELECT id_tanaman, id_taman, nama_umum, nama_ilmiah, jenis
            FROM tanaman
            ORDER BY id_taman, id_tanaman
        """),
        "laporan": rows("""
            SELECT
                l.id_laporan,
                l.id_tanaman,
                l.id_petugas,
                l.id_kegiatan,
                l.tanggal,
                l.isi_laporan,
                t.nama_umum      AS tanaman,
                p.nama_petugas   AS petugas,
                k.jenis_kegiatan AS kegiatan
            FROM laporan l
            JOIN tanaman  t ON t.id_tanaman = l.id_tanaman
            JOIN petugas  p ON p.id_petugas = l.id_petugas
            JOIN kegiatan k ON k.id_kegiatan = l.id_kegiatan
            ORDER BY l.tanggal DESC
            LIMIT %s
        """, (limit,))
    }

    for r in bundle["laporan"]:
        if isinstance(r.get("tanggal"), datetime):
            r["tanggal"] = r["tanggal"].isoformat(sep=" ", timespec="seconds")

    return jsonify(bundle)

@app.get("/api/report/html")
def report_html():
    """
    Server-rendered printable HTML report of the entire database.
    Optional: ?limit= (default 100000) to cap laporan rows.
    """
    limit = request.args.get("limit", default=100000, type=int)

    bundle = {
        "taman": rows("SELECT id_taman, nama_taman, luas_taman, lokasi FROM taman ORDER BY nama_taman"),
        "petugas": rows("SELECT id_petugas, nama_petugas, jabatan FROM petugas ORDER BY nama_petugas"),
        "kegiatan": rows("SELECT id_kegiatan, jenis_kegiatan FROM kegiatan ORDER BY jenis_kegiatan"),
        "tanaman": rows("SELECT id_tanaman, id_taman, nama_umum, nama_ilmiah, jenis FROM tanaman ORDER BY id_taman, id_tanaman"),
        "laporan": rows("""
            SELECT
                l.id_laporan,
                l.id_tanaman,
                l.id_petugas,
                l.id_kegiatan,
                l.tanggal,
                l.isi_laporan,
                t.nama_umum      AS tanaman,
                p.nama_petugas   AS petugas,
                k.jenis_kegiatan AS kegiatan
            FROM laporan l
            JOIN tanaman  t ON t.id_tanaman = l.id_tanaman
            JOIN petugas  p ON p.id_petugas = l.id_petugas
            JOIN kegiatan k ON k.id_kegiatan = l.id_kegiatan
            ORDER BY l.tanggal DESC
            LIMIT %s
        """, (limit,))
    }

    for r in bundle["laporan"]:
        if isinstance(r.get("tanggal"), datetime):
            r["tanggal"] = r["tanggal"].isoformat(sep=" ", timespec="seconds")

    html = _build_report_html(bundle)
    return app.response_class(html, mimetype="text/html")


# ==== Admin: clear all data (danger) ====
@app.post("/api/admin/clear_all")
def admin_clear_all():
    """
    Danger zone. Deletes all rows in FK-safe order:
      laporan -> tanaman -> petugas -> kegiatan -> taman

    Call with JSON body: { "confirm": true, "reset_auto_increment": true }
    - "confirm" is required to avoid accidental wipes
    - "reset_auto_increment" (default True) will reset AUTO_INCREMENT counters
    """
    try:
        payload = request.get_json(force=True, silent=True) or {}
    except Exception:
        payload = {}

    if not payload.get("confirm"):
        return {"error": "confirmation required: set {\"confirm\": true} in JSON body"}, 400

    reset_ai = bool(payload.get("reset_auto_increment", True))

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            # Delete in FK-safe order
            cur.execute("DELETE FROM laporan")
            cur.execute("DELETE FROM tanaman")
            cur.execute("DELETE FROM petugas")
            cur.execute("DELETE FROM kegiatan")
            cur.execute("DELETE FROM taman")

            # Optionally reset AUTO_INCREMENT for a clean slate
            if reset_ai:
                for tbl in ("laporan", "tanaman", "petugas", "kegiatan", "taman"):
                    try:
                        cur.execute(f"ALTER TABLE {tbl} AUTO_INCREMENT = 1")
                    except mysql.connector.Error:
                        # Non-fatal; skip if not supported
                        pass

        conn.commit()
        return {
            "status": "ok",
            "cleared": ["laporan", "tanaman", "petugas", "kegiatan", "taman"],
            "reset_auto_increment": reset_ai
        }
    except mysql.connector.Error as e:
        conn.rollback()
        return {"error": str(e)}, 500
    finally:
        conn.close()


if __name__ == "__main__":
    # Bind to all interfaces (fixes localhost/::1 issues). Visit from 127.0.0.1:5000
    app.run(host="0.0.0.0", port=5000, debug=True)
