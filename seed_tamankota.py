"""
Seed data injector for the `tamankota` database.

Usage examples:
    python seed_tamankota.py                 # seed with defaults
    python seed_tamankota.py --laporan-per-tanaman 5
    python seed_tamankota.py --host 127.0.0.1 --user root --password '' --db tamankota

Notes:
- Assumes schema already exists (tables taman, tanaman, petugas, kegiatan, laporan).
- Idempotent-ish for `taman` via UNIQUE(nama_taman); others may accumulate on repeated runs.
- Uses only stdlib + mysql-connector-python.

Dependencies:
    pip install mysql-connector-python
"""
from __future__ import annotations

import argparse
import random
from datetime import datetime, timedelta

import mysql.connector

# -------------------------------
# Helpers
# -------------------------------

def connect_mysql(host: str, port: int, user: str, password: str, db: str):
    return mysql.connector.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
    )


def seed_taman(cur) -> dict:
    taman_list = [
        ("Taman Mentari", 1200, "Jl. Sudirman"),
        ("Taman Anggrek", 900, "Jl. Melati"),
        ("Taman Nusantara", 2500, "Jl. Merdeka"),
        ("Taman Pelangi", 1500, "Jl. Cemara"),
    ]
    sql = (
        "INSERT INTO taman (nama_taman, luas_taman, lokasi) VALUES (%s, %s, %s) "
        "ON DUPLICATE KEY UPDATE luas_taman=VALUES(luas_taman), lokasi=VALUES(lokasi)"
    )
    for row in taman_list:
        cur.execute(sql, row)
    # fetch ids
    cur.execute("SELECT id_taman, nama_taman FROM taman")
    return {r[1]: r[0] for r in cur.fetchall()}


def seed_petugas(cur) -> dict:
    petugas_list = [
        ("Budi Santoso", "Pengawas"),
        ("Sari Utami", "Koordinator"),
        ("Andi Wijaya", "Petugas Lapangan"),
        ("Rina Kartika", "Petugas Lapangan"),
    ]
    sql = "INSERT INTO petugas (nama_petugas, jabatan) VALUES (%s, %s)"
    for row in petugas_list:
        cur.execute(sql, row)
    cur.execute("SELECT id_petugas, nama_petugas FROM petugas")
    return {r[1]: r[0] for r in cur.fetchall()}


def seed_kegiatan(cur) -> dict:
    kegiatan_list = [
        ("Penyiraman",),
        ("Pemangkasan",),
        ("Pemupukan",),
        ("Penyiangan",),
        ("Pengendalian Hama",),
        ("Pembersihan",),
    ]
    sql = "INSERT INTO kegiatan (jenis_kegiatan) VALUES (%s)"
    for row in kegiatan_list:
        cur.execute(sql, row)
    cur.execute("SELECT id_kegiatan, jenis_kegiatan FROM kegiatan")
    return {r[1]: r[0] for r in cur.fetchall()}


def seed_tanaman(cur, taman_ids: dict) -> dict:
    # Some sample species by type
    sample_plants = [
        ("Bougainvillea", "Bougainvillea glabra", "Semak"),
        ("Pucuk Merah", "Syzygium oleina", "Perdu"),
        ("Ketapang Kencana", "Terminalia mantaly", "Pohon"),
        ("Tabebuya", "Handroanthus chrysotrichus", "Pohon"),
        ("Rumput Gajah Mini", "Pennisetum purpureum cv.", "Groundcover"),
        ("Soka", "Ixora javanica", "Semak"),
    ]
    sql = (
        "INSERT INTO tanaman (id_taman, nama_umum, nama_ilmiah, jenis) "
        "VALUES (%s, %s, %s, %s)"
    )
    inserted = []
    for nama_taman, id_tmn in taman_ids.items():
        for _ in range(4):  # 4 plants per taman
            nm_umum, nm_ilmiah, jenis = random.choice(sample_plants)
            cur.execute(sql, (id_tmn, nm_umum, nm_ilmiah, jenis))
            inserted.append((cur.lastrowid, id_tmn, nm_umum))
    # fetch all for mapping
    cur.execute("SELECT id_tanaman, id_taman, nama_umum FROM tanaman")
    return {(r[0]): (r[1], r[2]) for r in cur.fetchall()}  # id_tanaman -> (id_taman, nama_umum)


def seed_laporan(cur, tanaman_map: dict, petugas_ids: dict, kegiatan_ids: dict, laporan_per_tanaman: int = 2):
    petugas_id_list = list(petugas_ids.values())
    kegiatan_id_list = list(kegiatan_ids.values())
    sql = (
        "INSERT INTO laporan (id_tanaman, id_petugas, id_kegiatan, tanggal, isi_laporan) "
        "VALUES (%s, %s, %s, %s, %s)"
    )
    now = datetime.now()
    for id_tanaman, (_id_taman, nama_umum) in tanaman_map.items():
        for i in range(laporan_per_tanaman):
            pid = random.choice(petugas_id_list)
            kid = random.choice(kegiatan_id_list)
            when = now - timedelta(days=random.randint(0, 30), hours=random.randint(0, 23))
            isi = f"{i+1}. Catatan {nama_umum}: kegiatan rutin"
            cur.execute(sql, (id_tanaman, pid, kid, when, isi))


# -------------------------------
# Main
# -------------------------------

def main():
    parser = argparse.ArgumentParser(description="Seed sample data into tamankota DB")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=3306)
    parser.add_argument("--user", default="root")
    parser.add_argument("--password", default="")
    parser.add_argument("--db", default="tamankota")
    parser.add_argument("--laporan-per-tanaman", type=int, default=2)

    args = parser.parse_args()

    conn = connect_mysql(args.host, args.port, args.user, args.password, args.db)
    try:
        conn.autocommit = False
        cur = conn.cursor()

        # Seed in FK-safe order
        taman_ids = seed_taman(cur)
        petugas_ids = seed_petugas(cur)
        kegiatan_ids = seed_kegiatan(cur)
        tanaman_map = seed_tanaman(cur, taman_ids)
        seed_laporan(cur, tanaman_map, petugas_ids, kegiatan_ids, args.laporan_per_tanaman)

        conn.commit()
        print("[OK] Seeding completed.")
        print(f" - Taman: {len(taman_ids)} (existing+new)")
        print(f" - Petugas: {len(petugas_ids)} (existing+new)")
        print(f" - Kegiatan: {len(kegiatan_ids)} (existing+new)")
        print(f" - Tanaman: {len(tanaman_map)} total rows now")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
