"""SQLite initialisation — run once: python init_db.py"""
import sqlite3, sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "vault.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS master_auth (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    password_hash TEXT    NOT NULL,   -- Argon2id PHC string (verification only)
    key_salt      TEXT    NOT NULL,   -- base64 salt for AES-256 key derivation
    created_at    TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS vault_entries (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    service    TEXT NOT NULL,
    username   TEXT NOT NULL,
    ciphertext TEXT NOT NULL,          -- base64( nonce || AES-256-GCM(password) )
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""

def init_db(path=DB_PATH):
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        print(f"[+] Database initialised at {path}")
    finally:
        conn.close()

if __name__ == "__main__":
    if DB_PATH.exists():
        print(f"[!] {DB_PATH} already exists — leaving it untouched.")
        sys.exit(0)
    init_db()
