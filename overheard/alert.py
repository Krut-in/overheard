"""Alert path for relevant inputs: Neon extracts the change, Hydrogen translates and captions, TTS whispers,
Nano Banana circles the line on the rider's photo, Carbon settles the 0.4 to 0.8 band and conflicts."""
import io, json, wave
from google.genai import types
from overheard import config
from overheard.gemini import client, timed

LOW = types.ThinkingConfig(thinking_level="low")


def _part(data: bytes, mime: str):
    return types.Part.from_bytes(data=data, mime_type=mime)


def _json(model, summary, parts, schema, thinking=LOW):
    r = timed(model, summary, client().models.generate_content, model=model, contents=parts,
              config=types.GenerateContentConfig(response_mime_type="application/json",
                                                 response_json_schema=schema, thinking_config=thinking))
    return json.loads(r.text)


CHANGE_SCHEMA = {"type": "object", "properties": {
    "quote": {"type": "string", "description": "the exact words in the input that state the change, in the input's language, as written or spoken"},
    "change": {"type": "string", "description": "one short English sentence: what changed for this rider"},
    "action": {"type": "string", "description": "one short English sentence: what the rider should do now"},
    "source_language": {"type": "string"}},
    "required": ["quote", "change", "action", "source_language"]}


def extract_change(data: bytes, mime: str, trip: dict) -> dict:
    prompt = (f"A rider is on this NYC subway trip: {trip['summary']} (stops: {', '.join(trip.get('stops_between', []))}). "
              "This input (a station announcement or a photo of a sign) affects their trip. Extract the exact change "
              "and what this rider should do. Be concrete and short.")
    return _json(config.NEON, f"extract change for {trip['summary']}", [prompt, _part(data, mime)], CHANGE_SCHEMA)


def translate(change: dict, lang: str) -> dict:
    schema = {"type": "object", "properties": {"change": {"type": "string"}, "action": {"type": "string"},
                                               "whisper": {"type": "string", "description": "one or two calm sentences to whisper, combining change and action"}},
              "required": ["change", "action", "whisper"]}
    prompt = (f"Translate for a subway rider into {lang}. Keep station names and line letters/numbers as written "
              f"(you may add a transliteration in brackets). Input JSON: {json.dumps(change)}")
    return _json(config.HYDROGEN, f"translate to {lang}", [prompt], schema)


def caption(data: bytes, mime: str) -> str:
    """Six-word gist for a silence receipt, e.g. 'poster about the L train'."""
    r = timed(config.HYDROGEN, "receipt caption", client().models.generate_content, model=config.HYDROGEN,
              contents=["In at most 8 English words, say what this subway announcement or sign is about, "
                        "e.g. 'poster about weekend L train shuttle buses' or 'door closing warning'. No period.",
                        _part(data, mime)],
              config=types.GenerateContentConfig(thinking_config=types.ThinkingConfig(thinking_level="low")))
    return (r.text or "").strip()


def whisper(text: str) -> bytes:
    """TTS whisper, returned as a wav file."""
    r = timed(config.TTS, f"whisper {text[:40]}", client().models.generate_content, model=config.TTS,
              contents=f"Whisper this softly and clearly, like a friend leaning in: {text}",
              config=types.GenerateContentConfig(
                  response_modalities=["AUDIO"],
                  speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                      prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=config.TTS_VOICE)))))
    pcm = r.candidates[0].content.parts[0].inline_data.data
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(24000); w.writeframes(pcm)
    return buf.getvalue()


def annotate(photo: bytes, mime: str, quote: str, translated: str) -> bytes | None:
    prompt = (f"Edit this photo. Draw a thick bright red hand-drawn circle around the text that says: \"{quote}\". "
              f"Next to the circle, add a yellow sticky-note style label with this text: \"{translated}\". "
              "Keep everything else in the photo exactly the same.")
    r = timed(config.IMAGE, f"annotate {quote[:40]}", client().models.generate_content, model=config.IMAGE,
              contents=[prompt, _part(photo, mime)],
              config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
    for part in r.candidates[0].content.parts:
        if part.inline_data:
            return part.inline_data.data
    return None


VERDICT = {"type": "object", "properties": {"relevant": {"type": "boolean"},
                                            "reason": {"type": "string", "description": "one sentence"}},
           "required": ["relevant", "reason"]}


def carbon_band(data: bytes, mime: str, trip: dict, scores: dict) -> dict:
    """0.4 to 0.8: Carbon looks at the input itself and decides."""
    prompt = (f"Rider trip: {trip['summary']}, stops between: {', '.join(trip.get('stops_between', []))}. "
              f"A fast relevance model was unsure (relevance {scores['relevance']}, strongest signals: "
              f"{json.dumps(scores['top_hits'][:3])}). Does this input announce or show a service change on the rider's "
              "line in their direction between their stations, or at their boarding or alighting station? "
              "Other lines, other directions and normal service do not count.")
    return _json(config.CARBON, "band check", [prompt, _part(data, mime)], VERDICT)


CONFLICT = {"type": "object", "properties": {"trust": {"type": "string", "enum": ["first", "second", "neither"]},
                                             "explanation": {"type": "string", "description": "two short sentences for the rider"},
                                             "do_now": {"type": "string"}},
            "required": ["trust", "explanation", "do_now"]}


def carbon_conflict(trip: dict, first: dict, second: dict) -> dict:
    prompt = (f"Rider trip: {trip['summary']}. Two sources disagree. Decide which to trust. Prefer the more recent, "
              "more specific, live source (a live announcement or countdown clock beats a printed poster, unless the "
              f"poster is for today and the other is generic).\nFirst: {json.dumps(first)}\nSecond: {json.dumps(second)}")
    return _json(config.CARBON, "conflict", [prompt], CONFLICT)
