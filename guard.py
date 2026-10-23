"""Input and output safety, the repeat detector, and pronunciation fixes for TTS.

Pure Python (no audio deps) so it can be unit tested anywhere.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Iterable

MAX_INPUT_CHARS = 300
MAX_SENTENCES = 3
SHORT_FRAGMENT_WORDS = 3
MAX_WORDS = 60
REPEAT_THRESHOLD = 0.75

# Whisper's usual output on silence or noise. Treated as "didn't catch that".
_HALLUCINATIONS = {
    "", "you", "thank you", "thanks", "thank you for watching", "thanks for watching",
    "bye", "okay", "ok", "uh", "um", "hmm", "so", "the end", "subtitles by the amara.org community",
}

_WAKE_PREFIX = re.compile(r"^\s*(hey|hi|hay|okay|ok)[\s,]+(jack|jac|jacques|jak)\b[\s,.!?]*", re.I)

# Kept short on purpose: the prompt does the real work, this catches the worst case.
_BLOCKLIST = re.compile(
    r"\b(fuck\w*|shit\w*|bitch\w*|asshole\w*|bastard\w*|dick\w*|cunt\w*|nigg\w*|fag\w*|retard\w*|"
    r"slut\w*|whore\w*|porn\w*|nazi\w*|kill yourself)\b",
    re.I,
)

_STAGE_DIRECTION = re.compile(r"\*[^*]{1,80}\*|\[[^\]]{1,80}\]")
_MARKDOWN = re.compile(r"[*#_`~>|]")
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF\U00002B00-\U00002BFF️‍]"
)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def clean_input(text: str) -> str:
    """Normalize a transcript. Returns "" when there's nothing usable."""
    t = " ".join((text or "").split())
    t = _WAKE_PREFIX.sub("", t)
    t = t[:MAX_INPUT_CHARS].strip()
    if t.lower().strip(" .!?,") in _HALLUCINATIONS:
        return ""
    if not re.search(r"[a-zA-Z]{2,}", t):
        return ""
    return t


def _cap_sentences(t: str) -> str:
    """Keep at most MAX_SENTENCES real sentences. Deadpan fragments of 3 words or fewer
    ("No?", "Classic.") don't count toward the cap; MAX_WORDS is the hard stop."""
    kept, counted, words = [], 0, 0
    for s in _SENTENCE_SPLIT.split(t):
        n = len(s.split())
        if words + n > MAX_WORDS or (n > SHORT_FRAGMENT_WORDS and counted >= MAX_SENTENCES):
            break
        kept.append(s)
        words += n
        if n > SHORT_FRAGMENT_WORDS:
            counted += 1
    if not kept:  # one run-on sentence: cut it at the word cap
        return " ".join(t.split()[:MAX_WORDS]).rstrip(",;:") + "."
    return " ".join(kept).strip()


def count_sentences(t: str) -> int:
    """Sentences that count toward the cap (fragments of 3 words or fewer are free)."""
    return sum(1 for s in _SENTENCE_SPLIT.split(t.strip()) if len(s.split()) > SHORT_FRAGMENT_WORDS)


def clean_output(text: str) -> str | None:
    """Make a reply safe to speak. Returns None if it must not be spoken."""
    t = text or ""
    t = re.sub(r"\*\*|__", "", t)  # bold markers first, so they aren't read as stage directions
    t = _STAGE_DIRECTION.sub(" ", t)
    t = _MARKDOWN.sub("", t)
    t = _EMOJI.sub("", t)
    t = " ".join(t.split())
    if not t:
        return None
    if _BLOCKLIST.search(t):
        return None
    return _cap_sentences(t) or None


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def is_repeat(text: str, recent: Iterable[str], threshold: float = REPEAT_THRESHOLD) -> str | None:
    """Return the earlier reply this one is too close to, or None."""
    for prev in recent:
        if similarity(text, prev) >= threshold:
            return prev
    return None


# ---------- pronunciation fixes for Piper ----------

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]


def two_digits(n: int) -> str:
    """Speak 0-99 as words; a leading-zero pair like 05 becomes 'oh five'."""
    if n < 20:
        return _ONES[n]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + ("" if ones == 0 else f" {_ONES[ones]}")


