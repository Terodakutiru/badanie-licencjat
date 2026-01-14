import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_TOKEN = (os.getenv("LIGHTHOUSE_TOKEN") or "").strip().strip('"').strip("'")

# node.* u Ciebie timeoutuje, więc od razu używamy upload.*
API_URL = "https://upload.lighthouse.storage/api/v0/add"


def _try_upload(path: str, headers: dict) -> requests.Response:
    with open(path, "rb") as f:
        files = {"file": (os.path.basename(path), f)}
        return requests.post(
            API_URL,
            headers=headers,
            files=files,
            timeout=60,
        )


def upload_file_to_lighthouse(path: str) -> str:
    """
    Upload do Lighthouse -> zwraca CID.
    Próbuje kilku formatów autoryzacji, bo Lighthouse lubi je zmieniać.
    """
    if not API_TOKEN:
        raise RuntimeError("Brak LIGHTHOUSE_TOKEN w .env (albo .env nie jest ładowany).")

    # dla debug:
    print("🔐 LIGHTHOUSE_TOKEN loaded:", True, "len:", len(API_TOKEN))

    header_variants = [
        # wariant 1: Bearer
        {"Authorization": f"Bearer {API_TOKEN}", "Accept": "application/json", "User-Agent": "python-requests"},
        # wariant 2: bez Bearer
        {"Authorization": API_TOKEN, "Accept": "application/json", "User-Agent": "python-requests"},
        # wariant 3: X-API-KEY
        {"X-API-KEY": API_TOKEN, "Accept": "application/json", "User-Agent": "python-requests"},
    ]

    last_err = None

    for headers in header_variants:
        try:
            resp = _try_upload(path, headers=headers)
        except requests.RequestException as e:
            last_err = e
            continue

        if resp.ok:
            data = resp.json()
            cid = data.get("Hash") or data.get("cid")
            if not cid:
                raise RuntimeError(f"Upload OK, ale nie znalazłem CID w odpowiedzi: {data}")
            print("✅ Uploaded to Lighthouse CID:", cid)
            return cid

        # 403/401 itd.
        last_err = RuntimeError(f"{resp.status_code} - {resp.text}")

    raise RuntimeError(f"Nie udało się uploadować do Lighthouse. Ostatni błąd: {last_err}")
