"""Jack's voice. Piper (local neural) first, then piper.exe, then Windows SAPI as a last resort."""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

import numpy as np

from audio import load_wav

log = logging.getLogger("jack.tts")


class Voice:
    def __init__(self, model_path: Path, length_scale: float = 1.1, piper_exe: str = ""):
        self.model_path = Path(model_path)
        self.length_scale = length_scale
        self.piper_exe = piper_exe
        self.engine = ""
        self._voice = None
        self._syn_config = None
        self._sapi = None
        self._load()
        log.info("TTS engine: %s", self.engine)

    def _load(self) -> None:
        if self.model_path.exists():
            try:
                from piper import PiperVoice, SynthesisConfig

                self._voice = PiperVoice.load(self.model_path)
                self._syn_config = SynthesisConfig(length_scale=self.length_scale)
                self.engine = "piper"
                return
            except Exception as e:  # noqa: BLE001 - any failure falls through to the next engine
                log.warning("Piper Python API unavailable (%s)", e)
            if self.piper_exe and Path(self.piper_exe).exists():
                self.engine = "piper-exe"
                return
        try:
            import pyttsx3

            self._sapi = pyttsx3.init()
            self._sapi.setProperty("rate", 165)
            self.engine = "sapi"
        except Exception as e:  # noqa: BLE001
            raise RuntimeError(f"No TTS engine available: {e}") from e

    def synth(self, text: str) -> tuple[np.ndarray, int]:
        if self.engine == "piper":
            chunks = list(self._voice.synthesize(text, syn_config=self._syn_config))
            if not chunks:
                return np.zeros(0, dtype=np.int16), 22050
            audio = np.concatenate([c.audio_int16_array for c in chunks])
            return audio, chunks[0].sample_rate
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "say.wav"
            if self.engine == "piper-exe":
                subprocess.run(
                    [self.piper_exe, "--model", str(self.model_path), "--length_scale",
                     str(self.length_scale), "--output_file", str(out)],
                    input=text.encode("utf-8"), check=True, capture_output=True, timeout=30,
                )
            else:
                self._sapi.save_to_file(text, str(out))
                self._sapi.runAndWait()
            return load_wav(out)
