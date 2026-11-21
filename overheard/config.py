"""All model IDs and thresholds for Overheard. Nothing else in the repo names a model."""

NEON = "gemini-4-neon"            # trip extraction, change extraction, video slicing
HYDROGEN = "gemini-4-hydrogen"    # fingerprint question expansion, translation
CARBON = "gemini-4-carbon"        # conflicts in the 0.4 to 0.8 band
DECISION = "gemini-decision-1"    # relevance scoring on every input
TTS = "gemini-3.8-flash-tts"      # whispered alert
IMAGE = "gemini-nano-banana-2.1"  # annotated photo, synthetic posters
MANAGED_AGENT = "antigravity-preview-09-2026"  # ffmpeg highlight clip

NEON_THINKING = "low"   # anything a user waits on

DIRECT_WEIGHT = 0.3     # relevance = 0.3 x direct question + 0.7 x fingerprint (picked on the eval set, see README)
ALERT_AT = 0.8          # above this: alert
CONFLICT_AT = 0.4       # 0.4 to 0.8: Carbon decides; below: silence receipt

TTS_VOICE = "Kore"

USE_MANAGED_AGENT = True  # video highlight: local ffmpeg clip at once, Managed Agent clip (about 60 s) replaces it
