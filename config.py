"""Load Jack's settings from .env into a typed Config.

Import this module before anything that reads Hugging Face env vars (stt.py),
so HF_HUB_OFFLINE from .env takes effect.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")


class ConfigError(Exception):
    pass


def _str(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _float(name: str, default: float) -> float:
    raw = _str(name)
    try:
        return float(raw) if raw else default
    except ValueError as e:
        raise ConfigError(f"{name} must be a number, got {raw!r}") from e


def _int(name: str, default: int) -> int:
    return int(_float(name, default))


def _bool(name: str, default: bool) -> bool:
    raw = _str(name).lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _clock(name: str, default: str) -> time:
    raw = _str(name, default)
    try:
        hh, mm = raw.split(":")
        return time(int(hh), int(mm))
    except ValueError as e:
        raise ConfigError(f"{name} must look like 12:00, got {raw!r}") from e


def _path(name: str, default: str) -> Path:
    p = Path(_str(name, default))
    return p if p.is_absolute() else ROOT / p


@dataclass(frozen=True)
class Config:
    api_key: str
    model: str
    llm_timeout_s: float
    llm_thinking: str

    wake_engine: str
    wake_model_path: Path
    wake_threshold: float
    wake_cooldown_s: float
    picovoice_access_key: str

    mic_device: str
    speaker_device: str

    whisper_model: str
    whisper_dir: Path
    offline_models: bool

    piper_voice_path: Path
    piper_length_scale: float
    piper_exe: str

    vad_aggressiveness: int
    silence_end_ms: int
    max_record_s: float
    first_listen_s: float
    followup_window_s: float
    max_turns: int

    voting_start: time
    voting_end: time

    log_transcripts: bool
    log_dir: Path
    cache_dir: Path


def load(require_api_key: bool = True, require_models: bool = True) -> Config:
    cfg = Config(
        api_key=_str("ANTHROPIC_API_KEY"),
        model=_str("MODEL", "claude-haiku-5-5"),
        llm_timeout_s=_float("LLM_TIMEOUT_S", 8.0),
        llm_thinking=_str("LLM_THINKING", "off").lower(),
        wake_engine=_str("WAKE_ENGINE", "openwakeword").lower(),
        wake_model_path=_path("WAKE_MODEL_PATH", "models/hey_jack.onnx"),
        wake_threshold=_float("WAKE_THRESHOLD", 0.5),
        wake_cooldown_s=_float("WAKE_COOLDOWN_S", 2.0),
        picovoice_access_key=_str("PICOVOICE_ACCESS_KEY"),
        mic_device=_str("MIC_DEVICE", "Jabra"),
        speaker_device=_str("SPEAKER_DEVICE", "Jabra"),
        whisper_model=_str("WHISPER_MODEL", "base.en"),
        whisper_dir=_path("WHISPER_DIR", "models/whisper"),
        offline_models=_bool("HF_HUB_OFFLINE", False),
        piper_voice_path=_path("PIPER_VOICE_PATH", "models/piper/en_US-ryan-medium.onnx"),
        piper_length_scale=_float("PIPER_LENGTH_SCALE", 1.1),
        piper_exe=_str("PIPER_EXE"),
        vad_aggressiveness=_int("VAD_AGGRESSIVENESS", 2),
        silence_end_ms=_int("SILENCE_END_MS", 800),
        max_record_s=_float("MAX_RECORD_S", 8.0),
        first_listen_s=_float("FIRST_LISTEN_S", 5.0),
        followup_window_s=_float("FOLLOWUP_WINDOW_S", 8.0),
        max_turns=_int("MAX_TURNS", 4),
        voting_start=_clock("VOTING_START", "12:00"),
        voting_end=_clock("VOTING_END", "15:00"),
        log_transcripts=_bool("LOG_TRANSCRIPTS", False),
        log_dir=_path("LOG_DIR", "logs"),
        cache_dir=_path("CACHE_DIR", "cache"),
    )
    problems = []
    if require_api_key and not cfg.api_key:
        problems.append("ANTHROPIC_API_KEY is empty. Copy config.example.env to .env and paste the key.")
    if cfg.llm_thinking not in ("off", "adaptive"):
        problems.append("LLM_THINKING must be 'off' or 'adaptive'.")
    if cfg.wake_engine not in ("openwakeword", "porcupine"):
        problems.append("WAKE_ENGINE must be 'openwakeword' or 'porcupine'.")
    if not 0 <= cfg.vad_aggressiveness <= 3:
        problems.append("VAD_AGGRESSIVENESS must be 0-3.")
    if require_models:
        if not cfg.wake_model_path.exists():
            problems.append(f"Wake model not found: {cfg.wake_model_path} (see models/README.md).")
        if cfg.wake_engine == "porcupine" and not cfg.picovoice_access_key:
            problems.append("WAKE_ENGINE=porcupine needs PICOVOICE_ACCESS_KEY.")
        if not cfg.piper_voice_path.exists() and not cfg.piper_exe:
            problems.append(f"Piper voice not found: {cfg.piper_voice_path} (run setup.ps1).")
    if problems:
        raise ConfigError("\n".join(problems))
    cfg.log_dir.mkdir(parents=True, exist_ok=True)
    cfg.cache_dir.mkdir(parents=True, exist_ok=True)
    return cfg
