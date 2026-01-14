import os
import csv
import hashlib
import json
import random
import secrets
from flask import Flask, request, jsonify, send_file, render_template, redirect, session
from datetime import datetime
from core.cert_builder import build_cert_image
from core.encryptor import encrypt_file
from core.decryptor import decrypt_from_ipfs, decrypt_local
from core.lighthouse_storage import upload_file_to_lighthouse as upload_to_ipfs
from core.nft_storage import create_collection, get_collection_id_by_name, upload_tokens_csv
from dotenv import load_dotenv
load_dotenv()

CERT_INDEX_PATH = "cert_index.json"

def _load_cert_index():
    if not os.path.exists(CERT_INDEX_PATH):
        return {}
    with open(CERT_INDEX_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:
            return {}

def _save_cert_index(idx: dict):
    with open(CERT_INDEX_PATH, "w", encoding="utf-8") as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)

def remember_cert_record(token_id: str, cert_cid: str, text_cid: str):
    """
    Zapisuje mapowanie token_id (hash) ->:
    - offline: ścieżki lokalne do *.encrypted
    - online: CID-y do IPFS
    Dzięki temu możemy pobierać cert zawsze po /download/.../by-hash/<token_id>
    """
    idx = _load_cert_index()

    rec = {
        "ts": datetime.utcnow().isoformat(),
        "cert_cid": "",
        "text_cid": "",
        "certificate_encrypted": "",
        "conversation_encrypted": "",
    }

    if cert_cid.startswith("local:"):
        rec["certificate_encrypted"] = os.path.abspath(cert_cid.replace("local:", "", 1))
    else:
        rec["cert_cid"] = cert_cid

    if text_cid.startswith("local:"):
        rec["conversation_encrypted"] = os.path.abspath(text_cid.replace("local:", "", 1))
    else:
        rec["text_cid"] = text_cid

    idx[token_id] = rec
    _save_cert_index(idx)

# ---------------------------
# IPFS: tryb online/offline
# ---------------------------
IPFS_MODE = os.getenv("IPFS_MODE", "lighthouse").lower()

def safe_upload(path: str) -> str:
    """Zwraca prawdziwy CID (online) lub local:... (offline / fallback)."""
    if IPFS_MODE == "offline":
        print("🟡 IPFS offline, zapis lokalny:", path)
        return f"local:{os.path.abspath(path)}"

    try:
        return upload_to_ipfs(path)
    except Exception as e:
        print("⚠️ IPFS upload failed, fallback local:", e)
        return f"local:{os.path.abspath(path)}"


app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY") or os.getenv("FLASK_SECRET") or "dev-secret-change-me"

