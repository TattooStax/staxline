"""The model worker's client: a local llama.cpp server over
HTTP, stdlib only (zero-dependency law). Two disciplines are
baked into how it calls:

- Calls carry a hard token budget sized for a text-message
  draft, reasoning is asserted off in the payload (see
  _payload), and any think-block that still leaks into the
  output is stripped before the text can become a draft — a
  draft is customer-facing words, not a reasoning trace.
- Latency is measured on every call and returned with the
  text: per-turn latency on real hardware is the product's
  first risk, and unmeasured numbers are how it stays
  invisible.
"""
import json
import re
import time
import urllib.request

THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


class ModelError(Exception):
    pass


def strip_think(text):
    return THINK_RE.sub("", text).strip()


class LlamaCppClient:
    """OpenAI-shaped chat completions against a local
    llama-server. The server is a separate process by design
    (architecture: the model worker is isolated so a model
    crash can never take the phone line down with it)."""

    def __init__(self, base_url="http://127.0.0.1:8080",
                 timeout=600):
        self.base = base_url.rstrip("/")
        self.timeout = timeout

    @staticmethod
    def _payload(system, user, max_tokens, temperature):
        return {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
            # Reasoning off, by name: with reasoning on, the
            # model can spend its whole token budget in the
            # reasoning channel and return an empty reply, so
            # a drafting call asserts it off and the reply gets
            # the full budget. Templates that don't know the
            # kwarg ignore it; the think-strip is the second
            # wall.
            "chat_template_kwargs": {"enable_thinking": False},
        }

    def complete(self, system, user, max_tokens=400,
                 temperature=0.3):
        payload = self._payload(system, user, max_tokens,
                                temperature)
        req = urllib.request.Request(
            self.base + "/v1/chat/completions",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST")
        started = time.time()
        try:
            with urllib.request.urlopen(req,
                                        timeout=self.timeout) as r:
                data = json.loads(r.read().decode())
        except Exception as e:
            raise ModelError(f"model server call failed: {e}")
        latency = time.time() - started
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ModelError(f"unexpected model response: "
                             f"{str(data)[:200]}")
        usage = data.get("usage") or {}
        return {"text": strip_think(text), "latency_s": latency,
                "prompt_tokens": usage.get("prompt_tokens"),
                "completion_tokens": usage.get("completion_tokens")}


class FakeModelClient:
    """Scripted model for tests: returns the queued replies in
    order and records every (system, user) it was shown, so a
    test can assert on the exact pack the model saw."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def complete(self, system, user, max_tokens=400,
                 temperature=0.3):
        self.seen.append((system, user))
        if not self.replies:
            raise ModelError("fake model out of scripted replies")
        return {"text": self.replies.pop(0), "latency_s": 0.0,
                "prompt_tokens": None, "completion_tokens": None}
