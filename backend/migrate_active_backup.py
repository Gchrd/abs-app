"""
Migration: Tambah kolom active_backup_id ke tabel devices.
Jalankan sekali saja: python migrate_active_backup.py
"""

import sqlite3
import sys
from pathlib import Path

# Cari DB file — sesuaikan path jika berbeda
DB_CANDIDATES = [
    Path("data/abs.db"),
    Path("../data/abs.db"),
    Path("abs.db"),
]

db_path = None
for candidate in DB_CANDIDATES:
    if candidate.exists():
        db_path = candidate.resolve()
        break

if db_path is None:
    # Coba baca dari .env
    env_file = Path(".env")
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if line.startswith("DB_URL"):
                url = line.split("=", 1)[1].strip().strip('"').strip("'")
                if url.startswith("sqlite:///"):
                    candidate = Path(url.replace("sqlite:///", ""))
                    if candidate.exists():
                        db_path = candidate.resolve()
                        break

if db_path is None:
    print("ERROR: Database file tidak ditemukan. Pastikan kamu menjalankan script ini dari folder backend/")
    sys.exit(1)

print(f"[+] Menggunakan database: {db_path}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

# Cek apakah kolom sudah ada
cur.execute("PRAGMA table_info(devices)")
columns = [row[1] for row in cur.fetchall()]

if "active_backup_id" in columns:
    print("[!] Kolom active_backup_id sudah ada. Migration dilewati.")
else:
    print("[+] Menambahkan kolom active_backup_id ke tabel devices...")
    cur.execute("ALTER TABLE devices ADD COLUMN active_backup_id INTEGER REFERENCES backups(id)")
    print("[+] Kolom berhasil ditambahkan.")

# Set default: active_backup_id = backup success terbaru per device
print("[+] Mengisi active_backup_id dengan backup terbaru per device...")
cur.execute("""
    UPDATE devices
    SET active_backup_id = (
        SELECT id FROM backups
        WHERE device_id = devices.id
          AND status = 'success'
        ORDER BY timestamp DESC
        LIMIT 1
    )
    WHERE active_backup_id IS NULL
""")

updated = cur.rowcount
conn.commit()
conn.close()

print(f"[+] Selesai. {updated} device diperbarui.")
print("[✓] Migration berhasil!")