def canonicalize_messages(messages):
    return json.dumps(messages, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

def certify_messages(messages):
    chat_text = canonicalize_messages(messages)
    token_id = hashlib.sha256(chat_text.encode("utf-8")).hexdigest()

    build_cert_image(token_id, output_path="certificate.png")

    with open("conversation.txt", "w", encoding="utf-8") as f:
        f.write(chat_text)

    encrypt_file("certificate.png", "certificate.encrypted")
    encrypt_file("conversation.txt", "conversation.encrypted")

    cert_cid = upload_to_ipfs("certificate.encrypted")
    text_cid = upload_to_ipfs("conversation.encrypted")

    return token_id, cert_cid, text_cid

@app.route("/")
def index():
    return render_template("home.html")

@app.route("/tool")
def tool():
    return render_template("index.html")

@app.route("/generate", methods=["POST"])
def generate():
    data = request.get_json(force=True)
    chat = (data.get("chat") or "").strip()
    if not chat:
        return jsonify({"error": "Brak treści rozmowy"}), 400

    # 1) token_id = SHA256 rozmowy
    token_id = hashlib.sha256(chat.encode("utf-8")).hexdigest()

    # 2) cert png
    build_cert_image(token_id, output_path="certificate.png")

    # 3) rozmowa -> txt
    with open("conversation.txt", "w", encoding="utf-8") as f:
        f.write(chat)

    # 4) szyfrowanie
    encrypt_file("certificate.png", "certificate.encrypted")
    encrypt_file("conversation.txt", "conversation.encrypted")

    # 5) upload (CID online lub local:... offline)
    cert_cid = safe_upload("certificate.encrypted")
    text_cid = safe_upload("conversation.encrypted")

    # 6) CSV do NFT.Storage (tylko jeśli CID jest prawdziwy)
    collection_id = None
    if not cert_cid.startswith("local:"):
        csv_path = "token_upload.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(["tokenID", "cid"])
            writer.writerow([token_id, cert_cid])

        collection_name = os.getenv("COLLECTION_NAME")
        try:
            collection_id = get_collection_id_by_name(collection_name)
        except ValueError:
            response = create_collection()
            collection_id = response.get("collectionID") or response.get("value", {}).get("collectionID")

        upload_tokens_csv(collection_id, csv_path)
    else:
        print("🟡 Tryb offline – pomijam NFT.Storage (bo CID nie jest prawdziwy).")

    return jsonify({
        "hash": token_id,
        "collection_id": collection_id,

        "cert_cid": cert_cid,
        "text_cid": text_cid,

        # linki tylko mają sens dla prawdziwych CID, ale zostawiamy dla spójności:
        "ipfs_url_cert": f"https://gateway.lighthouse.storage/ipfs/{cert_cid}",
        "ipfs_url_text": f"https://gateway.lighthouse.storage/ipfs/{text_cid}",
    })



@app.route("/decrypt", methods=["POST"])
def decrypt():
    data = request.get_json(force=True)
    cid = (data.get("cid") or "").strip()
    dtype = (data.get("type") or "text").strip().lower()

    if not cid:
        return jsonify({"error": "Brak CID"}), 400

    try:
        if dtype == "cert":
            output_path = "certificate_decrypted.png"
            if cid.startswith("local:"):
                enc_path = cid.replace("local:", "", 1)
                out = decrypt_local(enc_path, output_path)
            else:
                out = decrypt_from_ipfs(cid, output_path=output_path)
            return send_file(out, mimetype="image/png")

        # default: text
        output_path = "conversation_decrypted.txt"
        if cid.startswith("local:"):
            enc_path = cid.replace("local:", "", 1)
            out = decrypt_local(enc_path, output_path)
        else:
            out = decrypt_from_ipfs(cid, output_path=output_path)

        with open(out, "r", encoding="utf-8") as f:
            text = f.read()
        return jsonify({"text": text})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/download/cert/by-hash/<token_id>")
def download_cert_by_hash(token_id):
    idx = _load_cert_index()
    rec = idx.get(token_id)
    if not rec:
        return jsonify({"error": "Nie znam tego hasha (brak rekordu w cert_index.json)."}), 404

    # OFFLINE
    cert_path = (rec.get("certificate_encrypted") or "").strip()
    if cert_path and os.path.exists(cert_path):
        out = decrypt_local(cert_path, output_path="certificate_download.png")
        return send_file(out, mimetype="image/png", as_attachment=True, download_name="certificate.png")

    # ONLINE
    cid = (rec.get("cert_cid") or "").strip()
    if cid:
        out = decrypt_from_ipfs(cid, output_path="certificate_download.png")
        return send_file(out, mimetype="image/png", as_attachment=True, download_name="certificate.png")

    return jsonify({"error": "Rekord istnieje, ale nie ma ani ścieżki offline ani CID online."}), 404

@app.route("/verify/by-hash/<token_id>")
def verify_by_hash(token_id):
    idx = _load_cert_index()
    rec = idx.get(token_id, {})
    prefill = rec.get("cert_cid", "") or ""
    return render_template("verify.html", cert_cid=prefill)
@app.route("/api/certify", methods=["POST"])
def api_certify():
    data = request.get_json(force=True)

    # 1) przyjmujemy albo chat, albo messages[]
    chat = (data.get("chat") or "").strip()

    if not chat:
        msgs = data.get("messages") or []
        if isinstance(msgs, list) and msgs:
            # sklejamy transcript do jednego tekstu (stabilne i powtarzalne)
            lines = []
            for m in msgs:
                role = m.get("role", "unknown")
                content = (m.get("content") or "").strip()
                if content:
                    lines.append(f"{role.upper()}: {content}")
            chat = "\n".join(lines).strip()

    if not chat:
        return jsonify({"error": "Brak treści rozmowy"}), 400

    token_id = hashlib.sha256(chat.encode("utf-8")).hexdigest()

    build_cert_image(token_id, output_path="certificate.png")

    with open("conversation.txt", "w", encoding="utf-8") as f:
        f.write(chat)

    encrypt_file("certificate.png", "certificate.encrypted")
    encrypt_file("conversation.txt", "conversation.encrypted")

    cert_cid = safe_upload("certificate.encrypted")
    text_cid = safe_upload("conversation.encrypted")

    # KROK 5 (Twoje): zapisz mapowanie hash -> (CID lub local path)
    remember_cert_record(token_id, cert_cid, text_cid)

    log_event({
        "ts": datetime.utcnow().isoformat(),
        "participant_id": session.get("participant_id", ""),
        "group": session.get("group", ""),
        "event": "certify",
        "hash": token_id,
        "cert_cid": cert_cid,
        "text_cid": text_cid
    })

    return jsonify({
        "hash": token_id,
        "cert_cid": cert_cid,
        "text_cid": text_cid,
        "download_url": f"/download/cert/by-hash/{token_id}",
        "verify_url": f"/verify/by-hash/{token_id}",
        "cert_ipfs_url": "" if cert_cid.startswith("local:") else f"https://gateway.lighthouse.storage/ipfs/{cert_cid}",
        "text_ipfs_url": "" if text_cid.startswith("local:") else f"https://gateway.lighthouse.storage/ipfs/{text_cid}",
    })
@app.route("/download/cert/<cid>")
def download_cert(cid):
    # jeśli offline: CID wygląda jak local:/abs/path/...
    if cid.startswith("local:"):
        enc_path = cid.replace("local:", "", 1)
        out = decrypt_local(enc_path, output_path="certificate_download.png")
        return send_file(out, mimetype="image/png", as_attachment=True, download_name="certificate.png")

    # online: pobierz z IPFS i odszyfruj
    out = decrypt_from_ipfs(cid, output_path="certificate_download.png")
    return send_file(out, mimetype="image/png", as_attachment=True, download_name="certificate.png")
@app.route("/verify")
def verify_page_empty():
    # strona weryfikacji bez wstępnego CID (użytkownik wklei ręcznie)
    return render_template("verify.html", cert_cid="")
@app.route("/verify/<cid>")
def verify_page(cid):
    return render_template("verify.html", cert_cid=cid)
@app.route("/preview")
def preview():
    mode = (request.args.get("mode") or "").lower()

    if mode == "template":
        # generujemy wersję preview (placeholdery)
        build_cert_image("preview", output_path="certificate_template.png", preview=True)
        return send_file("certificate_template.png", mimetype="image/png")

    # domyślnie pokazujemy prawdziwy cert
    return send_file("certificate.png", mimetype="image/png")
@app.route("/study")
def study():
    if "participant_id" not in session:
        session["participant_id"] = secrets.token_hex(8)

    forced = (request.args.get("group") or "").upper().strip()
    if forced in ["CONTROL", "CERT", "AUTH"]:
        session["group"] = forced
    elif "group" not in session:
        session["group"] = random.choice(["CONTROL", "CERT", "AUTH"])

    log_event({
        "ts": datetime.utcnow().isoformat(),
        "participant_id": session["participant_id"],
        "group": session["group"],
        "event": "study_start",
        "hash": "",
        "cert_cid": "",
        "text_cid": ""
    })
    return render_template("study.html", group=session["group"])

@app.route("/survey")
def survey():
    pid = request.args.get("pid") or session.get("participant_id", "")
    grp = request.args.get("group") or session.get("group", "")
    return render_template("survey.html", pid=pid, group=grp)

@app.route("/debrief")
def debrief():
    # możesz przekazać pid/grupę jeśli chcesz to wyświetlać w treści
    pid = request.args.get("pid") or session.get("participant_id", "")
    grp = request.args.get("group") or session.get("group", "")
    return render_template("debrief.html", pid=pid, group=grp)

@app.route("/reset")
def reset():
    session.clear()
    return "OK, session cleared. Odśwież /study."

LOG_PATH = "study_log.csv"

def log_event(event: dict):
    is_new = not os.path.exists(LOG_PATH)
    with open(LOG_PATH, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "ts","participant_id","group","event","hash","cert_cid","text_cid"
        ])
        if is_new:
            w.writeheader()
        w.writerow(event)

