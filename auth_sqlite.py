# -*- coding: utf-8 -*-
"""
SQLite-based Auth service (standalone or blueprint).
Endpoints:
  POST /api/auth/register  -> { user: {id, username, name} }
  POST /api/auth/login     -> { user: {id, username, name}, token: null }
  GET  /api/auth/health    -> { status: "ok" }

Run standalone:
  python auth_sqlite.py                # listens on :5001
Integrate into existing Flask app:
  from auth_sqlite import auth_bp
  app.register_blueprint(auth_bp, url_prefix="/api")
"""

import os
import sqlite3
from contextlib import contextmanager
from flask import Flask, Blueprint, request, jsonify
from flask_cors import CORS
from werkzeug.security import generate_password_hash, check_password_hash

# --- SQLite location (sits next to this file, easy to see in VSCode) ---
DB_PATH = os.environ.get(
    "AUTH_SQLITE_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "auth.sqlite3")
)

auth_bp = Blueprint("auth", __name__)

# ---------- DB helpers ----------
@contextmanager
def get_db():
    conn = sqlite3.connect(DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db():
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                username      TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                name          TEXT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    return DB_PATH

# ---------- Routes ----------
@auth_bp.get("/auth/health")
def health():
    try:
        with get_db() as db:
            db.execute("SELECT 1")
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}, 500

@auth_bp.post("/auth/register")
def register():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    name     = (data.get("name") or "").strip()

    if not username or not password:
        return jsonify(error="username dan password wajib diisi"), 400
    if len(password) < 6:
        return jsonify(error="password minimal 6 karakter"), 400

    ph = generate_password_hash(password)
    try:
        with get_db() as db:
            cur = db.execute(
                "INSERT INTO users (username, password_hash, name) VALUES (?, ?, ?)",
                (username, ph, name or None),
            )
            uid = cur.lastrowid
        return jsonify(user={"id": uid, "username": username, "name": name}), 201
    except sqlite3.IntegrityError:
        return jsonify(error="username sudah digunakan"), 409

@auth_bp.post("/auth/login")
def login():
    data = request.get_json(force=True, silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not username or not password:
        return jsonify(error="username dan password wajib diisi"), 400

    with get_db() as db:
        row = db.execute(
            "SELECT id, username, password_hash, COALESCE(name, username) AS name "
            "FROM users WHERE username = ?",
            (username,)
        ).fetchone()

    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify(error="username atau password salah"), 401

    # Token/JWT could be generated here; returning null keeps frontend simple
    return jsonify(user={"id": row["id"], "username": row["username"], "name": row["name"]}, token=None)

# ---------- Standalone runner (optional) ----------
def create_app():
    app = Flask(__name__)
    CORS(app, resources={r"/api/*": {"origins": ["http://127.0.0.1:8081", "http://localhost:8081"]}})
    app.register_blueprint(auth_bp, url_prefix="/api")
    return app

if __name__ == "__main__":
    path = init_db()
    print(f"[auth] SQLite DB ready at: {path}")
    app = create_app()
    # Separate port 5001 so it won't conflict with your MySQL API on 5000
    app.run(host="0.0.0.0", port=5001, debug=True)
