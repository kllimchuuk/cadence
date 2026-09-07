import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHash, VerifyMismatchError

_password_hasher = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)
_DUMMY_HASH = _password_hasher.hash(secrets.token_hex(32))


def hash_password(password: str) -> str:
    return _password_hasher.hash(password)


def verify_password(password: str, hashed_password: str | None) -> bool:
    try:
        _password_hasher.verify(hashed_password or _DUMMY_HASH, password)
    except (VerifyMismatchError, InvalidHash):
        return False
    return True


def password_needs_rehash(hashed_password: str) -> bool:
    return _password_hasher.check_needs_rehash(hashed_password)


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)


def hash_session_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
