"""record_utterance and resampling logic with a fake mic (no audio hardware needed)."""
import sys
import types

import numpy as np
import pytest

try:
    import sounddevice  # noqa: F401
except (ImportError, OSError):  # no PortAudio on CI/sandbox: stub just enough to import audio.py
    sys.modules["sounddevice"] = types.SimpleNamespace(
        InputStream=None, PortAudioError=Exception, query_devices=None, query_hostapis=None,
        play=None, wait=None, stop=None)

audio = pytest.importorskip("audio")

SPEECH, QUIET = True, False


class FakeMic:
    """Feeds blocks from a script of voiced/unvoiced 80 ms blocks."""

    def __init__(self, script):
        self.script = list(script)
        self.reads = 0

    def read(self, timeout=2.0):
        self.reads += 1
        if not self.script:
            raise audio.AudioDeviceError("script ran out")
        voiced = self.script.pop(0)
        return np.full(audio.BLOCK, 1000 if voiced else 0, dtype=np.int16)


class FakeVad:
    def frames(self, block):
        return [bool(block[0])] * audio.FRAMES_PER_BLOCK


def blocks(ms, voiced):
    return [voiced] * (ms // 80)


def test_nobody_speaks_returns_none():
    mic = FakeMic(blocks(2000, QUIET))
    assert audio.record_utterance(mic, FakeVad(), start_timeout_s=1.0) is None
    assert mic.reads == 1000 // 80 + 1


def test_cough_does_not_start_recording():
    mic = FakeMic(blocks(160, SPEECH) + blocks(2000, QUIET))
    assert audio.record_utterance(mic, FakeVad(), start_timeout_s=1.5) is None


def test_records_until_silence():
    script = blocks(400, QUIET) + blocks(1600, SPEECH) + blocks(960, QUIET) + blocks(800, SPEECH)
    utt = audio.record_utterance(FakeMic(script), FakeVad(), start_timeout_s=3,
                                 silence_end_ms=800, max_record_s=8)
    assert utt is not None and not utt.hit_max
    seconds = len(utt.audio) / audio.TARGET_SR
    assert 2.0 <= seconds <= 3.0  # ~0.4 s preroll + 1.6 s speech + 0.8 s trailing silence


def test_hits_max_length():
    utt = audio.record_utterance(FakeMic(blocks(12000, SPEECH)), FakeVad(), start_timeout_s=3,
                                 max_record_s=8)
    assert utt.hit_max


@pytest.mark.parametrize("in_sr", [48000, 44100, 16000])
def test_resample_to_16k_blocks(in_sr):
    mic = object.__new__(audio.MicStream)
    from math import gcd
    g = gcd(in_sr, audio.TARGET_SR)
    mic._up, mic._down = audio.TARGET_SR // g, in_sr // g
    mic._in_block = audio.BLOCK * in_sr // audio.TARGET_SR
    import queue
    mic._q = queue.Queue()
    t = np.arange(mic._in_block) / in_sr
    mic._q.put((np.sin(2 * np.pi * 440 * t) * 10000).astype(np.int16))
    out = mic.read()
    assert out.dtype == np.int16 and len(out) == audio.BLOCK
    assert 5000 < np.abs(out).max() <= 10500
