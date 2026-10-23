"""Jack's afternoon "mood": anonymous counters that change through the day.

Holds numbers and angle labels only. Never stores what visitors said.
"""
from __future__ import annotations

import re
from datetime import datetime, time, timedelta
from typing import Callable

import persona

COFFEE_DRAIN_PER_HOUR = 30.0
COFFEE_FLOOR = 3


def _minutes_between(a: datetime, b: datetime) -> int:
    return int((b - a).total_seconds() // 60)


def _contains(text: str, phrase: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(phrase) + r"(?![a-z])", text) is not None


class Mood:
    def __init__(self, voting_start: time, voting_end: time,
                 clock: Callable[[], datetime] = datetime.now,
                 roast_angles: dict | None = None, max_turns: int = 4):
        self.clock = clock
        self.voting_start = voting_start
        self.voting_end = voting_end
        self.roast_angles = roast_angles if roast_angles is not None else persona.ROAST_ANGLES
        self.visitor = 0
        self.turn = 0
        self.max_turns = max_turns
        self.used_angles: dict[str, list[str]] = {}
        self.started_at = clock()

    # ----- events -----
    def on_visitor(self) -> None:
        self.visitor += 1
        self.turn = 0

    def on_turn(self) -> None:
        self.turn += 1

    def on_reply(self, reply: str) -> list[tuple[str, str]]:
        """Record which roast angles a reply used. Returns the (department, angle) pairs found."""
        text = reply.lower()
        found = []
        for dept, info in self.roast_angles.items():
            if not any(_contains(text, m) for m in info["match"]):
                continue
            for angle, keywords in info["angles"].items():
                if any(_contains(text, k) for k in keywords):
                    used = self.used_angles.setdefault(dept, [])
                    if angle not in used:
                        used.append(angle)
                    found.append((dept, angle))
        return found

    # ----- derived values -----
    def _today(self, t: time, now: datetime) -> datetime:
        return now.replace(hour=t.hour, minute=t.minute, second=0, microsecond=0)

    def coffee_level(self, now: datetime | None = None) -> int:
        now = now or self.clock()
        start = self._today(self.voting_start, now)
        if now <= start:
            return 100
        hours = (now - start).total_seconds() / 3600
        return max(COFFEE_FLOOR, round(100 - COFFEE_DRAIN_PER_HOUR * hours))

    def phase(self, now: datetime | None = None) -> str:
        now = now or self.clock()
        start, end = self._today(self.voting_start, now), self._today(self.voting_end, now)
        if now < start:
            return "before"
        if now >= end:
            return "after"
        if end - now <= timedelta(minutes=30):
            return "final30"
        return "voting"

    def snapshot(self, now: datetime | None = None) -> str:
        """The live status block sent to Claude with every request."""
        now = now or self.clock()
        start, end = self._today(self.voting_start, now), self._today(self.voting_end, now)
        phase = self.phase(now)
        clock = now.strftime("%I:%M %p").lstrip("0")
        lines = [
            "Live status:",
            f"Visitor #{self.visitor}, turn {max(self.turn, 1)} of {self.max_turns}. Time {clock}.",
        ]
        if phase == "before":
            lines.append(f"Voting opens in {_minutes_between(now, start)} minutes. You're warming up.")
        elif phase == "after":
            lines.append("Voting has closed. You're off the clock and reflective about your internship.")
        else:
            lines.append(f"Voting closes in {_minutes_between(now, end)} minutes.")
        if phase == "final30":
            lines.append("Final 30 minutes: you're in campaign mode. Roasts turn into short campaign "
                         "speeches for why people should vote for you.")
        lines.append(f"Your coffee level: {self.coffee_level(now)}%.")
        if self.visitor >= 50:
            lines.append(f"You've talked to {self.visitor} people today. Social battery: low.")
        if self.used_angles:
            used = "; ".join(f"{d}: {', '.join(a)}" for d, a in self.used_angles.items())
            lines.append(f"Roast angles already used today: {used}. Pick different ones.")
        else:
            lines.append("You haven't roasted anyone yet today.")
        return "\n".join(lines)
