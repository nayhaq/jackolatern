"""'Hey Jack' detection. Runs fully on the laptop.

Default engine is openWakeWord with a custom hey_jack.onnx model. Porcupine is the
fallback (Phase 2.5 of the plan) and keeps the same interface.
"""
from __future__ import annotations

import time

import numpy as np


class WakeDetector:
    """openWakeWord. process() takes one 1280-sample 16 kHz int16 block."""

    def __init__(self, model_path: str, threshold: float = 0.5, cooldown_s: float = 2.0):
        from openwakeword.model import Model

        self.model = Model(wakeword_models=[str(model_path)], inference_framework="onnx")
        self.threshold = threshold
        self.cooldown_s = cooldown_s
        self._last_fire = 0.0
        self.last_score = 0.0

    def process(self, block: np.ndarray) -> bool:
        scores = self.model.predict(block)
        self.last_score = float(max(scores.values())) if scores else 0.0
        if self.last_score < self.threshold:
            return False
        now = time.monotonic()
        if now - self._last_fire < self.cooldown_s:
            return False
        self._last_fire = now
        return True

    def reset(self) -> None:
        self.model.reset()
        self._last_fire = time.monotonic()


class PorcupineDetector:
    """Picovoice Porcupine fallback. Needs PICOVOICE_ACCESS_KEY and a 'Hey Jack' .ppn keyword file."""

    def __init__(self, keyword_path: str, access_key: str, threshold: float = 0.5, cooldown_s: float = 2.0):
        import pvporcupine

        self.engine = pvporcupine.create(access_key=access_key, keyword_paths=[str(keyword_path)],
                                         sensitivities=[threshold])
        self.frame = self.engine.frame_length
        self.cooldown_s = cooldown_s
        self._buf = np.zeros(0, dtype=np.int16)
        self._last_fire = 0.0
        self.last_score = 0.0

    def process(self, block: np.ndarray) -> bool:
        self._buf = np.concatenate([self._buf, block])
        fired = False
        while len(self._buf) >= self.frame:
            chunk, self._buf = self._buf[:self.frame], self._buf[self.frame:]
            if self.engine.process(chunk.tolist()) >= 0:
                fired = True
        self.last_score = 1.0 if fired else 0.0
        if not fired or time.monotonic() - self._last_fire < self.cooldown_s:
            return False
        self._last_fire = time.monotonic()
        return True

    def reset(self) -> None:
        self._buf = np.zeros(0, dtype=np.int16)
        self._last_fire = time.monotonic()


def make_detector(cfg):
    if cfg.wake_engine == "porcupine":
        return PorcupineDetector(cfg.wake_model_path, cfg.picovoice_access_key,
                                 cfg.wake_threshold, cfg.wake_cooldown_s)
    return WakeDetector(cfg.wake_model_path, cfg.wake_threshold, cfg.wake_cooldown_s)
