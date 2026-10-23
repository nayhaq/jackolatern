"""Offline checks on persona content and the session object."""
import guard
import persona
from session import Session


def test_prompt_contains_every_topic_and_department():
    prompt = persona.build_system_prompt()
    for card in persona.TOPICS:
        assert card["title"] in prompt
    for dept in persona.ROAST_ANGLES:
        assert dept in prompt


def test_ten_topic_cards():
    assert len(persona.TOPICS) == 10


def test_fixed_line_groups_have_variants():
    required = {"chirp", "filler", "err_offline", "err_timeout", "err_overloaded",
                "err_didnt_catch", "err_too_long", "err_blocked", "err_restart"}
    assert required <= set(persona.FIXED_LINES)
    for group, lines in persona.FIXED_LINES.items():
        assert len(lines) >= 4, group
        assert len(set(lines)) == len(lines), group


def test_fixed_lines_pass_output_guard():
    for lines in persona.FIXED_LINES.values():
        for line in lines:
            assert guard.clean_output(line) == line, line


def test_session_turn_limit():
    s = Session(max_turns=2)
    s.add_turn("q1", "a1")
    assert not s.full()
    s.add_turn("q2", "a2")
    assert s.full()
    assert s.history[0] == {"role": "user", "content": "q1"}
    s.reset()
    assert s.history == [] and not s.full()
