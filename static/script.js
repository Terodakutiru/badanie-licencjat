// static/script.js

const conversation = [
  { sender: "user", text: "Czuję się dziś przytłoczony." },
  { sender: "ai", text: "Rozumiem. Czy możesz opisać, co Cię tak przytłacza?" },
  { sender: "user", text: "Głównie praca i brak odpoczynku." },
  { sender: "ai", text: "To zupełnie zrozumiałe. Jak długo się tak czujesz?" },
  { sender: "user", text: "Od kilku tygodni. Myślę, że potrzebuję przerwy." },
  { sender: "ai", text: "Dbanie o siebie to ważny krok. Może warto zaplanować czas tylko dla siebie." }
];

const chatBox = document.getElementById("chat");
const typing = document.getElementById("typing");
const cert = document.getElementById("cert");
const hashSpan = document.getElementById("hash");
const cidSpan = document.getElementById("cid");

let index = 0;

function showNextMessage() {
  if (index >= conversation.length) {
    sendToServer();
    return;
  }

  const msg = conversation[index];

  if (msg.sender === "ai") {
    typing.style.display = "block";
  }

  setTimeout(() => {
    typing.style.display = "none";
    const bubble = document.createElement("div");
    bubble.className = `bubble ${msg.sender}`;
    bubble.textContent = msg.text;
    chatBox.appendChild(bubble);
    index++;
    showNextMessage();
  }, 1000 + Math.random() * 1000);
}

function sendToServer() {
  const convoText = conversation.map(m => m.text).join(" ");
  fetch("/certify", {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({ conversation: convoText })
  })
    .then(res => res.json())
    .then(data => {
      hashSpan.textContent = data.hash;
      cidSpan.textContent = data.cid;
      cert.style.display = "block";
    })
    .catch(err => {
      cert.innerHTML = `<p style='color:red;'>Błąd certyfikacji: ${err.message}</p>`;
      cert.style.display = "block";
    });
}

showNextMessage();

  async function sendConversation() {
    const chat = document.getElementById('chatInput').value;

    if (!chat.trim()) {
      alert("Wprowadź treść rozmowy.");
      return;
    }

    const response = await fetch("/generate", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ chat })
    });

    const result = await response.json();
    const box = document.getElementById("result");

    if (result.error) {
      box.innerHTML = `<p style='color:red;'>❌ ${result.error}</p>`;
      return;
    }

    box.innerHTML = `
      <p><strong>Hash SHA-256:</strong><br>${result.hash}</p>
      <p><strong>CID certyfikatu:</strong> ${result.cert_cid}<br>
         <a href="${result.ipfs_url_cert}" target="_blank">${result.ipfs_url_cert}</a></p>
      <p><strong>CID rozmowy:</strong> ${result.text_cid}<br>
         <a href="${result.ipfs_url_text}" target="_blank">${result.ipfs_url_text}</a></p>
      <p><img src="/preview" alt="Certyfikat" style="max-width:100%;"></p>
    `;

    // opcjonalnie automatycznie uzupełnij pola:
    document.getElementById('cidCert').value = result.cert_cid;
    document.getElementById('cidText').value = result.text_cid;
  }

  async function decryptCert() {
    const cid = document.getElementById('cidCert').value.trim();
    if (!cid) return alert("Wklej CID certyfikatu.");

    const res = await fetch("/decrypt", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ cid, type: "cert" })
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return alert(err.error || "Błąd odszyfrowania certyfikatu");
    }

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    document.getElementById("decryptResult").innerHTML =
      `<img src="${url}" alt="Odszyfrowany certyfikat" style="max-width:100%;">`;
  }

  async function decryptText() {
    const cid = document.getElementById('cidText').value.trim();
    if (!cid) return alert("Wklej CID rozmowy.");

    const res = await fetch("/decrypt", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify({ cid, type: "text" })
    });

    const data = await res.json().catch(() => ({}));
    if (!res.ok) return alert(data.error || "Błąd odszyfrowania rozmowy");

    document.getElementById("decryptResult").innerText = data.text || "";
  }

  function showTemplatePreview(){
  const box = document.getElementById("certPreviewBox");
  const img = document.getElementById("certPreviewImg");
  img.src = `/preview?mode=template&ts=${Date.now()}`;
  box.style.display = "block";
}
if(GROUP === "CERT"){
  showTemplatePreview();
}
function showRealPreview(){
  const box = document.getElementById("certPreviewBox");
  const img = document.getElementById("certPreviewImg");
  img.src = `/preview?ts=${Date.now()}`;
  box.style.display = "block";
}