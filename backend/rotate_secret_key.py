"""
One-time migration: re-encrypt every stored device credential (username,
password, enable secret) from an OLD SECRET_KEY to a NEW one.

Why this exists: SECRET_KEY is used to derive the Fernet key that encrypts
device credentials at rest (see app/utils/crypto.py) AND to sign JWT login
tokens. The key that was in use got committed to git, so it needs to be
rotated - but the DB was encrypted with the old key, so credentials must be
re-encrypted or every decrypt() call will fail after the key changes.

Usage:
    OLD_SECRET_KEY=... NEW_SECRET_KEY=... python rotate_secret_key.py [--apply]

Without --apply it only reports how many devices it *would* re-encrypt
(dry run) - nothing is written. Run with --apply to actually commit.

After running this successfully against the production DB, update
backend/.env's SECRET_KEY to NEW_SECRET_KEY and restart the backend -
every existing login session will need to log in again (JWTs signed with
the old key stop validating), which is expected and harmless.
"""
import base64
import hashlib
import os
import sqlite3
import sys

from cryptography.fernet import Fernet, InvalidToken


def _derive_key(secret_key: str) -> bytes:
    return base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode()).digest())


def rotate(db_path: str, old_key: str, new_key: str, apply: bool) -> None:
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        sys.exit(1)

    old_fernet = Fernet(_derive_key(old_key))
    new_fernet = Fernet(_derive_key(new_key))

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT id, hostname, username_enc, password_enc, secret_enc FROM devices")
    rows = cursor.fetchall()

    updates = []
    for device_id, hostname, username_enc, password_enc, secret_enc in rows:
        try:
            new_username_enc = new_fernet.encrypt(old_fernet.decrypt(username_enc.encode())).decode() if username_enc else username_enc
            new_password_enc = new_fernet.encrypt(old_fernet.decrypt(password_enc.encode())).decode() if password_enc else password_enc
            new_secret_enc = new_fernet.encrypt(old_fernet.decrypt(secret_enc.encode())).decode() if secret_enc else secret_enc
        except InvalidToken:
            print(f"FAILED to decrypt device id={device_id} hostname={hostname!r} with OLD_SECRET_KEY - "
                  f"aborting without writing anything. Check OLD_SECRET_KEY is correct.")
            conn.close()
            sys.exit(1)
        updates.append((new_username_enc, new_password_enc, new_secret_enc, device_id))

    print(f"{len(updates)} device credential row(s) decrypted OK with OLD_SECRET_KEY and re-encrypted with NEW_SECRET_KEY.")

    if not apply:
        print("Dry run only - nothing written. Re-run with --apply to commit.")
        conn.close()
        return

    cursor.executemany(
        "UPDATE devices SET username_enc = ?, password_enc = ?, secret_enc = ? WHERE id = ?",
        updates,
    )
    conn.commit()
    conn.close()
    print("Committed. Now update backend/.env's SECRET_KEY to NEW_SECRET_KEY and restart the backend.")


if __name__ == "__main__":
    old_key = os.getenv("OLD_SECRET_KEY")
    new_key = os.getenv("NEW_SECRET_KEY")
    apply = "--apply" in sys.argv
    db_path = os.getenv("DB_PATH", "data/abs.db")

    if not old_key or not new_key:
        print("Set OLD_SECRET_KEY and NEW_SECRET_KEY environment variables first.")
        sys.exit(1)
    if old_key == new_key:
        print("OLD_SECRET_KEY and NEW_SECRET_KEY are identical - nothing to rotate.")
        sys.exit(1)

    rotate(db_path, old_key, new_key, apply)
