# Jack O'Intern: Runbook

All commands run in PowerShell from the `jack-o-intern` folder. `py` means `.\.venv\Scripts\python.exe`.

## 0. Before you start (approvals)
| # | Task | Done |
|---|---|---|
| 0.1 | IT: allow `api.anthropic.com:443` on corporate Wi-Fi. For setup only: `pypi.org`, `files.pythonhosted.org`, `huggingface.co`, `github.com` | ☐ |
| 0.2 | IT: local install rights on the laptop | ☐ |
| 0.3 | HR: electronics next to the pumpkin are OK, and there's an outlet at the display spot | ☐ |
| 0.4 | Claude Console: new API key named `jack-o-intern`, monthly spend cap about $20 | ☐ |
| 0.5 | Jabra speakerphone and its USB cable reserved for Oct 26–30 | ☐ |
| 0.6 | Create 36" Long by 24" wide cubicle. | ☐ |

## 1. Laptop setup (once)
| # | Step | Expected result |
|---|---|---|
| 1.1 | Install Python 3.11 x64 from python.org with "Add to PATH" checked | `py -3.11 --version` prints 3.11.x |
| 1.2 | `git clone https://github.com/nayhaq/jackolatern.git`, then `cd jackolatern` | — |
| 1.3 | `powershell -ExecutionPolicy Bypass -File .\setup.ps1` | Ends with `SETUP OK` |
| 1.4 | Open `.env`, paste `ANTHROPIC_API_KEY`, and set `HF_HUB_OFFLINE=1` | — |
| 1.5 | Plug in the Jabra by USB. Run `py tools\list_devices.py` | Both `MIC_DEVICE` and `SPEAKER_DEVICE` lines show the Jabra |
| 1.6 | `py tools\mic_test.py`, then talk | Meter moves and `SPEECH` lights up when you talk |
| 1.7 | **Firewall gate** on corporate Wi-Fi: `py jack.py --text`, type `what does PNY make` | Jack answers in character. If you get an `err_offline` line, escalate the IT ticket |
| 1.8 | Windows settings: power plan never sleeps on AC; lid close does nothing on AC; pause Windows Update for 1 week; Focus Assist on; Settings > Privacy > Microphone allows desktop apps; Jabra set as default playback and recording; Teams, Zoom, and Jabra Direct closed and removed from startup apps | Screenshot saved |

