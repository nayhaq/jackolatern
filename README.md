# Jack O'Intern

A talking pumpkin for PNY's Pumpkin Painting Contest (theme: "Embracing AI"). Say "Hey Jack" and
a sassy, Gen Z, deadpan Day-1 IT intern answers questions about PNY and roasts other departments'
pumpkins.

**Setup and event-day steps:** [RUNBOOK.md](RUNBOOK.md)

## How it works
```
Jabra mic (USB) -> wake word (openWakeWord, local) -> record until quiet (webrtcvad)
  -> filler line plays  ||  speech-to-text (faster-whisper, local)
  -> Claude claude-haiku-5-5 (persona + live mood + this visitor's last turns)
  -> safety guard -> Piper TTS (local) -> Jabra speaker
  -> 8 s follow-up window (no wake word needed) -> back to listening
```
Only the question text and Jack's reply leave the laptop, and only to `api.anthropic.com`.
Audio never leaves the laptop.

| File | Job |
|---|---|
| `jack.py` | Main loop (`--text` to type instead of talk) |
| `persona.py` | System prompt, 10 PNY topic cards, roast angles, fixed lines. **Edit here to change what Jack says** |
| `brain.py` | Claude call and error mapping |
| `guard.py` | Input cleanup, output safety, repeat detector, pronunciation fixes |
| `mood.py` | Visitor count, coffee level, voting countdown, roast angles used today |
| `session.py` | One visitor's conversation (up to 4 turns) |
| `audio.py`, `wake.py`, `stt.py`, `tts.py` | Mic, wake word, speech-to-text, voice |
| `prerender.py` | Pre-records the fixed lines (chirps, fillers, error jokes) |
| `start.ps1` / `setup.ps1` | Run with auto-restart / one-time install |
| `tools/` | Device list, mic meter, wake tuning, voice audition, latency bench, model download |
| `tests/` | `pytest -m "not live"` runs offline. `tests/test_persona.py` hits the real API |
