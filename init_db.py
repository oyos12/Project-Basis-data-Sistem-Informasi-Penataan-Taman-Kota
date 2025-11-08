import mysql.connector
from mysql.connector import errorcode

# --- Config ---
DB_HOST = "localhost"
DB_PORT = 3306
DB_USER = "root"
DB_PASS = ""
DB_NAME = "tamankota"

# --- DDL statements ---
DDL = [
    # Database (created using a server-level connection, no DB selected)
    f"CREATE DATABASE IF NOT EXISTS {DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci",

    # Tables (run after we reconnect to DB_NAME)
    """
    CREATE TABLE IF NOT EXISTS taman (
        id_taman     INT AUTO_INCREMENT PRIMARY KEY,
        nama_taman   VARCHAR(100) NOT NULL,
        luas_taman   INT,
        lokasi       VARCHAR(255),
        UNIQUE KEY uk_taman_nama (nama_taman)
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE IF NOT EXISTS tanaman (
        id_tanaman   INT AUTO_INCREMENT PRIMARY KEY,
        id_taman     INT NOT NULL,
        nama_umum    VARCHAR(100),
        nama_ilmiah  VARCHAR(150),
        jenis        VARCHAR(80),
        CONSTRAINT fk_tanaman_taman
            FOREIGN KEY (id_taman) REFERENCES taman(id_taman)
            ON DELETE CASCADE ON UPDATE CASCADE,
        INDEX ix_tanaman_id_taman (id_taman)
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE IF NOT EXISTS petugas (
        id_petugas    INT AUTO_INCREMENT PRIMARY KEY,
        nama_petugas  VARCHAR(100) NOT NULL,
        jabatan       VARCHAR(100)
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE IF NOT EXISTS kegiatan (
        id_kegiatan    INT AUTO_INCREMENT PRIMARY KEY,
        jenis_kegiatan VARCHAR(120) NOT NULL
    ) ENGINE=InnoDB
    """,
    """
    CREATE TABLE IF NOT EXISTS laporan (
        id_laporan   INT AUTO_INCREMENT PRIMARY KEY,
        id_tanaman   INT NOT NULL,
        id_petugas   INT NOT NULL,
        id_kegiatan  INT NOT NULL,
        tanggal      DATETIME NOT NULL,
        isi_laporan  TEXT,

        CONSTRAINT fk_laporan_tanaman
            FOREIGN KEY (id_tanaman) REFERENCES tanaman(id_tanaman)
            ON DELETE RESTRICT ON UPDATE CASCADE,
        CONSTRAINT fk_laporan_petugas
            FOREIGN KEY (id_petugas) REFERENCES petugas(id_petugas)
            ON DELETE RESTRICT ON UPDATE CASCADE,
        CONSTRAINT fk_laporan_kegiatan
            FOREIGN KEY (id_kegiatan) REFERENCES kegiatan(id_kegiatan)
            ON DELETE RESTRICT ON UPDATE CASCADE,

        INDEX ix_laporan_tanaman (id_tanaman),
        INDEX ix_laporan_petugas (id_petugas),
        INDEX ix_laporan_kegiatan (id_kegiatan),
        INDEX ix_laporan_tanggal (tanggal)
    ) ENGINE=InnoDB
    """
]

def create_database_if_needed():
    """Create the database using a server-level connection (no database selected)."""
    conn = mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, port=DB_PORT
    )
    try:
        with conn.cursor() as cur:
            cur.execute(DDL[0])  # CREATE DATABASE IF NOT EXISTS ...
        conn.commit()
    finally:
        conn.close()

def connect_database():
    """Connect to the target database (assumes it exists)."""
    return mysql.connector.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASS, port=DB_PORT, database=DB_NAME
    )

def run_table_ddls():
    """Run table DDLs in order (skip the first DDL which is CREATE DATABASE)."""
    conn = connect_database()
    try:
        with conn.cursor() as cur:
            for stmt in DDL[1:]:
                # Some MySQL drivers require splitting on semicolons if multiple statements are present
                for sub in [s.strip() for s in stmt.strip().split(";") if s.strip()]:
                    cur.execute(sub)
        conn.commit()
    finally:
        conn.close()

def main():
    try:
        # Step 1: Ensure DB exists
        create_database_if_needed()
        print(f"[OK] Database '{DB_NAME}' ensured.")

        # Step 2: Create tables
        run_table_ddls()
        print("[OK] All tables ensured (created if missing).")

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Error: invalid MySQL credentials (user/password).")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Error: database does not exist and could not be created.")
        else:
            print(f"MySQL Error: {err}")
    except Exception as ex:
        print(f"Unexpected error: {ex}")

if __name__ == "__main__":
    main()
