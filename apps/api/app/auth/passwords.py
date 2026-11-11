"""Password hashing (Argon2id) and the rules a new password must meet (ADR-021).

The rules follow NIST SP 800-63B: length over composition, and no password that is
common or made from the account's own name or e-mail.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

MIN_LENGTH, MAX_LENGTH = 10, 128

# OWASP / argon2-cffi defaults for Argon2id (RFC 9106 low-memory profile).
_hasher = PasswordHasher()

# A valid hash to verify against when the account does not exist, so the answer takes
# the same time either way (no account enumeration by timing).
_DUMMY = _hasher.hash("smash-hub-dummy-password")

COMMON = {
    "1234567890",
    "12345678910",
    "0123456789",
    "contraseña",
    "contrasena",
    "contraseña123",
    "password",
    "password123",
    "password1234",
    "qwertyuiop",
    "qwerty12345",
    "asdfghjkl1",
    "1q2w3e4r5t",
    "iloveyou12",
    "smashbros1",
    "smashbros123",
    "smashultimate",
    "supersmashbros",
    "paraguay123",
    "abcdefghij",
    "abc1234567",
    "1111111111",
    "aaaaaaaaaa",
}


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify(password_hash: str | None, password: str) -> bool:
    """Constant-ish time: an account without a hash still pays for one verification."""
    try:
        return _hasher.verify(password_hash or _DUMMY, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True


def problem(password: str, *, username: str = "", email: str = "") -> str | None:
    """Why a new password is not accepted, or None when it is fine."""
    if len(password) < MIN_LENGTH:
        return f"La contraseña necesita al menos {MIN_LENGTH} caracteres."
    if len(password) > MAX_LENGTH:
        return f"La contraseña puede tener hasta {MAX_LENGTH} caracteres."
    lowered = password.lower()
    if lowered in COMMON or len(set(lowered)) <= 2:
        return "Esa contraseña es demasiado común. Probá con una frase más larga."
    local = email.split("@")[0].lower() if email else ""
    for own in (username.lower(), local):
        if own and len(own) >= 3 and own in lowered:
            return "La contraseña no puede contener tu usuario ni tu correo."
    return None
