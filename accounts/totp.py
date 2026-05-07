"""Pure-stdlib RFC 6238 TOTP + backup-code helpers — no external dep."""
import base64
import hashlib
import hmac
import secrets
import struct
import time

DIGITS = 6
STEP   = 30
ALG    = "SHA1"


def generate_secret(byte_length=20):
    """Return a base32-encoded secret (no padding, uppercase)."""
    return base64.b32encode(secrets.token_bytes(byte_length)).decode("ascii").rstrip("=")


def _b32decode(secret_b32):
    s = secret_b32.upper().replace(" ", "")
    pad = "=" * (-len(s) % 8)
    return base64.b32decode(s + pad)


def code_at(secret_b32, when=None, *, step=STEP, digits=DIGITS):
    if when is None:
        when = time.time()
    counter = int(when // step)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(_b32decode(secret_b32), msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    truncated = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return f"{truncated % (10 ** digits):0{digits}d}"


def verify(secret_b32, token, *, valid_window=1, when=None):
    """Constant-time check across [-valid_window, +valid_window] steps."""
    if not token:
        return False
    cleaned = "".join(ch for ch in token if ch.isdigit())
    if len(cleaned) != DIGITS:
        return False
    if when is None:
        when = time.time()
    for i in range(-valid_window, valid_window + 1):
        candidate = code_at(secret_b32, when + i * STEP)
        if hmac.compare_digest(candidate, cleaned):
            return True
    return False


def provisioning_uri(secret_b32, *, account_name, issuer="Dark Prompt"):
    """Return the otpauth:// URI suitable for QR encoding."""
    from urllib.parse import quote
    label = f"{quote(issuer)}:{quote(account_name)}"
    return (
        f"otpauth://totp/{label}"
        f"?secret={secret_b32}"
        f"&issuer={quote(issuer)}"
        f"&algorithm={ALG}"
        f"&digits={DIGITS}"
        f"&period={STEP}"
    )


# ---------- backup codes ------------------------------------------------

def _hash_code(code: str) -> str:
    normalized = "".join(ch for ch in code.upper() if ch.isalnum())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def generate_backup_codes(count=10):
    """Return a list of human-friendly codes (caller must show them once)."""
    codes = []
    for _ in range(count):
        # 4 + 4 alphanumeric chars, ambiguous chars stripped
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        first  = "".join(secrets.choice(alphabet) for _ in range(4))
        second = "".join(secrets.choice(alphabet) for _ in range(4))
        codes.append(f"{first}-{second}")
    return codes


def hash_codes(raw_codes):
    """Serialize a list of raw codes to the on-disk newline-joined hash blob."""
    return "\n".join(_hash_code(c) for c in raw_codes)


def consume_backup_code(profile, candidate) -> bool:
    """If `candidate` matches one of the stored backup hashes, remove it and return True."""
    if not (profile.backup_codes_hash or "").strip():
        return False
    target = _hash_code(candidate)
    hashes = [h for h in profile.backup_codes_hash.split("\n") if h]
    if target not in hashes:
        return False
    hashes.remove(target)
    profile.backup_codes_hash = "\n".join(hashes)
    profile.save(update_fields=["backup_codes_hash"])
    return True


def remaining_backup_codes(profile) -> int:
    blob = profile.backup_codes_hash or ""
    return len([h for h in blob.split("\n") if h])
