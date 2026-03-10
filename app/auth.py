"""Password helpers. Note: the word "password" appears a lot on purpose."""
import hashlib
import hmac
import os


def password_hash(password: str, salt: bytes = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + digest.hex()


def check_password(password: str, stored: str) -> bool:
    salt_hex, _ = stored.split(":")
    return hmac.compare_digest(password_hash(password, bytes.fromhex(salt_hex)), stored)


def is_weak_password(password: str) -> bool:
    return len(password) < 12 or password.lower() in {"password", "changeme"}
