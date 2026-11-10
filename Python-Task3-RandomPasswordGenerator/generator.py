"""
generator.py — Core Password & Passphrase Generation Engine
==========================================================
Why `secrets` and not `random`?
`random` is a pseudorandom generator (Mersenne Twister); its state can be
recovered from observed output — unusable for security. `secrets` is built
on the OS CSPRNG (getrandom(2) on Linux) and is designed for secrets.
"""
import secrets
import string
from pathlib import Path

AMBIGUOUS_CHARS = "l1IO0"  # visually confused characters

EMBEDDED_WORDLIST = """
apple banner canyon delta ember falcon glacier harbor igloo jungle kettle
lunar marble nectar ocelot prairie quiver river stone tumble umbrella violet
willow xenon yellow zipper anchor breeze cobra dagger ember fjord griffin
helmet isle jacket kernel lantern meadow nickel onyx pepper quartz raven
saddle timber urchin velvet walnut yard zenith amber basil cinder dune
flint grove hazel ivory jasper keystone lagoon mocha nordic obsidian
pines quasar ridge sapphire topaz upland vale wagon birch coral drift elm
frost garnet hollow inlet jade kraken lumen moss nettle olive plum
summit thorn unity vine woven yield arch bolt cloud eagle flame gulf hawk
juniper kite lava node oak peak reef surge tide urn veil wave zone
""".split()

_SYSTEM_WORDS = Path("/usr/share/dict/words")


def _load_wordlist():
    """Prefer the system dictionary (on Arch: `pacman -S words`) for real
    entropy; fall back to the embedded shortlist so the tool runs anywhere.
    NOTE: shortlist entropy is low — E = words * log2(N) — install the real
    wordlist for production use."""
    words = EMBEDDED_WORDLIST
    try:
        if _SYSTEM_WORDS.exists():
            candidates = [w.strip().lower()
                          for w in _SYSTEM_WORDS.read_text(errors="ignore").splitlines()]
            candidates = [w for w in candidates
                          if w.isalpha() and 3 <= len(w) <= 10 and w.isascii()]
            if len(candidates) >= 1000:
                words = candidates
    except OSError:
        pass
    return words


_WORDLIST = _load_wordlist()


def build_pool(upper=True, lower=True, digits=True, symbols=True,
               exclude_ambiguous=False):
    pool = ""
    if upper:
        pool += string.ascii_uppercase
    if lower:
        pool += string.ascii_lowercase
    if digits:
        pool += string.digits
    if symbols:
        pool += "!@#$%^&*()-_=+[]{};:,.<>?/~"
    if exclude_ambiguous:
        pool = "".join(c for c in pool if c not in AMBIGUOUS_CHARS)
    if not pool:
        raise ValueError("At least one character class must be enabled.")
    return pool, len(pool)


def calculate_pool_size(**kw):
    return build_pool(**kw)[1]


def generate_password(length=16, upper=True, lower=True, digits=True,
                      symbols=True, exclude_ambiguous=False):
    """
    Security properties:
      * Every enabled class is GUARANTEED to appear at least once — otherwise
        a 16-char 4-class password could silently miss a class.
      * Each character is an independent uniform draw: secrets.choice().
      * Guaranteed characters are placed via CSPRNG Fisher-Yates so they
        don't leak structural info by sitting at fixed positions.
    """
    if not 8 <= length <= 128:
        raise ValueError("Length must be between 8 and 128 characters.")

    pool, _ = build_pool(upper, lower, digits, symbols, exclude_ambiguous)

    classes = []
    if upper:
        classes.append(string.ascii_uppercase)
    if lower:
        classes.append(string.ascii_lowercase)
    if digits:
        classes.append(string.digits)
    if symbols:
        classes.append("!@#$%^&*()-_=+[]{};:,.<>?/~")
    if exclude_ambiguous:
        classes = ["".join(c for c in cls if c not in AMBIGUOUS_CHARS)
                   for cls in classes]
        classes = [c for c in classes if c]

    chars = [secrets.choice(cls) for cls in classes]          # 1. guarantee
    while len(chars) < length:
        chars.append(secrets.choice(pool))                      # 2. fill
    for i in range(len(chars) - 1, 0, -1):                    # 3. shuffle
        j = secrets.randbelow(i + 1)
        chars[i], chars[j] = chars[j], chars[i]
    return "".join(chars)


def generate_passphrase(word_count=4):
    """
    XKCD-936 style: N random words joined by hyphens.
    E = word_count * log2(wordlist_size). EFF large list (7776 words),
    6 words => 77.5 bits — stronger than most 12-char passwords and far
    easier to type/remember.
    """
    if not 4 <= word_count <= 6:
        raise ValueError("Passphrase must contain between 4 and 6 words.")
    return "-".join(secrets.choice(_WORDLIST) for _ in range(word_count))


if __name__ == "__main__":
    print(generate_password(16, exclude_ambiguous=True))
    print(generate_passphrase(4))
