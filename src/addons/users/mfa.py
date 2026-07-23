"""Native MFA utilities: TOTP (RFC 6238) + secret encryption at rest.

No third-party OTP dependency (pyotp): the HOTP/TOTP math is ~40 lines of
stdlib hmac/struct. The TOTP secret is encrypted with Fernet using a
**dedicated** key (settings.MFA_ENCRYPTION_KEY) so rotating SECRET_KEY does
not lock every 2FA user out.

Design: analisis-mfa-totp-nativo, analisis-utilidad-totp-nativa-kaupamex
(T-PLT-33; UC-PLT-08 enrolls the factor, UC-AUTH-02 consumes it at login).
"""
import base64
import hashlib
import hmac
import os
import secrets
import struct
import time
from urllib.parse import quote, urlencode

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

TOTP_STEP_SECONDS = 30
TOTP_DIGITS = 6
TOTP_SECRET_BYTES = 20  # 160 bits, SHA-1 recommended (RFC 4226)


class MfaCryptoError(Exception):
    """Raised when the TOTP secret cannot be decrypted (key absent/rotated,
    or corrupt blob). Callers must fail closed -- never degrade to no-2FA."""


def generate_totp_secret(nbytes: int = TOTP_SECRET_BYTES) -> str:
    """Return a fresh base32 TOTP secret (uppercase, unpadded-safe)."""
    return base64.b32encode(os.urandom(nbytes)).decode("ascii")


RECOVERY_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I,O,0,1
RECOVERY_CODE_GROUP = 5


def _recovery_group() -> str:
    return "".join(secrets.choice(RECOVERY_CODE_ALPHABET)
                   for _ in range(RECOVERY_CODE_GROUP))


def generate_recovery_codes(count: int = 8) -> list[str]:
    """Return ``count`` unique single-use recovery codes ("xxxxx-xxxxx").

    Alphabet excludes visually ambiguous chars (I/O/0/1). Codes are the
    plaintext shown once to the user; the device stores only their hashes.
    """
    codes: set[str] = set()
    while len(codes) < count:
        codes.add(f"{_recovery_group()}-{_recovery_group()}")
    return list(codes)


def _hotp(secret_b32: str, counter: int, digits: int) -> str:
    key = base64.b32decode(_pad_b32(secret_b32), casefold=True)
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    binary = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(binary % (10 ** digits)).zfill(digits)


def _pad_b32(secret_b32: str) -> str:
    s = secret_b32.strip().replace(" ", "").upper()
    pad = (-len(s)) % 8
    return s + ("=" * pad)


def totp_at(secret_b32: str, timestamp: float | None = None,
            step: int = TOTP_STEP_SECONDS, digits: int = TOTP_DIGITS) -> str:
    """Compute the TOTP code for a given unix timestamp (now if None)."""
    if timestamp is None:
        timestamp = time.time()
    counter = int(timestamp // step)
    return _hotp(secret_b32, counter, digits)


def verify_totp(secret_b32: str, code: str, timestamp: float | None = None,
                step: int = TOTP_STEP_SECONDS, digits: int = TOTP_DIGITS,
                window: int = 1) -> bool:
    """Validate ``code`` against the secret within +/- ``window`` steps."""
    if not code or not code.isdigit():
        return False
    if timestamp is None:
        timestamp = time.time()
    counter = int(timestamp // step)
    for drift in range(-window, window + 1):
        candidate = _hotp(secret_b32, counter + drift, digits)
        if hmac.compare_digest(candidate, code):
            return True
    return False


def provisioning_uri(secret_b32: str, account_name: str,
                     issuer: str = "Kaupamex") -> str:
    """Build the ``otpauth://`` URI for QR provisioning."""
    label = quote(f"{issuer}:{account_name}")
    params = urlencode({
        "secret": secret_b32,
        "issuer": issuer,
        "algorithm": "SHA1",
        "digits": TOTP_DIGITS,
        "period": TOTP_STEP_SECONDS,
    })
    return f"otpauth://totp/{label}?{params}"


def _mfa_fernet_key() -> bytes:
    """Fernet key derived from the DEDICATED MFA_ENCRYPTION_KEY (not
    SECRET_KEY). Same mechanism as settings_app._fernet_key, different source.
    """
    raw = settings.MFA_ENCRYPTION_KEY.encode()
    digest = hashlib.sha256(raw).digest()
    return base64.urlsafe_b64encode(digest)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a TOTP secret for storage at rest."""
    token = Fernet(_mfa_fernet_key()).encrypt(plaintext.encode())
    return token.decode("ascii")


def decrypt_secret(blob: str) -> str:
    """Decrypt a stored TOTP secret; raise MfaCryptoError on any failure."""
    try:
        return Fernet(_mfa_fernet_key()).decrypt(blob.encode()).decode()
    except (InvalidToken, ValueError, TypeError) as exc:
        raise MfaCryptoError("TOTP secret not decryptable") from exc
