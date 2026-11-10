<div align="center">

# Sentinel
### A Cryptographically Secure Local Vault & Password Generator

**Oasis Infobyte Internship — Task 3**

<img src="https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python" /> <img src="https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white" alt="Flask" /> <img src="https://img.shields.io/badge/SQLite-003B57?style=for-the-badge&logo=sqlite&logoColor=white" alt="SQLite" />

</div>

<br>

Sentinel is a highly secure, local-first password management tool built with Python and Flask. Designed with a strict adherence to modern cryptographic standards, it functions as both an advanced password generator and an encrypted local vault. Sentinel prioritizes data sovereignty—ensuring that your master keys never touch a disk and your plaintext data never leaves your machine.

---

### Key Features

* **Cryptographically Secure Generator:** Utilizes the OS-level CSPRNG (`secrets` module) rather than predictable pseudorandom generators (`random`). Guarantees uniform character distribution and prevents structural leakage via Fisher-Yates shuffling.
* **Passphrase Mode (XKCD-style):** Generates high-entropy passphrases using a secure wordlist. These provide mathematically stronger security guarantees while remaining easy for humans to type and remember.
* **Real-Time Threat Analysis:** Calculates Shannon entropy and estimates theoretical crack times across various threat models (from throttled online attacks to offline GPU-cluster leaks).
* **Zero-Knowledge Breach Checks:** Integrates with the Have I Been Pwned (HIBP) API using a strict k-anonymity model. Only the first 5 characters of a SHA-1 hash are transmitted, cryptographically guaranteeing that the network cannot reconstruct your password.

---

### Security Architecture

Sentinel is built on enterprise-grade cryptographic primitives to ensure the confidentiality and integrity of your vault:
1. **Authentication (Argon2id):** The master password is hashed using Argon2id (the winner of the Password Hashing Competition) purely for verification.
2. **Key Derivation:** A separate, cryptographically independent base64 salt is used to derive the raw 32-byte AES-256 vault key via Argon2id. This key is kept exclusively in active memory and is never written to disk.
3. **Authenticated Encryption (AES-256-GCM):** Vault secrets are stored in a local SQLite database (`vault.db`) as `base64( nonce || ciphertext + GCM-tag )`.
   * A fresh 96-bit nonce is generated for every encryption event.
   * The GCM authentication tag ensures that any tampering with the database files fails loudly upon decryption.

---

### Installation

**1. Clone the repository**
```bash
git clone https://github.com/palashhaoladar/OIBSIP.git
cd Python-Task3-RandomPasswordGenerator
```

**2. Create a Virtual Environment (Recommended)**
```bash
# For macOS/Linux
python -m venv venv
source venv/bin/activate

# For Windows
python -m venv venv
venv\Scripts\activate
```

**3. Install dependencies**
```bash
pip install -r requirements.txt
```

**4. Initialize the Database & Run**
```bash
python init_db.py
python app.py
```