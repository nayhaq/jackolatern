"""Mic capture (any device rate -> 16 kHz blocks), speech detection, and playback."""
from __future__ import annotations

import collections
import queue
import time
import wave
from dataclasses import dataclass
from math import gcd
from pathlib import Path

import numpy as np
import sounddevice as sd
import webrtcvad
from scipy.signal import resample_poly

TARGET_SR = 16000
BLOCK = 1280            # 80 ms at 16 kHz: openWakeWord's preferred frame
FRAME = 320             # 20 ms at 16 kHz: webrtcvad frame
FRAMES_PER_BLOCK = BLOCK // FRAME
FRAME_MS = 20

# Host APIs in order of preference on Windows. MME resamples for us and is the most forgiving.
_HOSTAPI_PREFERENCE = ["MME", "Windows DirectSound", "Windows WASAPI"]


class AudioDeviceError(Exception):
    pass


def find_device(name_substring: str, kind: str) -> int | None:
    """Index of the first device whose name contains name_substring. None = system default."""
    if not name_substring:
        return None
    hostapis = sd.query_hostapis()
    matches = []
    for idx, dev in enumerate(sd.query_devices()):
        channels = dev["max_input_channels"] if kind == "input" else dev["max_output_channels"]
        if channels > 0 and name_substring.lower() in dev["name"].lower():
            api = hostapis[dev["hostapi"]]["name"]
            rank = _HOSTAPI_PREFERENCE.index(api) if api in _HOSTAPI_PREFERENCE else len(_HOSTAPI_PREFERENCE)
            matches.append((rank, idx))
    if not matches:
        return None
    return sorted(matches)[0][1]


def device_label(index: int | None, kind: str) -> str:
    info = sd.query_devices(index, kind) if index is not None else sd.query_devices(kind=kind)
    api = sd.query_hostapis()[info["hostapi"]]["name"]
    return f"{info['name']} [{api}, {int(info['default_samplerate'])} Hz]"


def _to_int16(x: np.ndarray) -> np.ndarray:
    return np.clip(np.round(x), -32768, 32767).astype(np.int16)


