"""One-time model downloads (run by setup.ps1). Needs huggingface.co and github.com.

After this succeeds, set HF_HUB_OFFLINE=1 in .env so event day needs only api.anthropic.com.
"""
import _path  # noqa: F401

import shutil

from huggingface_hub import hf_hub_download

import config

PIPER_VOICES = [
    "en/en_US/ryan/medium/en_US-ryan-medium",
    "en/en_US/joe/medium/en_US-joe-medium",
    "en/en_US/lessac/medium/en_US-lessac-medium",
    "en/en_US/hfc_male/medium/en_US-hfc_male-medium",
]

cfg = config.load(require_api_key=False, require_models=False)
piper_dir = config.ROOT / "models" / "piper"
piper_dir.mkdir(parents=True, exist_ok=True)

print("1/3 openWakeWord feature models...")
import openwakeword.utils  # noqa: E402

openwakeword.utils.download_models()

print(f"2/3 faster-whisper {cfg.whisper_model}...")
from faster_whisper import WhisperModel  # noqa: E402

WhisperModel(cfg.whisper_model, device="cpu", compute_type="int8", download_root=str(cfg.whisper_dir))

print("3/3 Piper voices...")
for voice in PIPER_VOICES:
    for suffix in (".onnx", ".onnx.json"):
        target = piper_dir / (voice.rsplit("/", 1)[1] + suffix)
        if target.exists():
            continue
        src = hf_hub_download("rhasspy/piper-voices", voice + suffix)
        shutil.copy(src, target)
    print("   ", voice.rsplit("/", 1)[1])

print("MODELS OK")
