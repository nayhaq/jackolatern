"""Hear the same lines in every Piper voice in models/piper/, so you can pick Jack's voice.

    python tools/voice_audition.py
    python tools/voice_audition.py --length-scale 1.2
"""
import _path  # noqa: F401

import argparse

import audio
import config
from guard import say_friendly
from tts import Voice

LINES = [
    "Oh. A human. Hi.",
    "PNY's RTX 5090 has 32 GB of GDDR7. I'm not crying, you're crying.",
    "Marketing's pumpkin has been up for three hours and still no rebrand. Concerning.",
]

parser = argparse.ArgumentParser()
parser.add_argument("--length-scale", type=float, default=None)
args = parser.parse_args()
cfg = config.load(require_api_key=False, require_models=False)
scale = args.length_scale or cfg.piper_length_scale
player = audio.Player(audio.find_device(cfg.speaker_device, "output"))

voices = sorted((config.ROOT / "models" / "piper").glob("*.onnx"))
if not voices:
    raise SystemExit("No voices in models/piper/. Run setup.ps1 first.")
for path in voices:
    print(f"\n== {path.name} (length_scale {scale})")
    voice = Voice(path, scale)
    for line in LINES:
        print(f"   {line}")
        player.play(*voice.synth(say_friendly(line)))
print("\nSet PIPER_VOICE_PATH in .env to your favorite, then run: python prerender.py --force")
