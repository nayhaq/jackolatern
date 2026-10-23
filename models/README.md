# models/

Model files are large and not committed. `setup.ps1` downloads everything except the wake word.

| File | Where it comes from |
|---|---|
| `hey_jack.onnx` | You train it (RUNBOOK step 2). The openWakeWord "automatic model training" Colab notebook, target phrase `hey jack` |
| `piper/en_US-*-medium.onnx` + `.onnx.json` | `setup.ps1` (ryan, joe, lessac, hfc_male), from `rhasspy/piper-voices` on Hugging Face |
| `whisper/` | `setup.ps1` (faster-whisper `base.en`) |
| openWakeWord feature models | `setup.ps1` puts them inside the openwakeword package folder |

Porcupine fallback: put the "Hey Jack" `.ppn` file here, set `WAKE_ENGINE=porcupine`, set
`WAKE_MODEL_PATH` to the `.ppn` file, and add `PICOVOICE_ACCESS_KEY` to `.env`.
