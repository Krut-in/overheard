"""Rehearsal: the announcements and signs a traveller will likely meet on each booking, with labels.
Hydrogen writes the scripts, gemini-3.8-flash-tts voices them to mp3, Nano Banana draws the signs as JPEG.
The saved set in data/abroad/rehearsal/ is also the abroad eval set.

  rehearse(it, per_booking=6) -> [RehearsalItem]   in-product path, writes media to DIR
  load() -> [RehearsalItem]                          the saved set
  check(items, it) -> [problem]                      schema and label balance
  python -m overheard.rehearsal media                voice and draw scripts.json into items.json
"""
import io, json, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from google.genai import types
from overheard import config
from overheard.gemini import client, timed

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "data" / "abroad" / "rehearsal"
SCRIPTS = DIR / "scripts.json"
ITEMS = DIR / "items.json"
LANGS = ("fr", "nl", "en")
KINDS = ("audio", "image")
FIELDS = ("id", "booking_id", "lang", "kind", "script", "media", "labels", "why")
VOICES = ["Kore", "Charon", "Aoede", "Puck", "Fenrir"]
LOW = types.ThinkingConfig(thinking_level="low")


# ---------- saved set and checks ----------

def load(path: Path = ITEMS) -> list[dict]:
    return json.loads(Path(path).read_text())


def check(items: list[dict], it: dict, per_booking: int = 6) -> list[str]:
    """Problems with the set: missing fields, bad values, labels that skip a booking, unbalanced bookings."""
    ids = [b["id"] for b in it["bookings"]]
    problems = []
    for i in items:
        name = i.get("id", "?")
        missing = [f for f in FIELDS if f not in i]
        if missing:
            problems.append(f"{name}: missing {missing}")
            continue
        if i["booking_id"] not in ids:
            problems.append(f"{name}: unknown booking {i['booking_id']}")
        if i["lang"] not in LANGS:
            problems.append(f"{name}: lang {i['lang']}")
        if i["kind"] not in KINDS:
            problems.append(f"{name}: kind {i['kind']}")
        if not i["script"].strip() or not i["why"].strip():
            problems.append(f"{name}: empty script or why")
        if set(i["labels"]) != set(ids) or not all(isinstance(v, bool) for v in i["labels"].values()):
            problems.append(f"{name}: labels must give a bool for every booking")
    for b in ids:
        mine = [i for i in items if i.get("booking_id") == b and isinstance(i.get("labels"), dict)]
        hits = sum(bool(i["labels"].get(b)) for i in mine)
        if len(mine) < per_booking or hits * 2 != len(mine):
            problems.append(f"{b}: balance {hits} relevant of {len(mine)} (want half of at least {per_booking})")
    return problems


# ---------- scripts (Hydrogen) ----------

def _booking_line(b: dict) -> str:
    return (f"[{b['id']}] {b['title']}. From {b.get('from_place') or '-'} to {b.get('to_place') or '-'}. "
            f"Start {b['start']}, end {b['end']}. {b.get('details', '')} Local languages: {', '.join(b.get('langs', []))}.")


ITEM_SCHEMA = {"type": "object", "properties": {
    "lang": {"type": "string", "enum": list(LANGS)},
    "kind": {"type": "string", "enum": list(KINDS)},
    "script": {"type": "string", "description": "the words as spoken (audio) or printed on the sign (image)"},
    "relevant": {"type": "boolean", "description": "true only if it changes this exact booking"},
    "why": {"type": "string", "description": "one short English sentence"}},
    "required": ["lang", "kind", "script", "relevant", "why"]}