def model_number(num: str) -> str:
    """'5070' -> 'fifty seventy', '3250' -> 'thirty two fifty', '5005' -> 'fifty oh five'."""
    hi, lo = int(num[:2]), int(num[2:])
    lo_words = "hundred" if lo == 0 else (f"oh {_ONES[lo]}" if lo < 10 else two_digits(lo))
    return f"{two_digits(hi)} {lo_words}"


# Order matters: longer and more specific patterns first. Case-sensitive unless (?i).
_SAY_RULES: list[tuple[str, str]] = [
    (r"(?i)\bGB/s\b", "gigabytes per second"),
    (r"\bLYNK\+", "Link plus"),
    (r"\bGDDR(\d)\b", r"G D D R \1"),
    (r"\bDDR(\d)\b", r"D D R \1"),
    (r"\bRDIMMs?\b", "R dims"),
    (r"\bPCIe\b", "P C I E"),
    (r"\bNVMe\b", "N V M E"),
    (r"\bM\.2\b", "M dot two"),
    (r"\bGen(\d)\b", r"Gen \1"),
    (r"\b[xX](\d{1,2})\b", r"by \1"),
    (r"(?i)\b(\d[\d,]*)\s?MHz\b", r"\1 megahertz"),
    (r"(\d)\s?mm\b", r"\1 millimeter"),
    (r"(\d)\s?GB\b", r"\1 gigabytes"),
    (r"(\d)\s?TB\b", r"\1 terabytes"),
    (r"(\d)%", r"\1 percent"),
    (r"\bARGB\b", "A R G B"),
    (r"\bRGB\b", "R G B"),
    (r"\bOC\b", "O C"),
    (r"\bmATX\b", "micro A T X"),
    (r"\bAAA\b", "triple A"),
    (r"\bCOMPUTEX\b", "Computex"),
    (r"\bComfyUI\b", "Comfy U I"),
    (r"\bDLSS\b", "D L S S"),
    (r"\bCUDA\b", "Cooda"),
    (r"\bVRMs?\b", "V R M"),
    (r"\bGPUs\b", "G P U's"),
    (r"\bGPU\b", "G P U"),
    (r"\bCPUs?\b", "C P U"),
    (r"\bSSDs\b", "S S D's"),
    (r"\bSSD\b", "S S D"),
    (r"\bUSB\b", "U S B"),
    (r"\bPNY\b", "P N Y"),
    (r"\bRTX\b", "R T X"),
    (r"\bHR\b", "H R"),
    (r"\bIT\b", "I T"),
    (r"\bAI\b", "A I"),
    (r"\bCRM\b", "C R M"),
    (r"\bTLDR\b", "T L D R"),
    (r"\bA/B\b", "A B"),
    (r"\bTi\b", "tie"),
]
_SAY_COMPILED = [(re.compile(p), r) for p, r in _SAY_RULES]
# Product model numbers: "RTX 5070", "CS3250", "5070 Ti", "RTX 5080/5070 Ti".
_MODEL_NUM = re.compile(r"\b(RTX\s?|CS)?(\d{4})(?=\s?(?:Ti\b|/|,|\s|\.|$))")
_MODEL_PREFIX = {"RTX": "R T X ", "CS": "C S "}


def _say_model(m: re.Match) -> str:
    prefix = (m.group(1) or "").strip()
    num = m.group(2)
    # Plain years and quantities like 1985 or 2026 stay as-is unless they have a product prefix
    # or are followed by 'Ti'.
    followed_by_ti = m.string[m.end():m.end() + 3].strip().startswith("Ti")
    if not prefix and not followed_by_ti:
        return m.group(0)
    return _MODEL_PREFIX.get(prefix, "") + model_number(num)


def say_friendly(text: str) -> str:
    """Rewrite tech terms so Piper pronounces them the way people say them."""
    # "RTX 5080/5070 Ti/5070" -> "RTX 5080, RTX 5070 Ti, RTX 5070" so every number gets a prefix.
    t = text
    while True:
        new = re.sub(r"\b(RTX\s?\d{4}(?:\s?Ti)?)/(?=\d{4})", r"\1, RTX ", t)
        if new == t:
            break
        t = new
    t = _MODEL_NUM.sub(_say_model, t)
    for pattern, repl in _SAY_COMPILED:
        t = pattern.sub(repl, t)
    return " ".join(t.split())
