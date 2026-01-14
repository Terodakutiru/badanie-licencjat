# core/nft_storage.py
import os
import csv
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://preserve.nft.storage/api/v1"
API_KEY = os.getenv("NFT_STORAGE_TOKEN")
HEADERS_JSON = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json"
}
HEADERS_AUTH = {
    "Authorization": f"Bearer {API_KEY}"
}


def create_collection(contract_address=None, collection_name=None, chain_id=None, network=None):
    data = {
        "contractAddress": contract_address or os.getenv("CONTRACT_ADDRESS"),
        "collectionName": collection_name or os.getenv("COLLECTION_NAME"),
        "chainID": chain_id or os.getenv("CHAIN_ID"),
        "network": network or os.getenv("NETWORK")
    }
    url = f"{API_URL}/collection/create_collection"
    response = requests.post(url, headers=HEADERS_JSON, json=data)
    if response.ok:
        print("✅ Kolekcja utworzona.")
        return response.json()
    else:
        print("❌ Błąd przy tworzeniu kolekcji:", response.text)
        raise Exception(response.text)


def list_collections():
    url = f"{API_URL}/collection/list_collections"
    response = requests.get(url, headers=HEADERS_AUTH)
    if response.ok:
        return response.json()
    else:
        raise Exception(response.text)


def get_collection_id_by_name(name: str):
    collections = list_collections()
    for col in collections.get("collections", []):
        if col["collectionName"] == name:
            return col["collectionID"]
    raise ValueError("Kolekcja nie istnieje.")


def save_csv_token(token_id: int, cid: str, path: str = "upload.csv"):
    with open(path, mode="w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["tokenID", "cid"])
        writer.writerow([token_id, cid])
    print("📄 CSV wygenerowany:", path)
    return path


def upload_tokens_csv(collection_id: str, csv_path: str):
    import mimetypes

    url = f"{API_URL}/collection/add_tokens"

    # Podgląd dla debugowania
    print(f"➡️ Uploading: {csv_path}")
    print(f"➡️ Collection ID: {collection_id}")

    # Otwórz plik
    with open(csv_path, 'rb') as file:
        files = {
            'collectionID': (None, collection_id),
            'file': (os.path.basename(csv_path), file, 'text/csv')
        }

        headers = {
            'Authorization': f'Bearer {API_KEY}'
        }

        response = requests.post(url, headers=headers, files=files)

    if response.ok:
        print("✅ CSV przesłany pomyślnie.")
        return response.json()
    else:
        print(f"❌ Błąd przy uploadzie CSV: {response.status_code} - {response.text}")
        raise Exception(response.text)