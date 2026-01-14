import os
import requests
from cryptography.fernet import Fernet


def decrypt_from_ipfs(cid: str, output_path: str = "conversation_decrypted.txt", key_path: str = "secret.key") -> str:
    """
    Pobiera zaszyfrowany plik z IPFS i odszyfrowuje go lokalnie.
    Obsługuje automatycznie tryb tekstowy (.txt) lub binarny (.png, inne).
    """
    # 1. Pobierz zaszyfrowany plik z IPFS
    url = f"https://gateway.lighthouse.storage/ipfs/{cid}"
    print(f"🌐 Pobieranie z IPFS: {url}")
    response = requests.get(url)
    if not response.ok:
        raise Exception(f"❌ Błąd pobierania IPFS: {response.status_code} – {response.text}")

    encrypted_data = response.content

    # 2. Wczytaj klucz
    if not os.path.exists(key_path):
        raise FileNotFoundError("Brak pliku secret.key – nie można odszyfrować")

    with open(key_path, "rb") as key_file:
        key = key_file.read()

    fernet = Fernet(key)

    # 3. Deszyfrowanie
    decrypted_data = fernet.decrypt(encrypted_data)

    # 4. Zapis jako tekst lub binarnie
    if output_path.endswith(".txt"):
        with open(output_path, "w", encoding="utf-8") as out_file:
            out_file.write(decrypted_data.decode("utf-8"))
    else:
        with open(output_path, "wb") as out_file:
            out_file.write(decrypted_data)

    print(f"✅ Zapisano odszyfrowaną treść do: {output_path}")
    return output_path

def decrypt_local(path: str, output_path: str = "conversation_decrypted.txt", key_path: str = "secret.key") -> str:
    if not os.path.exists(path):
        raise FileNotFoundError(path)

    with open(path, "rb") as f:
        encrypted_data = f.read()

    if not os.path.exists(key_path):
        raise FileNotFoundError("Brak pliku secret.key – nie można odszyfrować")

    with open(key_path, "rb") as key_file:
        key = key_file.read()

    fernet = Fernet(key)
    decrypted_data = fernet.decrypt(encrypted_data)

    if output_path.endswith(".txt"):
        with open(output_path, "w", encoding="utf-8") as out_file:
            out_file.write(decrypted_data.decode("utf-8"))
    else:
        with open(output_path, "wb") as out_file:
            out_file.write(decrypted_data)

    return output_path