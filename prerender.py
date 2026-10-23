"""Render persona.FIXED_LINES to WAV files so chirps, fillers, and error lines play instantly
and work with no network.

    python prerender.py          # render anything new or changed
    python prerender.py --force  # re-render everything (after changing voice)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import random
from pathlib import Path

import numpy as np

import persona
from audio import load_wav, save_wav
from guard import say_friendly

log = logging.getLogger("jack.prerender")


def _key(text: str, voice_id: str) -> str:
    return hashlib.sha1(f"{voice_id}|{text}".encode()).hexdigest()[:12]


def render_all(voice, cache_dir: Path, force: bool = False) -> int:
    """Render missing or stale lines. Returns how many files were (re)rendered."""
    voice_id = f"{voice.engine}:{voice.model_path.name}:{voice.length_scale}"
    manifest_path = cache_dir / "manifest.json"
    old = {} if force or not manifest_path.exists() else json.loads(manifest_path.read_text())
    new: dict[str, list[dict]] = {}
    rendered = 0
    for group, lines in persona.FIXED_LINES.items():
        new[group] = []
        for text in lines:
            key = _key(text, voice_id)
            path = cache_dir / group / f"{key}.wav"
            if not path.exists() or key not in {e["key"] for e in old.get(group, [])}:
                audio, sr = voice.synth(say_friendly(text))
                save_wav(path, audio, sr)
                rendered += 1
            new[group].append({"key": key, "text": text, "file": path.relative_to(cache_dir).as_posix()})
    manifest_path.write_text(json.dumps(new, indent=2))
    return rendered


class FixedLines:
    """Random pick per group, never the same variant twice in a row."""

    def __init__(self, cache_dir: Path):
        manifest = json.loads((cache_dir / "manifest.json").read_text())
        self._audio: dict[str, list[tuple[str, np.ndarray, int]]] = {}
        for group, entries in manifest.items():
            self._audio[group] = []
            for e in entries:
                audio, sr = load_wav(cache_dir / e["file"])
                self._audio[group].append((e["text"], audio, sr))
        self._last: dict[str, int] = {}

    def pick(self, group: str) -> tuple[str, np.ndarray, int]:
        options = self._audio[group]
        choices = [i for i in range(len(options)) if i != self._last.get(group)] or [0]
        i = random.choice(choices)
        self._last[group] = i
        return options[i]


def main() -> None:
    import config
    from tts import Voice

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="re-render every line")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    cfg = config.load(require_api_key=False, require_models=False)
    voice = Voice(cfg.piper_voice_path, cfg.piper_length_scale, cfg.piper_exe)
    n = render_all(voice, cfg.cache_dir, force=args.force)
    print(f"Rendered {n} line(s) into {cfg.cache_dir}")


if __name__ == "__main__":
    main()
