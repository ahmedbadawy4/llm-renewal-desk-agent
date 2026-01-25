from __future__ import annotations

import base64
import logging
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_encryption_key: bytes | None = None


def get_encryption_key() -> bytes:
    global _encryption_key
    if _encryption_key is None:
        key_env = os.environ.get("ENCRYPTION_KEY")
        if key_env:
            _encryption_key = key_env.encode()
        else:
            salt = os.urandom(16)
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            _encryption_key = base64.urlsafe_b64encode(kdf.derive(b"default_key_change_in_production"))
            logger.warning("Using default encryption key. Set ENCRYPTION_KEY in production!")

    return _encryption_key


def encrypt_data(data: str) -> str:
    key = get_encryption_key()
    f = Fernet(key)
    encrypted = f.encrypt(data.encode())
    return base64.urlsafe_b64encode(encrypted).decode()


def decrypt_data(encrypted_data: str) -> str:
    key = get_encryption_key()
    f = Fernet(key)
    encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
    decrypted = f.decrypt(encrypted_bytes)
    return decrypted.decode()
