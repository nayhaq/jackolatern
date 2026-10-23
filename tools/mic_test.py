"""Live mic level meter with a speech indicator. Talk and watch it move. Ctrl+C to stop.

    python tools/mic_test.py
"""
import _path  # noqa: F401

import audio
import config

cfg = config.load(require_api_key=False, require_models=False)
idx = audio.find_device(cfg.mic_device, "input")
mic = audio.MicStream(idx).start()
vad = audio.Vad(cfg.vad_aggressiveness)
print(f"Mic: {audio.device_label(idx, 'input')}")
print(f"Capturing at {mic.in_sr} Hz, resampling to {audio.TARGET_SR} Hz. Ctrl+C to stop.\n")
try:
    while True:
        block = mic.read()
        db = audio.rms_dbfs(block)
        bar = "#" * max(0, int((db + 60) / 1.5))
        speech = "SPEECH" if sum(vad.frames(block)) >= 2 else "      "
        print(f"\r{db:6.1f} dBFS {speech} |{bar:<40}|", end="", flush=True)
except KeyboardInterrupt:
    print(f"\nDone. Dropped blocks: {mic.overflows}")
finally:
    mic.close()