SURVEY_URL = os.getenv("SURVEY_URL", "/survey")
@app.route("/finish")
def finish():
    pid = session.get("participant_id", "")
    grp = session.get("group", "")
    # parametry do ankiety (query params)
    return redirect(f"{SURVEY_URL}?pid={pid}&group={grp}")

SURVEY_LOG_PATH = "survey_responses.csv"
@app.route("/api/survey", methods=["POST"])
def api_survey():
    try:
        data = request.get_json(force=True)

        pid = (data.get("participant_id") or "").strip()
        grp = (data.get("group") or "").strip()
        answers = data.get("answers") or {}
        order = data.get("order") or []
        open_text = (data.get("open_text") or "").strip()
        ts = (data.get("ts") or datetime.utcnow().isoformat())

        if not pid or not grp:
            return jsonify({"error": "Brak participant_id lub group"}), 400

        # prosta walidacja: czy są wszystkie pytania
        required = [f"q{i}" for i in range(1, 11)] + ["mc1", "mc2"]
        for k in required:
            if k not in answers or str(answers[k]).strip() == "":
                return jsonify({"error": f"Brak odpowiedzi dla {k}"}), 400

        is_new = not os.path.exists(SURVEY_LOG_PATH)
        with open(SURVEY_LOG_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=[
                "ts", "participant_id", "group",
                "q1","q2","q3","q4","q5","q6","q7","q8","q9","q10",
                "mc1","mc2",
                "open_text",
                "order_json"
            ])
            if is_new:
                w.writeheader()

            row = {
                "ts": ts,
                "participant_id": pid,
                "group": grp,
                "open_text": open_text,
                "order_json": json.dumps(order, ensure_ascii=False),
            }
            for k in required:
                row[k] = answers.get(k)

            w.writerow(row)

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
if __name__ == "__main__":
    app.run(debug=True)
