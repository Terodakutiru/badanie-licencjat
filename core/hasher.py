# core/hasher.py

import hashlib

def hash_conversation(text: str) -> str:
    """
    Zwraca hash SHA-256 rozmowy w postaci heksadecymalnej.
    """
    text = text.strip().encode("utf-8")
    return hashlib.sha256(text).hexdigest()