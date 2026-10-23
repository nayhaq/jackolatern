"""List audio devices and show which ones MIC_DEVICE / SPEAKER_DEVICE pick.

    python tools/list_devices.py
"""
import _path  # noqa: F401

import sounddevice as sd

import audio
import config

cfg = config.load(require_api_key=False, require_models=False)
hostapis = sd.query_hostapis()
print(f"{'#':>3}  {'in':>2} {'out':>3}  {'rate':>6}  host API              name")
for i, d in enumerate(sd.query_devices()):
    print(f"{i:>3}  {d['max_input_channels']:>2} {d['max_output_channels']:>3}  "
          f"{int(d['default_samplerate']):>6}  {hostapis[d['hostapi']]['name']:<20}  {d['name']}")

mic = audio.find_device(cfg.mic_device, "input")
spk = audio.find_device(cfg.speaker_device, "output")
print()
print(f"MIC_DEVICE={cfg.mic_device!r}  -> {audio.device_label(mic, 'input')}"
      + ("" if mic is not None or not cfg.mic_device else "   (NO MATCH: using system default)"))
print(f"SPEAKER_DEVICE={cfg.speaker_device!r}  -> {audio.device_label(spk, 'output')}"
      + ("" if spk is not None or not cfg.speaker_device else "   (NO MATCH: using system default)"))
