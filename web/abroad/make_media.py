"""Draws the fixture media for the abroad phone page: a Gare du Nord departures board photo with the
Eurostar 9315 line circled (the proof), and voices the Hindi whisper and two announcement clips with macOS `say`.

Run once: .venv/bin/python web/abroad/make_media.py   (writes into web/abroad/media/)
No Gemini calls. Ticket F replaces these with Nano Banana proofs and Gemini TTS whispers.
"""
import random, subprocess, tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

OUT = Path(__file__).resolve().parent / "media"
FONTS = Path("/System/Library/Fonts")


def font(name, size, index=0):
    for p in (FONTS / name, FONTS / "Supplemental" / name):
        if p.exists():
            return ImageFont.truetype(str(p), size, index=index)
    return ImageFont.load_default(size)


def board(path: Path):
    W, H = 900, 1100
    img = Image.new("RGB", (W, H), (24, 22, 20))
    d = ImageDraw.Draw(img)
    # station wall and the board panel, slightly off-axis like a phone photo
    for y in range(H):
        g = 40 + int(18 * y / H)
        d.line([(0, y), (W, y)], fill=(g, g - 3, g - 8))
    panel = Image.new("RGB", (820, 860), (10, 30, 78))
    p = ImageDraw.Draw(panel)
    bold, mono = font("DIN Condensed Bold.ttf", 44), font("Menlo.ttc", 30, 1)
    small = font("Menlo.ttc", 22)
    p.rectangle([0, 0, 820, 92], fill=(255, 255, 255))
    p.text((28, 18), "DÉPARTS  ·  DEPARTURES", font=font("DIN Condensed Bold.ttf", 58), fill=(10, 30, 78))
    p.text((640, 30), "08:58", font=font("DIN Condensed Bold.ttf", 50), fill=(200, 30, 30))
    p.text((28, 104), "HEURE   DESTINATION              TRAIN      VOIE", font=small, fill=(150, 175, 230))
    rows = [
        ("09:04", "LILLE-EUROPE", "TGV 7031", "7", "À L'HEURE"),
        ("09:13", "LONDON ST PANCRAS", "EST 9014", "4", "À L'HEURE"),
        ("09:16", "AMIENS", "TER 847512", "19", "RETARD 10'"),
        ("09:25", "AMSTERDAM-CENTRAAL", "EST 9315", "--", "SUPPRIMÉ"),
        ("09:31", "BRUXELLES-MIDI", "EST 9417", "8", "À L'HEURE"),
        ("09:46", "CREIL", "RER D", "40", "À L'HEURE"),
        ("10:13", "LONDON ST PANCRAS", "EST 9022", "3", "À L'HEURE"),
        ("11:25", "AMSTERDAM-CENTRAAL", "EST 9323", "9", "À L'HEURE"),
    ]
    y = 150
    for t, dest, tr, voie, info in rows:
        p.line([(20, y - 10), (800, y - 10)], fill=(30, 55, 115), width=2)
        p.text((28, y), t, font=mono, fill=(255, 214, 10))
        p.text((150, y), dest, font=mono, fill=(255, 255, 255))
        p.text((150, y + 40), tr, font=small, fill=(150, 175, 230))
        p.text((560, y + 40), info, font=small, fill=(255, 90, 80) if info != "À L'HEURE" else (120, 220, 150))
        p.text((740, y), voie, font=mono, fill=(255, 255, 255))
        if tr == "EST 9315":
            target_y = y
        y += 86
    p.text((28, 820), "Grève : trafic Eurostar perturbé. Renseignez-vous en hall 2.", font=small, fill=(255, 214, 10))
    panel = panel.rotate(-2.2, expand=True, fillcolor=(34, 32, 30))
    img.paste(panel, (34, 90))
    d = ImageDraw.Draw(img)
    # the circle and the label, as the proof step would draw them
    cy = 90 + 18 + target_y + 30
    d.ellipse([18, cy - 62, W - 18, cy + 74], outline=(255, 64, 40), width=9)
    tag = font("DIN Condensed Bold.ttf", 40)
    d.rounded_rectangle([60, cy + 92, 760, cy + 160], 16, fill=(255, 64, 40))
    d.text((84, cy + 104), "YOUR TRAIN 9315 IS CANCELLED  ·  next: 9323 at 11:25", font=tag, fill=(255, 255, 255))
    # phone-photo feel: grain and a little blur
    rnd = random.Random(7)
    noise = Image.effect_noise((W, H), 22).convert("RGB")
    img = Image.blend(img, noise, 0.06).filter(ImageFilter.GaussianBlur(0.6))
    _ = rnd
    img.save(path, quality=84, optimize=True)


def voice(text: str, voice_name: str, path: Path):
    with tempfile.TemporaryDirectory() as tmp:
        aiff = Path(tmp) / "a.aiff"
        subprocess.run(["say", "-v", voice_name, "-o", str(aiff), text], check=True)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(aiff), "-ac", "1", "-ar", "22050",
                        "-b:a", "48k", str(path)], check=True)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    board(OUT / "proof_train_ams.jpg")
    voice("आपकी यूरोस्टार 9315, पेरिस से एम्स्टर्डम, रद्द हो गई है। हॉल 2 के यूरोस्टार काउंटर पर जाएँ। "
          "अगली ट्रेन 9323, 11 बजकर 25 मिनट पर है।", "Lekha", OUT / "whisper_train_ams.m4a")
    voice("Mesdames et messieurs, le TER 847512 à destination d'Amiens partira voie 19, avec un retard de 10 minutes.",
          "Thomas", OUT / "fr_ter_amiens.m4a")
    voice("Dames en heren, de sprinter naar Zandvoort aan Zee vertrekt vandaag van spoor 5b.",
          "Xander", OUT / "nl_sprinter_zandvoort.m4a")
    print("wrote", sorted(x.name for x in OUT.iterdir()))
    voice("सूचना: 27 से 29 नवंबर तक फ़्रांस में रेल हड़ताल का नोटिस है। 28 नवंबर की आपकी यूरोस्टार 9315 रद्द हो सकती है। "
          "एक दिन पहले शाम को जाँच लें।", "Lekha", OUT / "whisper_radar_strike.m4a")
    voice("आपकी फ़्लाइट AF 23 टर्मिनल 2E की जगह टर्मिनल 2F पर उतरेगी।", "Lekha", OUT / "whisper_flight_out.m4a")
    print("wrote extra whispers")
