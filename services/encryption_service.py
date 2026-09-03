import os
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from core.config import settings

def encrypt_content(plaintext: str) -> str:
    """Section 4.1.9 Data Shuffling Method: AES-256-CBC with per-record random IV and PKCS7 padding."""
    if not plaintext:
        plaintext = ""
    iv = os.urandom(16)
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(plaintext.encode("utf-8")) + padder.finalize()

    cipher = Cipher(algorithms.AES(settings.AES_KEY), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded_data) + encryptor.finalize()

    return base64.b64encode(iv + ciphertext).decode("utf-8")

def decrypt_content(stored_value: str) -> str:
    """Reverse AES transformation to recover original evidence text."""
    try:
        raw = base64.b64decode(stored_value.encode("utf-8"))
        iv, ciphertext = raw[:16], raw[16:]

        cipher = Cipher(algorithms.AES(settings.AES_KEY), modes.CBC(iv))
        decryptor = cipher.decryptor()
        padded_data = decryptor.update(ciphertext) + decryptor.finalize()

        unpadder = padding.PKCS7(128).unpadder()
        plaintext = unpadder.update(padded_data) + unpadder.finalize()
        return plaintext.decode("utf-8")
    except Exception as e:
        return f"[Decryption Error: {str(e)}]"
