#!/bin/sh
python3 - <<'EOF'
import sqlite3, os, pathlib

db_url = os.environ.get('DB_URL', 'sqlite:///./data/abs.db')
db_path = db_url.replace('sqlite:///', '')
if not pathlib.Path(db_path).is_absolute():
    db_path = '/app/' + db_path.lstrip('./')

print(f"[+] DB path: {db_path}")
print(f"[+] Exists: {pathlib.Path(db_path).exists()}")

conn = sqlite3.connect(db_path)
cur = conn.cursor()

cur.execute("PRAGMA table_info(devices)")
cols = [r[1] for r in cur.fetchall()]
print(f"[+] Current columns: {cols}")

if 'active_backup_id' in cols:
    print("[!] active_backup_id already exists, skipping ALTER.")
else:
    cur.execute("ALTER TABLE devices ADD COLUMN active_backup_id INTEGER")
    print("[+] Column added!")

cur.execute("""
    UPDATE devices
    SET active_backup_id = (
        SELECT id FROM backups
        WHERE device_id = devices.id AND status = 'success'
        ORDER BY timestamp DESC LIMIT 1
    )
    WHERE active_backup_id IS NULL
""")
print(f"[+] Devices updated: {cur.rowcount}")
conn.commit()
conn.close()
print("[OK] Done!")
EOF
