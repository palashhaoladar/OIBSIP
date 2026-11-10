"""
crypto_utils.py — Cryptographic Security Layer
1. Entropy & time-to-crack      3. Argon2id master-password protection
2. HIBP k-anonymity breach check 4. AES-256-GCM vault encryption

NOTE: `cryptography.fernet` is AES-128-CBC + HMAC, NOT AES-256. For honest
AES-256 this module uses AES-256-GCM — an AEAD providing confidentiality and
integrity in one primitive, with a fresh 96-bit nonce per message (the
critical GCM requirement: never reuse a nonce under one key).
"""
import base64
import hashlib
import math
import secrets

import requests
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from argon2.low_level import hash_secret, Type
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# ---------------------------------------------------------------- 1. entropy
def entropy_bits(length, pool_size):
    """Shannon entropy of a uniform random password: E = L * log2(R).
    Entropy is a property of the generation PROCESS, not the string."""
    if pool_size <= 1 or length <= 0:
        return 0.0
    return length * math.log2(pool_size)


def _human_duration(seconds):
    if seconds < 1:
        return "instantly"
    units = [(60**4*24*365.25*1e9, "billion years"),
             (60**4*24*365.25*1e6, "million years"),
             (60**4*24*365.25*1e3, "thousand years"),
             (60**4*24*365.25, "years"), (60**4*24*30, "months"),
             (60**4*24*7, "weeks"), (60**4*24, "days"),
             (60**4, "hours"), (60, "minutes")]
    for factor, name in units:
        if seconds >= factor:
            return f"{seconds / factor:,.1f} {name}"
    return f"{seconds:,.0f} seconds"


def estimate_crack_times(length, pool_size):
    """Average-case crack time = half the key space / guess rate.
    online_throttled: 100 guesses/s   — rate-limited remote login
    offline_fast_hash: 10e9 guesses/s — leaked fast-hash DB on a GPU rig
    offline_cluster:   1e12 guesses/s — nation-state scale
    The offline numbers are the realistic worst case — hence salting + slow
    hashes (Argon2) matter so much."""
    E = entropy_bits(length, pool_size)
    possibilities = 2 ** E
    scenarios = {"online_throttled": 1e2,
                 "offline_fast_hash": 1e10,
                 "offline_cluster": 1e12}
    out = {"entropy_bits": round(E, 1)}
    for name, rate in scenarios.items():
        out[name] = _human_duration((possibilities / 2) / rate)
    return out

# ------------------------------------------------------- 2. k-anonymity HIBP
def check_pwned(password, timeout=10):
    """
    k-ANONYMITY model — the password is NEVER transmitted:
      1. SHA-1 locally; 2. send only the first 5 hex chars (prefix);
      3. HIBP returns ~500 matching suffixes + counts;
      4. compare the full suffix locally.
    A 5-hex prefix covers ~1/1,048,576 of the digest space — reveals nothing.
    (Hardening step: do the hash in browser Web Crypto so the plaintext
    never even reaches the localhost server.)
    """
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    resp = requests.get(f"https://api.pwnedpasswords.com/range/{prefix}",
                        headers={"User-Agent": "oib-password-vault/1.0"},
                        timeout=timeout)
    resp.raise_for_status()
    for line in resp.text.splitlines():
        returned_suffix, _, count = line.partition(":")
        if returned_suffix.strip() == suffix:
            return True, int(count)
    return False, 0

# --------------------------------------------- 3. Argon2id master protection
# Argon2 won the Password Hashing Competition; `id` blends side-channel-safe
# and GPU-resistant memory access (RFC 9106 / OWASP recommendations).
_ARGON_TIME, _ARGON_MEM, _ARGON_PAR = 3, 65536, 4   # t=3, m=64 MiB, p=4

_hasher = PasswordHasher(time_cost=_ARGON_TIME, memory_cost=_ARGON_MEM,
                         parallelism=_ARGON_PAR)

def hash_master_password(password):
    """PHC self-describing string — verification only, stored in SQLite."""
    return _hasher.hash(password)

def verify_master_password(stored_hash, password):
    """Constant-time verification."""
    try:
        return _hasher.verify(stored_hash, password)
    except VerifyMismatchError:
        return False

def generate_key_salt():
    return secrets.token_bytes(16)

def derive_vault_key(password, salt):
    """Raw 32-byte AES-256 key derived via Argon2id. Kept ONLY in memory —
    separate salt from the verification hash so the two outputs are
    cryptographically independent."""
    return hash_secret(secret=password.encode("utf-8"), salt=salt,
                       time_cost=_ARGON_TIME, memory_cost=_ARGON_MEM,
                       parallelism=_ARGON_PAR, hash_len=32, type=Type.ID)

# ------------------------------------------------------ 4. AES-256-GCM vault
def encrypt_secret(key, plaintext):
    """Returns base64( nonce(12B) || ciphertext+GCM-tag ). The tag makes the
    stored blob self-authenticating — any tampering fails loudly on open."""
    nonce = secrets.token_bytes(12)
    ct = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")

def decrypt_secret(key, blob_b64):
    """Raises InvalidTag if blob was tampered with or key is wrong."""
    raw = base64.b64decode(blob_b64)
    return AESGCM(key).decrypt(raw[:12], raw[12:], None).decode("utf-8")
