from __future__ import annotations

import base64
import logging
import os
from pathlib import Path
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_encryption_key: bytes | None = None

# The fallback key is derived from these two constants, which are public in the source.
# It keeps local demos working across restarts and gives no protection: set ENCRYPTION_KEY
# (a Fernet key) anywhere real documents are stored.
_DEFAULT_KEY_PASSWORD = b"default_key_change_in_production"
_DEFAULT_KEY_SALT = b"renewal-desk-demo-salt"

# A stored file is base64 of a Fernet token, and every Fernet token starts with "gAAAAA".
_STORED_PREFIX = "Z0FBQUFB"


def get_encryption_key() -> bytes:
    global _encryption_key
    if _encryption_key is None:
        key_env = os.environ.get("ENCRYPTION_KEY")
        if key_env:
            _encryption_key = key_env.encode()
        else:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=_DEFAULT_KEY_SALT,
                iterations=100000,
            )
            _encryption_key = base64.urlsafe_b64encode(kdf.derive(_DEFAULT_KEY_PASSWORD))
            logger.warning("Using the default encryption key. Set ENCRYPTION_KEY wherever real documents are stored.")

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


def read_text(path: Path) -> str:
    """Read a stored text file and decrypt it when it was stored encrypted.

    The object store encrypts uploaded `.txt` and `.csv` files. Files that are not
    encrypted, such as the files in `examples/`, are returned as they are.
    """
    raw = path.read_text(encoding="utf-8", errors="ignore")
    if not raw.startswith(_STORED_PREFIX):
        return raw
    try:
        return decrypt_data(raw.strip())
    except Exception as exc:
        logger.warning("Could not decrypt %s; is ENCRYPTION_KEY the key used at upload? (%s)", path, exc)
        return raw