class MicStream:
    """Captures mono audio at the device's native rate and hands out 16 kHz int16 blocks."""

    def __init__(self, device: int | None = None, max_blocks: int = 200):
        self.device = device
        info = sd.query_devices(device, "input") if device is not None else sd.query_devices(kind="input")
        self.in_sr = int(info["default_samplerate"])
        g = gcd(self.in_sr, TARGET_SR)
        self._up, self._down = TARGET_SR // g, self.in_sr // g
        self._in_block = BLOCK * self.in_sr // TARGET_SR
        self._q: queue.Queue[np.ndarray] = queue.Queue(maxsize=max_blocks)
        self._stream: sd.InputStream | None = None
        self.overflows = 0

    def start(self) -> "MicStream":
        self._stream = sd.InputStream(
            samplerate=self.in_sr, channels=1, dtype="int16", blocksize=self._in_block,
            device=self.device, callback=self._callback,
        )
        self._stream.start()
        return self

    def close(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _callback(self, indata, frames, time_info, status) -> None:
        if status.input_overflow:
            self.overflows += 1
        data = indata[:, 0].copy()
        try:
            self._q.put_nowait(data)
        except queue.Full:  # we fell behind: drop the oldest block
            try:
                self._q.get_nowait()
            except queue.Empty:
                pass
            self._q.put_nowait(data)

    def read(self, timeout: float = 2.0) -> np.ndarray:
        """Next 1280-sample (80 ms) block at 16 kHz. Raises AudioDeviceError if the mic goes quiet."""
        try:
            raw = self._q.get(timeout=timeout)
        except queue.Empty as e:
            raise AudioDeviceError("no audio from mic (unplugged or grabbed by another app?)") from e
        if self._up == self._down:
            out = raw
        else:
            out = _to_int16(resample_poly(raw.astype(np.float32), self._up, self._down))
        if len(out) != BLOCK:
            out = np.pad(out, (0, max(0, BLOCK - len(out))))[:BLOCK]
        return out

    def drain(self) -> None:
        while True:
            try:
                self._q.get_nowait()
            except queue.Empty:
                return


class Vad:
    def __init__(self, aggressiveness: int = 2):
        self._vad = webrtcvad.Vad(aggressiveness)

    def frames(self, block: np.ndarray) -> list[bool]:
        return [self._vad.is_speech(block[i:i + FRAME].tobytes(), TARGET_SR)
                for i in range(0, BLOCK, FRAME)]


def rms_dbfs(block: np.ndarray) -> float:
    rms = np.sqrt(np.mean(block.astype(np.float64) ** 2)) + 1e-9
    return 20 * np.log10(rms / 32768)


@dataclass
class Utterance:
    audio: np.ndarray       # int16, 16 kHz
    hit_max: bool           # speaker was still going when MAX_RECORD_S ran out
    record_ms: int


def record_utterance(mic: MicStream, vad: Vad, start_timeout_s: float, silence_end_ms: int = 800,
                     max_record_s: float = 8.0, start_window_ms: int = 500,
                     start_voiced_ms: int = 300, preroll_ms: int = 400) -> Utterance | None:
    """Wait up to start_timeout_s for speech, then record until silence_end_ms of quiet.

    Speech "starts" when start_voiced_ms of the last start_window_ms is voiced, so a cough or a
    dropped tray doesn't count. Returns None if nobody spoke.
    """
    window: collections.deque[bool] = collections.deque(maxlen=start_window_ms // FRAME_MS)
    preroll: collections.deque[np.ndarray] = collections.deque(maxlen=max(1, preroll_ms // 80))
    waited_ms = 0
    while True:
        block = mic.read()
        preroll.append(block)
        window.extend(vad.frames(block))
        waited_ms += 80
        if sum(window) * FRAME_MS >= start_voiced_ms:
            break
        if waited_ms >= start_timeout_s * 1000:
            return None

    blocks = list(preroll)
    silence_ms = 0
    t0 = time.monotonic()
    speech_ms = len(blocks) * 80
    while True:
        block = mic.read()
        blocks.append(block)
        speech_ms += 80
        for voiced in vad.frames(block):
            silence_ms = 0 if voiced else silence_ms + FRAME_MS
        if silence_ms >= silence_end_ms:
            hit_max = False
            break
        if speech_ms >= max_record_s * 1000:
            hit_max = True
            break
    return Utterance(np.concatenate(blocks), hit_max, int((time.monotonic() - t0) * 1000))


# ---------- playback ----------

def load_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() > 1:
            data = data.reshape(-1, w.getnchannels())[:, 0]
    return data.copy(), sr


def save_wav(path: Path, audio: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(audio.astype(np.int16).tobytes())


class Player:
    def __init__(self, device: int | None = None):
        self.device = device
        info = sd.query_devices(device, "output") if device is not None else sd.query_devices(kind="output")
        self.device_sr = int(info["default_samplerate"])

    def _start(self, audio: np.ndarray, sr: int) -> None:
        try:
            sd.play(audio, sr, device=self.device)
        except sd.PortAudioError:
            # Some host APIs refuse rates the device doesn't run at natively. Resample and retry.
            g = gcd(sr, self.device_sr)
            res = _to_int16(resample_poly(audio.astype(np.float32), self.device_sr // g, sr // g))
            sd.play(res, self.device_sr, device=self.device)

    def play(self, audio: np.ndarray, sr: int) -> None:
        self._start(audio, sr)
        sd.wait()

    def play_async(self, audio: np.ndarray, sr: int) -> None:
        self._start(audio, sr)

    @staticmethod
    def wait() -> None:
        sd.wait()

    @staticmethod
    def stop() -> None:
        sd.stop()
