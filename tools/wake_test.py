"""Live wake-word scores, for tuning WAKE_THRESHOLD. Ctrl+C prints a summary.

    python tools/wake_test.py
    python tools/wake_test.py --threshold 0.4
"""
import _path  # noqa: F401

import argparse
import time

import audio
import config
from wake import make_detector

parser = argparse.ArgumentParser()
parser.add_argument("--threshold", type=float, default=None)
args = parser.parse_args()

cfg = config.load(require_api_key=False)
threshold = args.threshold if args.threshold is not None else cfg.wake_threshold
detector = make_detector(cfg)
detector.threshold = threshold
detector.cooldown_s = 1.5
idx = audio.find_device(cfg.mic_device, "input")
mic = audio.MicStream(idx).start()
print(f"Mic: {audio.device_label(idx, 'input')}")
print(f"Threshold {threshold}. Say 'Hey Jack'. Ctrl+C to stop.\n")

hits, peak, t0 = 0, 0.0, time.monotonic()
try:
    while True:
        fired = detector.process(mic.read())
        score = detector.last_score
        peak = max(peak, score)
        if fired:
            hits += 1
            print(f"\n  WAKE #{hits}  score {score:.2f}")
        elif score > 0.1:
            print(f"\r  score {score:.2f} {'#' * int(score * 40):<40}", end="", flush=True)
except KeyboardInterrupt:
    mins = (time.monotonic() - t0) / 60
    print(f"\n\n{hits} wake(s) in {mins:.1f} min. Highest score seen: {peak:.2f}")
finally:
    mic.close()
