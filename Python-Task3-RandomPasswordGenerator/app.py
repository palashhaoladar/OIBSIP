"""Flask app: Password Generator + Encrypted Vault. Run: python app.py"""
import base64, secrets, sqlite3
from pathlib import Path
from flask import Flask, jsonify, render_template, request, session
import generator
import crypto_utils as cu

DB_PATH = Path(__file__).parent / "vault.db"
app = Flask(__name__)
app.secret_key = secrets.token_hex(32)  # local tool; regenerates per restart

# Derived AES keys live ONLY in memory, keyed by an opaque session id in the
# cookie. Nothing secret is persisted; lock/restart = vault unreadable.
MASTER_KEYS = {}

def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _vault_key():
    sid = session.get("sid")
    return MASTER_KEYS.get(sid) if sid else None

@app.route("/")
def index():
    return render_template("index.html")

# ---------------- Generator API ----------------
@app.post("/api/generate")
def api_generate():
    import math
    body = request.get_json(force=True)
    if body.get("mode") == "passphrase":
        words = int(body.get("words", 4))
        pwd = generator.generate_passphrase(words)
        n = len(generator._WORDLIST)
        est = cu.estimate_crack_times(words, n)
        return jsonify({"password": pwd, "mode": "passphrase",
                        "wordlist_size": n,
                        "entropy_bits": round(words * math.log2(n), 1),
                        "crack": est})
    length = int(body.get("length", 16))
    opts = {k: bool(body.get(k, True)) for k in
            ("upper", "lower", "digits", "symbols")}
    opts["exclude_ambiguous"] = bool(body.get("exclude_ambiguous", False))
    try:
        pool = generator.calculate_pool_size(**opts)
        pwd = generator.generate_password(length=length, **opts)
        est = cu.estimate_crack_times(length, pool)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"password": pwd, "mode": "password", "pool_size": pool,
                    "entropy_bits": est["entropy_bits"], "crack": est})

# ---------------- Breach check ----------------
@app.post("/api/breach")
def api_breach():
    password = request.get_json(force=True).get("password", "")
    if not password:
        return jsonify({"error": "No password supplied."}), 400
    try:
        pwned, count = cu.check_pwned(password)
    except Exception as exc:
        return jsonify({"error": f"Breach check unavailable: {exc}"}), 502
    return jsonify({"pwned": pwned, "count": count})

# ---------------- Vault APIs ----------------
@app.get("/api/status")
def api_status():
    conn = _get_db()
    try:
        row = conn.execute("SELECT id FROM master_auth WHERE id = 1").fetchone()
    finally:
        conn.close()
    return jsonify({"has_master": row is not None,
                    "unlocked": _vault_key() is not None})

@app.post("/api/setup")
def api_setup():
    password = request.get_json(force=True).get("master", "")
    if len(password) < 12:
        return jsonify({"error": "Master password must be at least 12 characters."}), 400
    conn = _get_db()
    try:
        if conn.execute("SELECT id FROM master_auth WHERE id = 1").fetchone():
            return jsonify({"error": "Master password already set. Use Unlock."}), 409
        salt = cu.generate_key_salt()
        conn.execute("INSERT INTO master_auth (id, password_hash, key_salt)"
                     " VALUES (1, ?, ?)",
                     (cu.hash_master_password(password),
                      base64.b64encode(salt).decode()))
        conn.commit()
    finally:
        conn.close()
    return _unlock(password)

@app.post("/api/unlock")
def api_unlock():
    password = request.get_json(force=True).get("master", "")
    conn = _get_db()
    try:
        row = conn.execute("SELECT password_hash FROM master_auth WHERE id = 1").fetchone()
    finally:
        conn.close()
    if not row or not cu.verify_master_password(row["password_hash"], password):
        return jsonify({"error": "Wrong master password."}), 401
    return _unlock(password)

def _unlock(password):
    conn = _get_db()
    try:
        row = conn.execute("SELECT key_salt FROM master_auth WHERE id = 1").fetchone()
    finally:
        conn.close()
    salt = base64.b64decode(row["key_salt"])
    sid = secrets.token_hex(16)
    session["sid"] = sid
    MASTER_KEYS[sid] = cu.derive_vault_key(password, salt)
    return jsonify({"ok": True})

@app.post("/api/lock")
def api_lock():
    sid = session.pop("sid", None)
    MASTER_KEYS.pop(sid, None)
    return jsonify({"ok": True})

@app.post("/api/vault/save")
def api_vault_save():
    key = _vault_key()
    if key is None:
        return jsonify({"error": "Vault is locked."}), 401
    b = request.get_json(force=True)
    if not (b.get("service") and b.get("username") and b.get("password")):
        return jsonify({"error": "service, username and password required."}), 400
    blob = cu.encrypt_secret(key, b["password"])
    conn = _get_db()
    try:
        conn.execute("INSERT INTO vault_entries (service, username, ciphertext)"
                     " VALUES (?, ?, ?)", (b["service"], b["username"], blob))
        conn.commit()
    finally:
        conn.close()
    return jsonify({"ok": True})

@app.get("/api/vault/list")
def api_vault_list():
    key = _vault_key()
    if key is None:
        return jsonify({"error": "Vault is locked."}), 401
    conn = _get_db()
    try:
        rows = conn.execute("SELECT id, service, username, created_at"
                            " FROM vault_entries ORDER BY service").fetchall()
    finally:
        conn.close()
    return jsonify({"entries": [dict(r) for r in rows]})  # metadata only, no ciphertext

@app.post("/api/vault/reveal")
def api_vault_reveal():
    key = _vault_key()
    if key is None:
        return jsonify({"error": "Vault is locked."}), 401
    entry_id = int(request.get_json(force=True).get("id", 0))
    conn = _get_db()
    try:
        row = conn.execute("SELECT ciphertext FROM vault_entries WHERE id = ?",
                           (entry_id,)).fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "Entry not found."}), 404
    try:
        return jsonify({"password": cu.decrypt_secret(key, row["ciphertext"])})
    except Exception:
        return jsonify({"error": "Decryption failed — tampered data or wrong key."}), 500

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)  # debugger = RCE; never debug=True