def write_scripts(it: dict, booking: dict, per_booking: int = 6) -> list[dict]:
    """Hydrogen writes per_booking items for one booking: half hit it, half are near misses."""
    n_audio = max(per_booking - per_booking // 3, 1)
    others = "\n".join(_booking_line(b) for b in it["bookings"] if b["id"] != booking["id"])
    prompt = (
        f"Write {per_booking} things a traveller will hear or see on this booking:\n{_booking_line(booking)}\n"
        f"{n_audio} are public address announcements (kind audio) as spoken at that place, the rest are the exact text "
        "of a sign, poster, departure board or screen (kind image). Exactly half are relevant: they announce a change "
        "that hits this exact booking (cancellation, delay, gate or platform change, entrance or station closure on "
        "its date). The other half are near misses that look similar but do not change it: another train or flight "
        "number, another terminal, another date, the other direction, another station, or a stop that is open. "
        "Use the language each place really uses (French in France, Dutch in the Netherlands, English as the "
        "second language). None may hit these other bookings:\n" + others)
    schema = {"type": "array", "items": ITEM_SCHEMA}
    r = timed(config.HYDROGEN, f"rehearsal scripts {booking['id']}", client().models.generate_content,
              model=config.HYDROGEN, contents=[prompt],
              config=types.GenerateContentConfig(response_mime_type="application/json",
                                                 response_json_schema=schema, thinking_config=LOW))
    ids = [b["id"] for b in it["bookings"]]
    out = []
    for n, x in enumerate(json.loads(r.text)[:per_booking], 1):
        labels = {b: False for b in ids}
        labels[booking["id"]] = bool(x["relevant"])
        out.append({"id": f"{booking['id']}_{n}", "booking_id": booking["id"], "lang": x["lang"], "kind": x["kind"],
                    "script": x["script"], "media": "", "labels": labels, "why": x["why"]})
    return out


# ---------- media ----------

PLACE = {"flight": "airport", "train": "railway station", "hotel": "metro or tram stop", "ticket": "museum and its metro station"}


def _ffmpeg(args: list[str]):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def voice(item: dict, booking: dict, idx: int = 0) -> str:
    """TTS the script and save it as a small mp3 next to items.json.
    Only the script is sent: a style prefix in the prompt gets read aloud, and this TTS model rejects
    system instructions (400 "Developer instruction is not enabled"). Variety comes from the voice."""
    r = timed(config.TTS, f"rehearsal tts {item['id']} {item['script'][:40]}", client().models.generate_content,
              model=config.TTS, contents=item["script"],
              config=types.GenerateContentConfig(
                  response_modalities=["AUDIO"],
                  speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                      prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICES[idx % len(VOICES)])))))
    pcm = r.candidates[0].content.parts[0].inline_data.data
    name = f"{item['id']}.mp3"
    with tempfile.NamedTemporaryFile(suffix=".pcm") as f:
        f.write(pcm); f.flush()
        _ffmpeg(["-f", "s16le", "-ar", "24000", "-ac", "1", "-i", f.name, "-b:a", "48k", str(DIR / name)])
    return name


def draw(item: dict, booking: dict) -> str:
    """Nano Banana draws the sign as a phone photo; saved as a JPEG under 300 KB."""
    from PIL import Image
    prompt = (f"A realistic smartphone photo of a sign, poster or departure board at the {booking['city']} "
              f"{PLACE.get(booking['kind'], 'station')} for {booking['operator']}, taken by a traveller. "
              "The sign shows exactly this text, spelled exactly, nothing else readable:\n" + item["script"])
    r = timed(config.IMAGE, f"rehearsal sign {item['id']} {item['script'][:40]}", client().models.generate_content,
              model=config.IMAGE, contents=prompt, config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
    data = next(p.inline_data.data for p in r.candidates[0].content.parts if p.inline_data)
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((1024, 1024))
    name = f"{item['id']}.jpg"
    for q in (80, 65, 50):
        img.save(DIR / name, "JPEG", quality=q, optimize=True)
        if (DIR / name).stat().st_size < 300_000:
            break
    return name


def media(items: list[dict], it: dict, skip_existing: bool = True) -> list[dict]:
    """Voice every audio item and draw every image item (at most 4 image calls at once)."""
    DIR.mkdir(parents=True, exist_ok=True)
    by_id = {b["id"]: b for b in it["bookings"]}

    def one(pair):
        idx, i = pair
        ext = ".mp3" if i["kind"] == "audio" else ".jpg"
        if skip_existing and (DIR / f"{i['id']}{ext}").exists():
            i["media"] = f"{i['id']}{ext}"
            return
        b = by_id[i["booking_id"]]
        i["media"] = voice(i, b, idx) if i["kind"] == "audio" else draw(i, b)

    audio = [(n, i) for n, i in enumerate(items) if i["kind"] == "audio"]
    image = [(n, i) for n, i in enumerate(items) if i["kind"] == "image"]
    with ThreadPoolExecutor(8) as ea, ThreadPoolExecutor(4) as ei:
        futs = [ea.submit(one, x) for x in audio] + [ei.submit(one, x) for x in image]
        for f in futs:
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                print("MEDIA FAILED", e, flush=True)
    return items


def rehearse(it: dict, per_booking: int = 6) -> list[dict]:
    """In-product path: Hydrogen writes the scripts for every booking, then voice and draw them."""
    with ThreadPoolExecutor(6) as ex:
        items = [x for xs in ex.map(lambda b: write_scripts(it, b, per_booking), it["bookings"]) for x in xs]
    return [i for i in media(items, it) if i["media"]]


if __name__ == "__main__":
    it = json.loads((ROOT / "data/abroad/itinerary.json").read_text())
    if sys.argv[1:] == ["media"]:
        items = media(json.loads(SCRIPTS.read_text()), it)
        ITEMS.write_text(json.dumps(items, indent=1, ensure_ascii=False))
        print(f"{len(items)} items, problems: {check(items, it)}")
