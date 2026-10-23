"""Speech-to-text with faster-whisper, on the laptop CPU. Audio never leaves the machine."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

# Biases Whisper toward words visitors are likely to say.
VOCAB_HINT = "Hey Jack. PNY, GPU, RTX, GeForce, NVIDIA, SSD, DDR5, Marketing, Finance, HR, Sales."


class Transcriber:
    def __init__(self, model_name: str = "base.en", download_dir: Path | None = None,
                 offline: bool = False):
        self.model = WhisperModel(
            model_name, device="cpu", compute_type="int8",
            download_root=str(download_dir) if download_dir else None,
            local_files_only=offline,
        )
        self.transcribe(np.zeros(16000, dtype=np.int16))  # warm-up so the first visitor isn't slow

    def transcribe(self, audio: np.ndarray) -> str:
        samples = audio.astype(np.float32) / 32768.0
        segments, _info = self.model.transcribe(
            samples, language="en", beam_size=1, vad_filter=False,
            condition_on_previous_text=False, initial_prompt=VOCAB_HINT,
        )
        return " ".join(s.text.strip() for s in segments).strip()
