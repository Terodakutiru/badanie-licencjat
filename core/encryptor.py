# core/encryptor.py

from cryptography.fernet import Fernet
from pathlib import Path

KEY_PATH = Path("secret.key")


def load_or_create_key() -> bytes:
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes()
    else:
        key = Fernet.generate_key()
        KEY_PATH.write_bytes(key)
        return key


def encrypt_file(input_path: str, output_path: str) -> None:
    key = load_or_create_key()
    fernet = Fernet(key)

    with open(input_path, "rb") as f:
        data = f.read()

    encrypted = fernet.encrypt(data)

    with open(output_path, "wb") as f:
        f.write(encrypted)

    print(f"✅ Plik zaszyfrowany jako {output_path}")
