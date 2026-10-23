"""Jack.think(): guard, repeat retry, error mapping, and session/mood updates (no network)."""
import pytest

import config
from brain import BrainOverloaded


class FakeBrain:
    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def reply(self, history, user_text, status, nudge=None):
        self.calls.append({"history": list(history), "text": user_text, "status": status, "nudge": nudge})
        r = self.replies.pop(0)
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def jack(monkeypatch, tmp_path):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("LOG_DIR", str(tmp_path / "logs"))
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    from jack import Jack

    j = Jack(config.load(require_models=False), text_mode=True)
    j.mood.on_visitor()
    return j


def test_good_reply_updates_session_and_mood(jack):
    jack.brain = FakeBrain(["Marketing A/B tested my googly eyes. Rude."])
    reply, status = jack.think("Roast Marketing")
    assert status == "ok" and reply.startswith("Marketing")
    assert jack.session.history[-1] == {"role": "assistant", "content": reply}
    assert jack.mood.used_angles["Marketing"] == ["A/B testing"]
    assert "Visitor #1, turn 1" in jack.brain.calls[0]["status"]


def test_repeat_triggers_one_retry_with_nudge(jack):
    first = "Finance approved my pumpkin in triplicate. Classic Finance."
    jack.recent.append(first)
    jack.brain = FakeBrain([first, "Finance cut my coffee budget. I'm running on fumes and spreadsheets."])
    reply, status = jack.think("Roast Finance")
    assert status == "ok" and "coffee budget" in reply
    assert len(jack.brain.calls) == 2
    assert first in jack.brain.calls[1]["nudge"]


def test_blocked_reply(jack):
    jack.brain = FakeBrain(["That's a shitty pumpkin."])
    reply, status = jack.think("Say something rude")
    assert reply is None and status == "err_blocked"
    assert jack.session.history == []


def test_brain_error_maps_to_line(jack):
    jack.brain = FakeBrain([BrainOverloaded("529")])
    assert jack.think("hello") == (None, "err_overloaded")


def test_follow_up_sends_history(jack):
    jack.brain = FakeBrain(["PNY makes GPUs, memory, and SSDs. Mostly GPUs in my heart.",
                            "The Slim cards. Small PC, big energy."])
    jack.think("What does PNY make?")
    jack.think("Which one fits a small PC?")
    second = jack.brain.calls[1]
    assert len(second["history"]) == 2
    assert "turn 2" in second["status"]
