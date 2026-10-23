"""Jack O'Intern main loop.

    python jack.py            # normal run (start.ps1 wraps this with auto-restart)
    python jack.py --text     # type questions instead of speaking (no mic, wake word, or STT)

Exit codes: 0 = stopped on purpose (Ctrl+C), 1 = crashed (start.ps1 restarts it),
2 = configuration problem (start.ps1 stops so a human can fix it).
"""
from __future__ import annotations

import argparse
import collections
import ctypes
import json
import logging
import os
import sys
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler

import config  # first: loads .env (HF_HUB_OFFLINE must be set before faster-whisper imports)
import guard
import persona
from brain import Brain, BrainConfigError, BrainError
from mood import Mood
from session import Session

log = logging.getLogger("jack")

REPEAT_MEMORY = 30
DEAF_AFTER_SPEAKING_S = 0.5
MAX_MISSES_PER_VISIT = 2
AUDIO_REOPEN_ATTEMPTS = 12      # x 5 s = 1 minute of trying before exiting for a restart


def setup_logging(cfg: config.Config) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    handler = RotatingFileHandler(cfg.log_dir / "jack.log", maxBytes=5_000_000, backupCount=3,
                                  encoding="utf-8")
    handler.setFormatter(fmt)
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(fmt)
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers = [handler, console]


def keep_awake() -> None:
    """Stop Windows from sleeping or blanking the display while Jack runs."""
    if os.name != "nt":
        return
    es_continuous, es_system, es_display = 0x80000000, 0x00000001, 0x00000002
    ctypes.windll.kernel32.SetThreadExecutionState(es_continuous | es_system | es_display)


class TurnLog:
    """One JSON line per turn in logs/turns-YYYYMMDD.jsonl. Transcripts only if LOG_TRANSCRIPTS=true."""

    def __init__(self, cfg: config.Config):
        self.cfg = cfg

    def write(self, **fields) -> None:
        if not self.cfg.log_transcripts:
            fields.pop("heard", None)
            fields.pop("reply", None)
        fields["ts"] = datetime.now().isoformat(timespec="seconds")
        path = self.cfg.log_dir / f"turns-{datetime.now():%Y%m%d}.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(fields) + "\n")


