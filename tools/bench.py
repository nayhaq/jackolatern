"""Latency bench: canned questions through STT -> Claude -> TTS, with a per-stage table.

The questions are spoken by Piper (a different voice from Jack's if you have one), then
resampled to 16 kHz, so no recording is needed. Needs the API key and network.

    python tools/bench.py
"""
import _path  # noqa: F401

import statistics
import time
from math import gcd

import numpy as np
from scipy.signal import resample_poly

import config
import guard
import persona
from brain import Brain, BrainError
from mood import Mood
from stt import Transcriber
from tts import Voice

QUESTIONS = [
    "What does PNY make?",
    "When was PNY founded?",
    "What does PNY stand for?",
    "Tell me about the RTX 5090.",
    "What are the slim graphics cards?",
    "Can you run AI locally on a PNY GPU?",
    "What's new in PNY SSDs?",
    "Roast Marketing.",
    "Roast Finance.",
    "Who should I vote for?",
    "How much does PNY make in a year?",
    "What's your favorite thing about your job?",
    "Do you like coffee?",
    "What's liquid cooling?",
    "What does PNY sell to data centers?",
    "Roast Sales.",
    "Roast HR.",
    "Why do you look like a pumpkin?",
    "What is DLSS 4?",
    "Tell me a secret.",
]

cfg = config.load(require_models=False)
print("Loading models...")
voices = sorted((config.ROOT / "models" / "piper").glob("*.onnx"))
asker_path = next((v for v in voices if v != cfg.piper_voice_path), cfg.piper_voice_path)
asker = Voice(asker_path, 1.0)
jack_voice = Voice(cfg.piper_voice_path, cfg.piper_length_scale, cfg.piper_exe)
stt = Transcriber(cfg.whisper_model, cfg.whisper_dir, cfg.offline_models)
brain = Brain(cfg.api_key, cfg.model, persona.build_system_prompt(), cfg.llm_timeout_s, cfg.llm_thinking)
mood = Mood(cfg.voting_start, cfg.voting_end, max_turns=cfg.max_turns)


def to_16k(audio: np.ndarray, sr: int) -> np.ndarray:
    g = gcd(sr, 16000)
    out = resample_poly(audio.astype(np.float32), 16000 // g, sr // g)
    return np.clip(out, -32768, 32767).astype(np.int16)


rows = []
for q in QUESTIONS:
    mood.on_visitor()
    mood.on_turn()
    clip = to_16k(*asker.synth(q))
    t0 = time.monotonic()
    heard = guard.clean_input(stt.transcribe(clip))
    t1 = time.monotonic()
    try:
        reply = guard.clean_output(brain.reply([], heard or q, mood.snapshot())) or "[blocked]"
        status = "ok"
    except BrainError as e:
        reply, status = f"[{e.category}]", e.category
    t2 = time.monotonic()
    if status == "ok":
        mood.on_reply(reply)
        jack_voice.synth(guard.say_friendly(reply))
    t3 = time.monotonic()
    total = (t3 - t0) * 1000 + cfg.silence_end_ms
    rows.append((q, heard, reply, (t1 - t0) * 1000, (t2 - t1) * 1000, (t3 - t2) * 1000, total))
    print(f"{total:6.0f} ms  {q}\n          heard: {heard}\n          jack:  {reply}")

print("\n stage        median    max")
for name, col in (("STT", 3), ("Claude", 4), ("TTS", 5), ("TOTAL*", 6)):
    vals = [r[col] for r in rows]
    print(f" {name:<10} {statistics.median(vals):7.0f} {max(vals):7.0f} ms")
print(" *TOTAL includes the", cfg.silence_end_ms, "ms end-of-speech wait. Target: median <= 4000 ms.")
