# core/ipfs_uploader.py
import requests
import os

WEB3_API = "https://api.web3.storage/upload"
WEB3_TOKEN = os.getenv("WEB3_STORAGE_TOKEN")

def upload_to_ipfs(file_path: str) -> str:
    headers = {
        "Authorization": f"Bearer {WEB3_TOKEN}"
    }

    with open(file_path, "rb") as f:
        files = {'file': (os.path.basename(file_path), f)}
        response = requests.post(WEB3_API, headers=headers, files=files)

    if response.ok:
        cid = response.json()["cid"]
        print("✅ CID z Web3.Storage:", cid)
        return cid
    else:
        print("❌ Błąd uploadu:", response.status_code, response.text)
        raise Exception(response.text)