## 2. "Hey Jack" wake model (once, about 1 hour)
1. Open the openWakeWord **automatic model training** Colab notebook, linked from the openWakeWord GitHub README.
2. Set the target phrase to `hey jack`. Keep the default sample counts and steps. Run all cells on a free GPU runtime.
3. Download the `.onnx` file. Rename it to `hey_jack.onnx` and put it in `models\`.
4. `py tools\wake_test.py`. Say "Hey Jack" 20 times from 1–2 m. **Pass:** at least 18 wakes.
5. Play 10 minutes of a talk podcast near the laptop without saying the wake word. **Pass:** 1 or fewer wakes.
6. If it fails, retrain once with more samples. If it still fails, use Porcupine (see `models\README.md`).

## 3. Pick the voice
1. `py tools\voice_audition.py`. Try `--length-scale 1.2` for extra deadpan.
2. Set `PIPER_VOICE_PATH` and `PIPER_LENGTH_SCALE` in `.env`.
3. `py prerender.py --force`. Every fixed line is re-recorded in the new voice.

## 4. Check the brain and the speed
| # | Step | Pass |
|---|---|---|
| 4.1 | `py -m pytest tests\test_persona.py -v` (live API, under $0.05) | All green. Then read `logs\persona_review.md` for tone and made-up facts |
| 4.2 | `py tools\bench.py` | `TOTAL` median ≤ 4000 ms |
| 4.3 | Set `LOG_TRANSCRIPTS=true`, run `.\start.ps1`, and have 20 real conversations | In character, ≤3 sentences, no made-up facts. Read `logs\turns-*.jsonl` |
| 4.4 | "Hey Jack, what does PNY make?" then, without the wake word, "Which one's the best?" | The second answer builds on the first |
| 4.5 | Wait 25 s, then "Hey Jack, what did I just ask?" | Jack doesn't know |

## 5. Soak test (Oct 27)
| # | Step | Pass |
|---|---|---|
| 5.1 | `.\start.ps1` for 4+ hours with a radio or podcast playing nearby | No hang. 3 or fewer false wakes per hour (count `Wake` lines in `logs\jack.log`) |
| 5.2 | Kill `python.exe` in Task Manager | Back within 10 s, with an `err_restart` line. Listed in `logs\restarts.log` |
| 5.3 | Wi-Fi off for 2 min, then ask a question | An `err_offline` line plays. Normal answers once Wi-Fi returns |
| 5.4 | Unplug the Jabra USB for 10 s, then plug it back in | `Audio device back` in the log, or a restart with an `err_restart` line |
| 5.5 | Mumble, then talk nonstop for 10+ s | `err_didnt_catch`, then `err_too_long` |

## 6. Verify the PNY facts (by Oct 28)
Open `persona.py`. For each of the 10 topic cards, check every fact against pny.com or a PNY press release.
- Confirmed: set `"verified": True`.
- Can't confirm: **delete that fact**. Don't reword it.
- Then `py -m pytest -q -m "not live"`.

`logs\jack.log` lists any card still unverified at startup.

## 7. On-site test, Memory Cafe (Oct 29)
| Check | Pass |
|---|---|
| Step 1.7 on the cafe Wi-Fi | Jack answers |
| `py tools\wake_test.py`: 20 "Hey Jack"s in real noise | At least 18 wakes |
| 15 minutes of cafe noise, no wake word | 1 or fewer false wakes |
| Volume at 2 m | Clear, no distortion |
| Outlet and cable path | Hidden, no trip hazard |

Write the final `WAKE_THRESHOLD`, `VAD_AGGRESSIVENESS`, and `FOLLOWUP_WINDOW_S` values here: ______________________

## 8. Event day (Oct 30)
| Time | Action |
|---|---|
| 9:30 | Boot the laptop, join Wi-Fi, run step 1.7 |
| 10:00 | Set up at the display spot. Jabra by USB, buttons taped, charger plugged in |
| 10:30 | Set `LOG_TRANSCRIPTS=false`. Run `.\start.ps1`. Do 3 live exchanges. Close the lid |
| 11:00 | Hand off to HR |
| 12:00–3:00 | Hourly: one live "Hey Jack". Glance at `logs\jack.log` if you have the laptop open |
| 3:00+ | Ctrl+C. Delete `logs\` after the contest |

## Troubleshooting (one step at a time)
| Symptom | Check first | Fix |
|---|---|---|
| `CONFIG PROBLEM` on start | Read the message | Fix `.env` or put the missing model file in `models\` |
| Every answer is an `err_offline` line | `py jack.py --text` on the same Wi-Fi | API blocked or key wrong. Check `logs\jack.log` for `Claude rejected the request` (key or model) versus connection errors (firewall) |
| Jack never wakes | `py tools\wake_test.py`: do scores move at all? | No scores means the wrong mic: rerun `list_devices.py`. Low scores: lower `WAKE_THRESHOLD` by 0.1 |
| Wakes on random chatter | Count the `Wake` lines | Raise `WAKE_THRESHOLD` by 0.1 |
| Answers people who didn't say "Hey Jack" | That's the follow-up window | Lower `FOLLOWUP_WINDOW_S` (try 5) or raise `VAD_AGGRESSIVENESS` to 3 |
| Cuts people off mid-question | — | Raise `SILENCE_END_MS` to 1000 |
| No sound | Windows volume mixer, Jabra mute light | Unmute. If it's still silent, set `SPEAKER_DEVICE=` (blank) to use the default output |
| Mispronounces a word | — | Add a rule to `_SAY_RULES` in `guard.py`, then `py prerender.py --force` |
| Slow answers (> 5 s) | `py tools\bench.py`: which stage is slow? | STT: keep `base.en`. Claude: check the Wi-Fi |
