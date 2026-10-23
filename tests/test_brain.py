"""Brain request shape and error mapping, using a fake HTTP transport (no network)."""
import json

import httpx2
import pytest

from brain import (Brain, BrainConfigError, BrainOffline, BrainOverloaded, BrainRefused,
                   BrainTimeout)


def ok_body(text="Sup. I'm a pumpkin.", stop_reason="end_turn"):
    content = [{"type": "text", "text": text}] if text else []
    return {
        "id": "msg_test", "type": "message", "role": "assistant", "model": "claude-haiku-5-5",
        "content": content, "stop_reason": stop_reason, "stop_sequence": None,
        "usage": {"input_tokens": 10, "output_tokens": 5},
    }


def make_brain(handler):
    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    return Brain("test-key", "claude-haiku-5-5", "PERSONA", timeout_s=2.0, http_client=client)


def test_request_shape():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=ok_body())

    brain = make_brain(handler)
    history = [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]
    reply = brain.reply(history, "What does PNY make?", "STATUS", nudge="NUDGE")
    body = seen["body"]
    assert reply == "Sup. I'm a pumpkin."
    assert body["model"] == "claude-haiku-5-5"
    assert body["thinking"] == {"type": "disabled"}
    assert body["output_config"] == {"effort": "low"}
    assert "temperature" not in body
    assert body["system"][0] == {"type": "text", "text": "PERSONA", "cache_control": {"type": "ephemeral"}}
    assert [b["text"] for b in body["system"][1:]] == ["STATUS", "NUDGE"]
    assert body["messages"][-1] == {"role": "user", "content": "What does PNY make?"}
    assert len(body["messages"]) == 3
    assert history == [{"role": "user", "content": "hi"}, {"role": "assistant", "content": "yo"}]


def test_adaptive_thinking_option():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx2.Response(200, json=ok_body())

    client = httpx2.Client(transport=httpx2.MockTransport(handler))
    Brain("k", "claude-haiku-5-5", "P", thinking="adaptive", http_client=client).reply([], "q", "s")
    assert seen["body"]["thinking"] == {"type": "adaptive"}


@pytest.mark.parametrize("status,expected", [
    (429, BrainOverloaded),
    (529, BrainOverloaded),
    (500, BrainOverloaded),
    (401, BrainConfigError),
    (400, BrainConfigError),
])
def test_status_errors(status, expected):
    def handler(request):
        return httpx2.Response(status, json={"type": "error", "error": {"type": "x", "message": "nope"}},
                               headers={"retry-after": "0"})

    with pytest.raises(expected):
        make_brain(handler).reply([], "q", "s")


def test_connection_error():
    def handler(request):
        raise httpx2.ConnectError("no route", request=request)

    with pytest.raises(BrainOffline) as e:
        make_brain(handler).reply([], "q", "s")
    assert e.value.category == "err_offline"


def test_timeout():
    def handler(request):
        raise httpx2.ReadTimeout("slow", request=request)

    with pytest.raises(BrainTimeout) as e:
        make_brain(handler).reply([], "q", "s")
    assert e.value.category == "err_timeout"


def test_refusal_and_empty():
    with pytest.raises(BrainRefused):
        make_brain(lambda r: httpx2.Response(200, json=ok_body("", "refusal"))).reply([], "q", "s")
    with pytest.raises(BrainRefused):
        make_brain(lambda r: httpx2.Response(200, json=ok_body(""))).reply([], "q", "s")
