from __future__ import annotations

import base64
import json
import os
from typing import Any, Dict, Union
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def _derive_key(key_material: Union[str, bytes]) -> bytes:
    """Derives a strict 32-byte (256-bit) AES key from input string or bytes."""
    if isinstance(key_material, str):
        # If 64-char hex string, decode directly
        if len(key_material.strip()) == 64:
            try:
                return bytes.fromhex(key_material.strip())
            except ValueError:
                pass
        raw = key_material.encode("utf-8")
    else:
        raw = key_material

    import hashlib
    return hashlib.sha256(raw).digest()


def encrypt_payload(
    data: Union[Dict[str, Any], str],
    key: Union[str, bytes],
) -> tuple[str, str, str]:
    """Encrypts data using AES-256-GCM.
    
    Returns:
        (ciphertext_b64, nonce_b64, tag_b64)
        Note: AESGCM in cryptography appends the 16-byte authentication tag to ciphertext.
        We separate them for clean DB storage and standard auditability.
    """
    key_bytes = _derive_key(key)
    aesgcm = AESGCM(key_bytes)
    nonce = os.urandom(12)  # 96-bit standard nonce for GCM

    if isinstance(data, (dict, list)):
        payload_bytes = json.dumps(data, ensure_ascii=False).encode("utf-8")
    else:
        payload_bytes = str(data).encode("utf-8")

    # AESGCM.encrypt returns ciphertext + 16-byte tag
    encrypted = aesgcm.encrypt(nonce, payload_bytes, associated_data=None)
    ciphertext = encrypted[:-16]
    tag = encrypted[-16:]

    return (
        base64.b64encode(ciphertext).decode("ascii"),
        base64.b64encode(nonce).decode("ascii"),
        base64.b64encode(tag).decode("ascii"),
    )


def decrypt_payload(
    ciphertext_b64: str,
    nonce_b64: str,
    tag_b64: str,
    key: Union[str, bytes],
) -> Union[Dict[str, Any], str]:
    """Decrypts AES-256-GCM encrypted payload and parses JSON if applicable."""
    key_bytes = _derive_key(key)
    aesgcm = AESGCM(key_bytes)

    ciphertext = base64.b64decode(ciphertext_b64.encode("ascii"))
    nonce = base64.b64decode(nonce_b64.encode("ascii"))
    tag = base64.b64decode(tag_b64.encode("ascii"))

    combined = ciphertext + tag
    decrypted_bytes = aesgcm.decrypt(nonce, combined, associated_data=None)
    decrypted_str = decrypted_bytes.decode("utf-8")

    try:
        return json.loads(decrypted_str)
    except Exception:
        return decrypted_str
