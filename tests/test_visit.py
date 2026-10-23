"""Jack.visit() control flow with fake mic, STT, voice, and player (no audio hardware)."""
import json
import types

import numpy as np
import pytest

import config
from brain import BrainOffline


class Utt:
    def __init__(self, hit_max=False):
        self.audio = np.zeros(16000, dtype=np.int16)
        self.hit_max = hit_max
        self.record_ms = 1200


class FakeBrain:
    def __init__(self, replies):
        self.replies = list(replies)

    def reply(self, history, user_text, status, nudge=None):
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


class Recorder:
    def __init__(self):
        self.played = []

    def play(self, audio, sr):
        self.played.append(("play", audio))

    def play_async(self, audio, sr):
        self.played.append(("async", audio))

    def wait(self):
        pass


class Lines:
    def pick(self, group):
        return group, group, 22050  # the "audio" is the group name, so tests can read it


@pytest.fixture
def jack(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("LOG_TRANSCRIPTS", "false")
    import jack as jack_mod

    monkeypatch.setattr(jack_mod, "DEAF_AFTER_SPEAKING_S", 0)
    j = jack_mod.Jack(config.load(require_models=False), text_mode=True)
    j.player = Recorder()
    j.lines = Lines()
    j.mic = types.SimpleNamespace(drain=lambda: None)
    j.vad = None
    j.wake = types.SimpleNamespace(last_score=0.9)
    j.voice = types.SimpleNamespace(synth=lambda text: (f"SPOKEN:{text}", 22050))
    return j


def script(j, utterances, transcripts, replies):
    utts = list(utterances)
    heard = list(transcripts)
    j.audio = types.SimpleNamespace(record_utterance=lambda *a, **k: utts.pop(0) if utts else None)
    j.stt = types.SimpleNamespace(transcribe=lambda audio: heard.pop(0))
    j.brain = FakeBrain(replies)


def spoken(j):
    return [a for kind, a in j.player.played if kind == "play"]


def test_two_turn_visit_then_walk_away(jack):
    script(jack, [Utt(), Utt()], ["Hey Jack, what does PNY make?", "Which is best?"],
           ["GPUs, memory, SSDs. Mostly GPUs in my heart.", "The RTX 5090. Obviously."])
    jack.visit()
    out = spoken(jack)
    assert out[0] == "chirp"
    assert out[1] == "SPOKEN:G P U's, memory, S S D's. Mostly G P U's in my heart."
    assert out[2] == "SPOKEN:The R T X fifty ninety. Obviously."
    assert [a for k, a in jack.player.played if k == "async"] == ["filler", "filler"]
    assert jack.session.history == []  # wiped when they walked away
    assert jack.mood.visitor == 1


def test_offline_plays_error_line_and_ends_visit(jack):
    script(jack, [Utt(), Utt()], ["what does PNY make", "hello?"], [BrainOffline("down")])
    jack.visit()
    assert spoken(jack) == ["chirp", "err_offline"]


def test_didnt_catch_twice_ends_visit(jack):
    script(jack, [Utt(), Utt(), Utt()], ["Thank you.", "", "never reached"], [])
    jack.visit()
    assert spoken(jack) == ["chirp", "err_didnt_catch", "err_didnt_catch"]


def test_too_long_then_retry(jack):
    script(jack, [Utt(hit_max=True), Utt()], ["Roast Sales"], ["Sales promised this joke by Friday."])
    jack.visit()
    assert spoken(jack) == ["chirp", "err_too_long", "SPOKEN:Sales promised this joke by Friday."]


def test_turn_limit(jack):
    script(jack, [Utt()] * 6, [f"question {i}" for i in range(6)],
           ["GPUs are my love language.", "Coffee is at ninety percent.", "Marketing tried a rebrand again.",
            "Finance approved this sentence.", "Sales promised a fifth turn.", "HR is watching me."])
    jack.visit()
    assert len(spoken(jack)) == 1 + jack.cfg.max_turns


def test_turn_log_hides_transcripts(jack):
    script(jack, [Utt()], ["what does PNY make"], ["GPUs. Obviously."])
    jack.visit()
    lines = [json.loads(line) for f in jack.cfg.log_dir.glob("turns-*.jsonl") for line in f.read_text().splitlines()]
    assert lines and lines[0]["status"] == "ok"
    assert "heard" not in lines[0] and "reply" not in lines[0]
    assert lines[0]["total_ms"] >= jack.cfg.silence_end_ms
