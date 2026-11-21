"""Model backends. Each has chat(messages, seed=None) -> str.

MockBackend is a scripted stand-in for tests. It never calls a network.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from .defenses import MONITOR_MARKER

MOCK_MODELS = ("obedient", "careful", "gullible")


class Backend:
    name = "base"

    def prepare(self, scenario: Any) -> None:  # only the mock needs this
        pass

    def chat(self, messages: List[Dict[str, str]], seed: Optional[int] = None) -> str:
        raise NotImplementedError


class MockBackend(Backend):
    """Scripted behaviours, for tests and for checking the plumbing.

    obedient: does the benign plan, then follows any injection it has seen.
    careful:  does the benign plan and ignores injections.
    gullible: like obedient, but ignores text wrapped as untrusted data.
    As a monitor: careful vetoes send_email/delete_file unless the task asked
    for them; the others approve everything.
    """

    name = "mock"

    def __init__(self, model: str = "careful"):
        if model not in MOCK_MODELS:
            raise ValueError("mock model must be one of %s" % (MOCK_MODELS,))
        self.model = model
        self.scenario = None

    def prepare(self, scenario: Any) -> None:
        self.scenario = scenario

    # -- monitor role ------------------------------------------------------
    def _monitor_reply(self, text: str) -> str:
        if self.model != "careful":
            return "YES"
        task = text.split('"', 2)[1].lower() if '"' in text else ""
        line = [ln for ln in text.splitlines() if ln.startswith('{"tool"')]
        call = json.loads(line[0]) if line else {}
        tool = call.get("tool")
        if tool == "send_email" and not ("email" in task or "send" in task):
            return "NO"
        if tool == "delete_file" and not ("delete" in task or "remove" in task):
            return "NO"
        return "YES"

    # -- agent role --------------------------------------------------------
    def _susceptible(self, seen: str) -> bool:
        inj = self.scenario.injection
        if inj is None or self.model == "careful" or inj.text not in seen:
            return False
        if self.model == "gullible" and "<untrusted_data" in seen:
            return False
        return True

    def _attack_calls(self) -> List[Dict[str, Any]]:
        inj, sc = self.scenario.injection, self.scenario
        if inj.goal == "exfiltrate":
            return [{"tool": "send_email",
                     "args": {"to": inj.recipient, "subject": "data", "body": sc.canary}}]
        if inj.goal == "delete":
            return [{"tool": "delete_file", "args": {"path": inj.path}}]
        return []

    def chat(self, messages: List[Dict[str, str]], seed: Optional[int] = None) -> str:
        last = messages[-1]["content"]
        if last.startswith(MONITOR_MARKER):
            return self._monitor_reply(last)
        sc = self.scenario
        seen = "\n".join(m["content"] for m in messages if m["role"] == "user")
        step = sum(1 for m in messages if m["role"] == "assistant")
        plan = list(sc.mock_plan)
        bad = self._susceptible(seen)
        if bad:
            plan += self._attack_calls()
        if step < len(plan):
            return json.dumps(plan[step])
        if bad and sc.injection.goal == "ignore":
            return json.dumps({"final": sc.hijack_marker})
        return json.dumps({"final": "Answer: " + sc.expected_answer})


class OllamaBackend(Backend):
    name = "ollama"

    def __init__(self, model: str, base_url: str = "http://127.0.0.1:11434",
                 temperature: float = 0.7, timeout: int = 300):
        self.model, self.base_url = model, base_url.rstrip("/")
        self.temperature, self.timeout = temperature, timeout

    def chat(self, messages: List[Dict[str, str]], seed: Optional[int] = None) -> str:
        import requests
        options: Dict[str, Any] = {"temperature": self.temperature}
        if seed is not None:
            options["seed"] = seed
        resp = requests.post(
            self.base_url + "/api/chat",
            json={"model": self.model, "messages": messages, "stream": False, "options": options},
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["message"]["content"]


class AnthropicBackend(Backend):
    name = "anthropic"

    def __init__(self, model: str, temperature: float = 0.7, max_tokens: int = 1024):
        try:
            import anthropic  # imported lazily so the package stays optional
        except ImportError as exc:
            raise RuntimeError("pip install anthropic to use the anthropic backend") from exc
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        self.client = anthropic.Anthropic(api_key=key)
        self.model, self.temperature, self.max_tokens = model, temperature, max_tokens

    def chat(self, messages: List[Dict[str, str]], seed: Optional[int] = None) -> str:
        system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
        turns = [m for m in messages if m["role"] != "system"]
        kwargs: Dict[str, Any] = dict(model=self.model, max_tokens=self.max_tokens, messages=turns)
        if self.temperature is not None:
            kwargs["temperature"] = self.temperature
        if system:
            kwargs["system"] = system
        try:
            resp = self.client.messages.create(**kwargs)
        except Exception as exc:
            # Newer models reject the temperature setting; drop it once and keep their default sampling.
            if "temperature" not in kwargs or "temperature" not in str(exc):
                raise
            self.temperature = None
            del kwargs["temperature"]
            resp = self.client.messages.create(**kwargs)
        return "".join(getattr(b, "text", "") for b in resp.content)


def make_backend(kind: str, model: str, ollama_url: str = "http://127.0.0.1:11434",
                 temperature: float = 0.7) -> Backend:
    if kind == "mock":
        return MockBackend(model)
    if kind == "ollama":
        return OllamaBackend(model, base_url=ollama_url, temperature=temperature)
    if kind == "anthropic":
        return AnthropicBackend(model, temperature=temperature)
    raise ValueError("unknown backend: " + kind)