class Jack:
    def __init__(self, cfg: config.Config, text_mode: bool = False):
        self.cfg = cfg
        self.text_mode = text_mode
        self.brain = Brain(cfg.api_key, cfg.model, persona.build_system_prompt(),
                           cfg.llm_timeout_s, cfg.llm_thinking)
        self.mood = Mood(cfg.voting_start, cfg.voting_end, max_turns=cfg.max_turns)
        self.session = Session(cfg.max_turns)
        self.recent: collections.deque[str] = collections.deque(maxlen=REPEAT_MEMORY)
        self.turns = TurnLog(cfg)

        if text_mode:
            return
        # Audio stack is imported here so --text works on machines without audio libs set up.
        import audio
        import prerender
        from stt import Transcriber
        from tts import Voice
        from wake import make_detector

        self.audio = audio
        log.info("Loading voice...")
        self.voice = Voice(cfg.piper_voice_path, cfg.piper_length_scale, cfg.piper_exe)
        n = prerender.render_all(self.voice, cfg.cache_dir)
        if n:
            log.info("Pre-rendered %d fixed line(s)", n)
        self.lines = prerender.FixedLines(cfg.cache_dir)
        log.info("Loading speech-to-text (%s)...", cfg.whisper_model)
        self.stt = Transcriber(cfg.whisper_model, cfg.whisper_dir, cfg.offline_models)
        log.info("Loading wake word (%s)...", cfg.wake_engine)
        self.wake = make_detector(cfg)
        self.vad = audio.Vad(cfg.vad_aggressiveness)
        self.mic_index = audio.find_device(cfg.mic_device, "input")
        self.speaker_index = audio.find_device(cfg.speaker_device, "output")
        log.info("Mic: %s", audio.device_label(self.mic_index, "input"))
        log.info("Speaker: %s", audio.device_label(self.speaker_index, "output"))
        self.player = audio.Player(self.speaker_index)
        self.mic = audio.MicStream(self.mic_index).start()

    # ---------- shared brain step ----------

    def think(self, heard: str) -> tuple[str | None, str]:
        """Returns (reply, status). reply is None when a fixed error line should play instead;
        status then names the FIXED_LINES group."""
        self.mood.on_turn()
        status = self.mood.snapshot()
        try:
            raw = self.brain.reply(self.session.history, heard, status)
            reply = guard.clean_output(raw)
            if reply is None:
                return None, "err_blocked"
            prev = guard.is_repeat(reply, self.recent)
            if prev:
                log.info("Reply too close to an earlier one; asking for a new angle")
                nudge = (f"You already said something very close to this today: <earlier>{prev}</earlier> "
                         "Say something different, with a new angle.")
                retry = guard.clean_output(self.brain.reply(self.session.history, heard, status, nudge))
                if retry:
                    reply = retry
        except BrainConfigError:
            log.exception("Claude rejected the request: check ANTHROPIC_API_KEY and MODEL")
            return None, "err_offline"
        except BrainError as e:
            log.warning("Brain error (%s): %s", e.category, e)
            return None, e.category
        self.session.add_turn(heard, reply)
        self.mood.on_reply(reply)
        self.recent.append(reply)
        return reply, "ok"

    # ---------- voice mode ----------

    def say_line(self, group: str) -> None:
        _text, audio_data, sr = self.lines.pick(group)
        self.player.play(audio_data, sr)

    def listen_again(self) -> None:
        """Throw away what the mic heard while Jack was talking, so he can't wake himself."""
        time.sleep(DEAF_AFTER_SPEAKING_S)
        self.mic.drain()

    def visit(self) -> None:
        self.mood.on_visitor()
        self.session.reset()
        self.say_line("chirp")
        self.listen_again()
        start_timeout = self.cfg.first_listen_s
        misses = 0
        while not self.session.full():
            utt = self.audio.record_utterance(
                self.mic, self.vad, start_timeout, self.cfg.silence_end_ms, self.cfg.max_record_s)
            if utt is None:
                break  # they walked away
            start_timeout = self.cfg.followup_window_s
            if utt.hit_max:
                self.say_line("err_too_long")
                self.listen_again()
                continue

            t_start = time.monotonic()
            _t, filler, filler_sr = self.lines.pick("filler")
            self.player.play_async(filler, filler_sr)
            heard = guard.clean_input(self.stt.transcribe(utt.audio))
            t_stt = time.monotonic()
            if not heard:
                self.player.wait()
                misses += 1
                self.say_line("err_didnt_catch")
                self.turns.write(visitor=self.mood.visitor, status="empty", rec_ms=utt.record_ms,
                                 stt_ms=int((t_stt - t_start) * 1000))
                if misses >= MAX_MISSES_PER_VISIT:
                    break
                self.listen_again()
                continue

            reply, status = self.think(heard)
            t_llm = time.monotonic()
            if reply is None:
                self.player.wait()
                self.say_line(status)
                self.turns.write(visitor=self.mood.visitor, turn=self.mood.turn, status=status,
                                 rec_ms=utt.record_ms, stt_ms=int((t_stt - t_start) * 1000),
                                 llm_ms=int((t_llm - t_stt) * 1000), heard=heard)
                break
            speech, sr = self.voice.synth(guard.say_friendly(reply))
            t_tts = time.monotonic()
            self.player.wait()  # let the filler finish
            t_first_word = time.monotonic()
            self.player.play(speech, sr)
            self.turns.write(
                visitor=self.mood.visitor, turn=self.mood.turn, status="ok",
                wake_score=round(getattr(self.wake, "last_score", 0.0), 3),
                rec_ms=utt.record_ms,
                stt_ms=int((t_stt - t_start) * 1000),
                llm_ms=int((t_llm - t_stt) * 1000),
                tts_ms=int((t_tts - t_llm) * 1000),
                total_ms=int((t_first_word - t_start) * 1000) + self.cfg.silence_end_ms,
                heard=heard, reply=reply,
            )
            self.listen_again()
        self.session.reset()

    def reopen_mic(self) -> None:
        self.mic.close()
        for attempt in range(1, AUDIO_REOPEN_ATTEMPTS + 1):
            time.sleep(5)
            try:
                self.mic_index = self.audio.find_device(self.cfg.mic_device, "input")
                self.speaker_index = self.audio.find_device(self.cfg.speaker_device, "output")
                self.player = self.audio.Player(self.speaker_index)
                self.mic = self.audio.MicStream(self.mic_index).start()
                self.mic.read(timeout=3.0)
                log.info("Audio device back (attempt %d)", attempt)
                return
            except Exception as e:  # noqa: BLE001
                log.warning("Audio reopen attempt %d failed: %s", attempt, e)
                self.mic.close()
        raise RuntimeError("Audio device did not come back; exiting so start.ps1 restarts Jack")

    def run(self) -> None:
        if os.environ.get("JACK_RESTART") == "1":
            self.say_line("err_restart")
            self.listen_again()
        log.info("Ready. Say 'Hey Jack'.")
        while True:
            try:
                block = self.mic.read()
                if not self.wake.process(block):
                    continue
                log.info("Wake (score %.2f)", self.wake.last_score)
                self.visit()
                self.wake.reset()
                self.mic.drain()
            except self.audio.AudioDeviceError as e:
                log.warning("Audio problem: %s. Reopening...", e)
                self.reopen_mic()
                self.wake.reset()

    # ---------- text mode ----------

    def run_text(self) -> None:
        print("Text mode. Type a question; blank line starts a new visitor; Ctrl+C quits.")
        self.mood.on_visitor()
        while True:
            try:
                heard = guard.clean_input(input("you> "))
            except EOFError:
                return
            if not heard:
                self.session.reset()
                self.mood.on_visitor()
                print("(new visitor)")
                continue
            reply, status = self.think(heard)
            print(f"jack> {reply}" if reply else f"jack> [{status}: {persona.FIXED_LINES[status][0]}]")
            if self.session.full():
                self.session.reset()
                self.mood.on_visitor()
                print("(turn limit hit: new visitor)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Jack O'Intern")
    parser.add_argument("--text", action="store_true", help="type instead of talk")
    args = parser.parse_args()
    try:
        cfg = config.load(require_models=not args.text)
    except config.ConfigError as e:
        print(f"CONFIG PROBLEM:\n{e}", file=sys.stderr)
        return 2
    setup_logging(cfg)
    unverified = persona.unverified_topics()
    if unverified:
        log.warning("%d topic card(s) not yet verified against pny.com: %s",
                    len(unverified), "; ".join(unverified))
    keep_awake()
    try:
        jack = Jack(cfg, text_mode=args.text)
        jack.run_text() if args.text else jack.run()
    except KeyboardInterrupt:
        log.info("Stopped by user")
        return 0
    except Exception:  # noqa: BLE001
        log.exception("Crashed")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
