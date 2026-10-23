"""Claude call: persona + live status + this visitor's history -> Jack's reply text."""
from __future__ import annotations

import anthropic

MAX_TOKENS = 300  # replies are capped at 3 sentences by the prompt and guard.clean_output


class BrainError(Exception):
    """Base class. `category` names the FIXED_LINES group jack.py should play."""
    category = "err_offline"


class BrainOffline(BrainError):
    category = "err_offline"


class BrainTimeout(BrainError):
    category = "err_timeout"


class BrainOverloaded(BrainError):
    category = "err_overloaded"


class BrainRefused(BrainError):
    category = "err_blocked"


class BrainConfigError(BrainError):
    """Bad key, bad model name, or a malformed request. Needs a human, not a retry."""
    category = "err_offline"


class Brain:
    def __init__(self, api_key: str, model: str, system_prompt: str,
                 timeout_s: float = 8.0, thinking: str = "off", http_client=None):
        self.client = anthropic.Anthropic(api_key=api_key, timeout=timeout_s, max_retries=1,
                                          http_client=http_client)
        self.model = model
        self.system_prompt = system_prompt
        # "off" gives the steadiest latency for short spoken replies.
        # "adaptive" lets Haiku think when it wants (slower, sometimes smarter).
        if thinking == "adaptive":
            self.thinking = {"type": "adaptive"}
        else:
            self.thinking = {"type": "disabled"}

    def reply(self, history: list[dict], user_text: str, status: str, nudge: str | None = None) -> str:
        system = [
            {"type": "text", "text": self.system_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": status},
        ]
        if nudge:
            system.append({"type": "text", "text": nudge})
        messages = [*history, {"role": "user", "content": user_text}]
        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=MAX_TOKENS,
                thinking=self.thinking,
                output_config={"effort": "low"},
                system=system,
                messages=messages,
            )
        except anthropic.APITimeoutError as e:  # subclass of APIConnectionError: catch first
            raise BrainTimeout(str(e)) from e
        except anthropic.APIConnectionError as e:
            raise BrainOffline(str(e)) from e
        except anthropic.RateLimitError as e:
            raise BrainOverloaded(str(e)) from e
        except anthropic.APIStatusError as e:
            if e.status_code >= 500:
                raise BrainOverloaded(f"{e.status_code}: {e}") from e
            raise BrainConfigError(f"{e.status_code}: {e}") from e

        if resp.stop_reason == "refusal":
            raise BrainRefused("model declined")
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        if not text:
            raise BrainRefused(f"empty reply (stop_reason={resp.stop_reason})")
        return text
