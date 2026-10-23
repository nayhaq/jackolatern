from datetime import datetime, time

import pytest

import persona
from mood import Mood


def at(hh, mm):
    return datetime(2026, 10, 30, hh, mm)


@pytest.fixture
def mood():
    return Mood(time(12, 0), time(15, 0), clock=lambda: at(13, 0))


def test_coffee_drains_from_noon(mood):
    assert mood.coffee_level(at(11, 0)) == 100
    assert mood.coffee_level(at(12, 0)) == 100
    assert mood.coffee_level(at(13, 0)) == 70
    assert mood.coffee_level(at(14, 30)) == 25
    assert mood.coffee_level(at(18, 0)) == 3  # floor


def test_phases(mood):
    assert mood.phase(at(11, 30)) == "before"
    assert mood.phase(at(13, 0)) == "voting"
    assert mood.phase(at(14, 31)) == "final30"
    assert mood.phase(at(15, 0)) == "after"


def test_snapshot_countdown_and_visitor(mood):
    mood.on_visitor()
    mood.on_turn()
    snap = mood.snapshot(at(14, 20))
    assert "Visitor #1, turn 1 of 4" in snap
    assert "Voting closes in 40 minutes" in snap
    assert "coffee level: 30%" in snap
    assert "campaign mode" not in snap


def test_final_30_campaign_mode(mood):
    assert "campaign mode" in mood.snapshot(at(14, 45))


def test_before_and_after_voting(mood):
    assert "Voting opens in 30 minutes" in mood.snapshot(at(11, 30))
    assert "Voting has closed" in mood.snapshot(at(15, 10))


def test_roast_angle_tracking(mood):
    found = mood.on_reply("Marketing A/B tested the googly eyes and called it a rebrand.")
    assert ("Marketing", "A/B testing") in found
    assert ("Marketing", "rebrands") in found
    snap = mood.snapshot(at(13, 0))
    assert "Marketing: A/B testing, rebrands" in snap


def test_angle_needs_department_mention(mood):
    # "budget" alone shouldn't count as a Finance roast unless Finance is named.
    assert mood.on_reply("I'm on a budget too, honestly.") == []


def test_hr_matches_whole_word_only(mood):
    assert mood.on_reply("Three hours of voting left, no policy on that.") == []
    assert ("HR", "policies") in mood.on_reply("HR wrote a policy about this pumpkin.")


def test_visitor_counter_resets_turns(mood):
    mood.on_visitor()
    mood.on_turn()
    mood.on_turn()
    mood.on_visitor()
    assert mood.visitor == 2 and mood.turn == 0


def test_every_department_has_angles():
    for dept, info in persona.ROAST_ANGLES.items():
        assert info["match"], dept
        assert len(info["angles"]) >= 3, dept
