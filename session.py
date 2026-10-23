"""One visitor's conversation. Wiped when they walk away or hit the turn limit."""
from __future__ import annotations


class Session:
    def __init__(self, max_turns: int = 4):
        self.max_turns = max_turns
        self.history: list[dict] = []

    @property
    def turns(self) -> int:
        return len(self.history) // 2

    def full(self) -> bool:
        return self.turns >= self.max_turns

    def add_turn(self, user_text: str, reply: str) -> None:
        self.history.append({"role": "user", "content": user_text})
        self.history.append({"role": "assistant", "content": reply})

    def reset(self) -> None:
        self.history = []
