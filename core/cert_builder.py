from PIL import Image, ImageDraw, ImageFont
from datetime import datetime
import qrcode
import os

def _load_font(size: int, weight: str = "Regular"):
    font_path = os.path.join("static", "fonts", f"Inter-{weight}.ttf")
    if os.path.exists(font_path):
        return ImageFont.truetype(font_path, size)

    # fallback Windows (jak testujesz lokalnie)
    for path in ("arial.ttf", "C:/Windows/Fonts/arial.ttf"):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            pass

    return ImageFont.load_default()

def _rounded_rectangle(draw, xy, radius, fill, outline=None, width=1):
    try:
        draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)
    except Exception:
        draw.rectangle(xy, fill=fill, outline=outline, width=width)


def _wrap_text_lines(text: str, max_chars: int):
    """
    Proste łamanie po znakach (bez mierzenia szerokości fontem).
    Działa OK dla Twojego fontu/rozmiaru i krótkich linii.
    """
    words = text.split()
    lines = []
    cur = ""
    for w in words:
        if len(cur) + len(w) + 1 <= max_chars:
            cur = (cur + " " + w).strip()
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def build_cert_image(hash_hex: str, output_path: str = "certificate.png", preview: bool = False):
    # A4-ish @ ~150dpi
    W, H = 1240, 1754
    img = Image.new("RGB", (W, H), (10, 16, 32))
    draw = ImageDraw.Draw(img)

    # Background gradient (subtle)
    for y in range(H):
        t = y / (H - 1)
        r = int(11 + 25 * t)
        g = int(18 + 20 * t)
        b = int(35 + 35 * t)
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    # Decorative glow
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse((-250, -250, 700, 700), fill=(124, 92, 255, 80))
    gdraw.ellipse((700, -200, 1500, 600), fill=(46, 229, 157, 55))
    img = Image.alpha_composite(img.convert("RGBA"), glow).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Card area
    margin = 90
    card = (margin, 110, W - margin, H - 110)
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sdraw = ImageDraw.Draw(shadow)
    _rounded_rectangle(sdraw, (card[0] + 10, card[1] + 14, card[2] + 10, card[3] + 14), 24, fill=(0, 0, 0, 140))
    img = Image.alpha_composite(img.convert("RGBA"), shadow).convert("RGB")
    draw = ImageDraw.Draw(img)

    _rounded_rectangle(draw, card, 24, fill=(18, 26, 51), outline=(255, 255, 255), width=2)

    # Fonts
    title = _load_font(52, "SemiBold")
    h1 = _load_font(34, "SemiBold")
    body = _load_font(24, "Regular")
    mono = _load_font(24, "Regular")
    small = _load_font(19, "Regular")

    # Header
    draw.text((card[0] + 46, card[1] + 40), "CERTYFIKAT ROZMOWY AI", font=title, fill=(233, 236, 245))
    draw.text((card[0] + 46, card[1] + 98), "Potwierdzenie integralności i szyfrowania treści rozmowy", font=body, fill=(170, 179, 208))

    # Badges
    def badge(x, y, text, bg):
        pad_x, pad_y = 14, 8
        tw = draw.textlength(text, font=body)
        box = (x, y, x + int(tw) + 2 * pad_x, y + 2 * pad_y + 26)
        _rounded_rectangle(draw, box, 14, fill=bg, outline=None)
        draw.text((x + pad_x, y + pad_y), text, font=body, fill=(8, 12, 24))

    badge(card[2] - 420, card[1] + 44, "ENCRYPTED", (46, 229, 157))
    badge(card[2] - 260, card[1] + 44, "IPFS", (124, 92, 255))

    # Meta block
    if preview:
        now = "— — — —-— —-— —  — —:— —:— —"
        cert_id = "— — — — — — — —"
    else:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cert_id = hash_hex[:12].upper()

    meta_top = card[1] + 160
    _rounded_rectangle(draw, (card[0] + 40, meta_top, card[2] - 40, meta_top + 140), 18, fill=(15, 22, 44), outline=(255, 255, 255), width=1)

    draw.text((card[0] + 70, meta_top + 28), "Data i czas:", font=body, fill=(170, 179, 208))
    draw.text((card[0] + 260, meta_top + 28), now, font=h1, fill=(233, 236, 245))

    draw.text((card[0] + 70, meta_top + 78), "ID certyfikatu:", font=body, fill=(170, 179, 208))
    draw.text((card[0] + 300, meta_top + 78), cert_id, font=h1, fill=(233, 236, 245))

    # Hash section
    section_y = meta_top + 190
    draw.text((card[0] + 46, section_y), "Hash SHA-256 rozmowy", font=h1, fill=(233, 236, 245))
    draw.text((card[0] + 46, section_y + 44), "Wartość obliczona na podstawie pełnej treści rozmowy.", font=body, fill=(170, 179, 208))

    # Hash box (minimalnie niższy, żeby zmieścić opis standardów)
    hash_y = section_y + 110
    hash_box_h = 260  # było 270
    _rounded_rectangle(draw, (card[0] + 40, hash_y, card[2] - 40, hash_y + hash_box_h), 18,
                       fill=(10, 16, 32), outline=(255, 255, 255), width=1)

    if preview:
        # placeholder, ale w tym samym układzie
        preview_hash = "xxxx xxxx xxxx xxxx xxxx xxxx xxxx xxxx\nxxxx xxxx xxxx xxxx xxxx xxxx xxxx xxxx"
        draw.text((card[0] + 70, hash_y + 50), preview_hash, font=mono, fill=(233, 236, 245))
    else:
        groups = [hash_hex[i:i + 8] for i in range(0, len(hash_hex), 8)]
        line_len = 5  # było 6
        x0, y0 = card[0] + 70, hash_y + 34
        line_step = mono.size + 10

        for j in range(0, len(groups), line_len):
            line = "  ".join(groups[j:j + line_len])
            draw.text((x0, y0), line, font=mono, fill=(233, 236, 245))
            y0 += line_step

    # QR with payload
    if preview:
        payload = "PREVIEW"
    else:
        payload = f"hash={hash_hex}&ts={now}"

    qr = qrcode.QRCode(border=1, box_size=6)
    qr.add_data(payload)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Place QR
    qr_box = (card[2] - 40 - 270, hash_y + 20, card[2] - 40, hash_y + 20 + 270)
    _rounded_rectangle(draw, qr_box, 18, fill=(255, 255, 255), outline=None)
    qr_img = qr_img.resize((230, 230))
    img.paste(qr_img, (qr_box[0] + 20, qr_box[1] + 20))
    draw.text((qr_box[0] + 20, qr_box[3] - 46), "QR: hash + czas", font=body, fill=(10, 16, 32))

    # Verification instructions
    v_y = hash_y + hash_box_h + 40  # było hash_y + 320 (zależne od wysokości)
    draw.text((card[0] + 46, v_y), "Jak zweryfikować:", font=h1, fill=(233, 236, 245))
    steps = [
        "1) Pobierz zaszyfrowany plik z IPFS.",
        "2) Odszyfruj go kluczem certyfikatu (Fernet).",
        "3) Oblicz SHA-256 treści i porównaj z hashem powyżej.",
    ]
    yy = v_y + 56
    for s in steps:
        draw.text((card[0] + 60, yy), s, font=body, fill=(170, 179, 208))
        yy += 34

    # NOWE: standardy / wymagania certyfikacji narzędzia (na samym PNG)
    std_y = yy + 26
    draw.text((card[0] + 46, std_y), "Standardy certyfikacji narzędzia (opis):", font=h1, fill=(233, 236, 245))
    std_y += 44

    standards = [
        "Modele i procedury powinny być zweryfikowane oraz testowane przed wdrożeniem.",
        "Dane rozmowy są szyfrowane, a integralność zapisu potwierdzana przez hash (SHA-256).",
        "Zapis rozmowy jest powiązany z graficznym certyfikatem w celu kontroli integralności i autentyczności danych.",
        "Dostęp do treści rozmowy powinien mieć wyłącznie pacjent i terapeuta (kontrola uprawnień).",
        "Narzędzie powinno spełniać wymagania bezpieczeństwa danych i standardy etyczne.",
        "Model powinien być trenowany na wiarygodnych danych naukowych oraz przeglądany przez ekspertów z branży cyfrowej i psychologicznej.",
        "Architektura systemu powinna być warstwowa (frontend, backend, warstwa bezpieczeństwa i certyfikacji, warstwa przechowywania danych).",
        "System powinien realizować zasady privacy by design oraz security by design.",
        "Każda rozmowa powinna posiadać unikalny identyfikator sesji oraz znacznik czasu.",
        "Certyfikat powinien umożliwiać weryfikację integralności i autentyczności zapisu rozmowy."
    ]
   # Footer line
    footer_y = card[3] - 120
    max_std_y = footer_y - 20

    for line in standards:
        wrapped = _wrap_text_lines(line, max_chars=88)
        for wline in wrapped:
            if std_y >= max_std_y:
                break
            draw.text((card[0] + 60, std_y), wline, font=small, fill=(170, 179, 208))
            std_y += 26
        if std_y >= max_std_y:
            break
        std_y += 4
    draw.line((card[0] + 40, footer_y, card[2] - 40, footer_y), fill=(255, 255, 255), width=1)
    draw.text((card[0] + 46, card[3] - 92), "Wytwór badawczy: certyfikacja rozmów AI • Uniwersytet SWPS", font=body, fill=(170, 179, 208))

    img.save(output_path)
    print(f"📄 Certyfikat graficzny zapisany jako {output_path}")
