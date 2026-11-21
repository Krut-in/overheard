"""Generate the synthetic eval set: TTS announcements (gemini-3.8-flash-tts) and posters (Nano Banana) from data/spec.py."""
import sys, wave, json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from google.genai import types
from overheard import config
from overheard.gemini import client, timed
from data.spec import AUDIO, IMAGES, TRIPS

OUT = Path(__file__).resolve().parent / "synth"
VOICES = ["Kore", "Charon", "Puck", "Fenrir", "Aoede"]


def pcm_to_wav(pcm: bytes, path: Path, rate=24000):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate); w.writeframes(pcm)


def tts(text: str, voice: str, style: str) -> bytes:
    r = timed(config.TTS, f"tts {text[:50]}", client().models.generate_content,
              model=config.TTS, contents=f"{style}: {text}",
              config=types.GenerateContentConfig(
                  response_modalities=["AUDIO"],
                  speech_config=types.SpeechConfig(voice_config=types.VoiceConfig(
                      prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)))))
    return r.candidates[0].content.parts[0].inline_data.data


def gen_audio(i_item):
    i, (aid, lang, text, _) = i_item
    p = OUT / "audio" / f"{aid}.wav"
    if p.exists():
        return
    style = "Read this as a flat, slightly hurried New York subway public address announcement"
    pcm_to_wav(tts(text, VOICES[i % len(VOICES)], style), p)


def gen_image(item):
    iid, kind, prompt, text, _ = item
    p = OUT / "images" / f"{iid}.png"
    if p.exists():
        return
    r = timed(config.IMAGE, f"poster {iid} {text[:40]}", client().models.generate_content,
              model=config.IMAGE, contents=prompt + text,
              config=types.GenerateContentConfig(response_modalities=["IMAGE"]))
    for part in r.candidates[0].content.parts:
        if part.inline_data:
            p.write_bytes(part.inline_data.data)
            return
    raise RuntimeError(f"no image for {iid}")


def write_labels():
    labels = {"trips": TRIPS, "items": []}
    for aid, lang, text, rel in AUDIO:
        labels["items"].append({"id": aid, "modality": "audio", "file": f"data/synth/audio/{aid}.wav",
                                "lang": lang, "text": text, "relevant": rel, "source": "synthetic"})
    for iid, kind, _, text, rel in IMAGES:
        labels["items"].append({"id": iid, "modality": "image", "file": f"data/synth/images/{iid}.png",
                                "kind": kind, "text": text, "relevant": rel, "source": "synthetic"})
    (OUT.parent / "labels.json").write_text(json.dumps(labels, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    write_labels()
    which = sys.argv[1] if len(sys.argv) > 1 else "all"
    with ThreadPoolExecutor(8) as ex:
        futs = []
        if which in ("all", "audio"):
            futs += [ex.submit(gen_audio, x) for x in enumerate(AUDIO)]
        if which in ("all", "images"):
            futs += [ex.submit(gen_image, x) for x in IMAGES]
        for f in futs:
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                print("FAILED", e)
