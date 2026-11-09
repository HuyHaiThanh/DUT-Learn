"""Deterministic LLM substitute for downstream tests."""

from collections.abc import Callable
from copy import deepcopy
from threading import Lock
from time import sleep

from app.rag.llm import ChatMessage, LLMError, LLMResult


class FakeLLMClient:
    def __init__(
        self,
        response: str | Callable[[list[ChatMessage]], str] = "Câu trả lời thử nghiệm.",
        *,
        delay_s: float = 0.0,
        error: LLMError | None = None,
    ) -> None:
        self.response = response
        self.delay_s = delay_s
        self.error = error
        self.messages: list[list[ChatMessage]] = []
        self._lock = Lock()

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        seed: int = 42,
        max_tokens: int = 512,
    ) -> LLMResult:
        snapshot = deepcopy(messages)
        with self._lock:
            self.messages.append(deepcopy(snapshot))
        sleep(self.delay_s)
        if self.error is not None:
            raise self.error
        text = self.response(snapshot) if callable(self.response) else self.response
        return LLMResult(text, "fake", 0, 0, 0.0, self.delay_s * 1000, self.delay_s * 1000, 0.0)
