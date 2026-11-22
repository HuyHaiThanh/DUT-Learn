"""Synchronous, process-shared Ollama access. No prompt or output is logged."""

import argparse
import logging
import math
import re
import threading
from collections import deque
from collections.abc import Iterator
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FutureTimeout
from contextlib import contextmanager
from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from typing import Any, Literal, Protocol, TypedDict
from uuid import uuid4

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import Settings, get_settings
from app.errors import error_response

logger = logging.getLogger(__name__)


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


@dataclass(frozen=True)
class LLMResult:
    text: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    load_ms: float
    generate_ms: float
    total_ms: float
    queue_wait_ms: float


class LLMClient(Protocol):
    def generate(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        seed: int = 42,
        max_tokens: int = 512,
    ) -> LLMResult: ...


class LLMError(Exception):
    status_code = 503
    code = "llm_unavailable"
    message = "Không kết nối được mô hình ngôn ngữ."

    def __init__(self) -> None:
        super().__init__(self.message)


class LLMUnavailable(LLMError):
    pass


class LLMTimeout(LLMError):
    status_code = 504
    code = "llm_timeout"
    message = "Mô hình phản hồi quá lâu."


class LLMBusy(LLMError):
    status_code = 429
    code = "llm_busy"
    message = "Trợ giảng đang bận, vui lòng thử lại sau ít phút."


def register_llm_errors(app: FastAPI) -> None:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        assert isinstance(exc, LLMError)
        if not getattr(request.state, "request_id", None):
            request.state.request_id = str(uuid4())
        return error_response(request, exc.status_code, exc.code, exc.message)

    app.add_exception_handler(LLMError, handler)


class OllamaClient:
    def __init__(
        self, settings: Settings | None = None, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        self.settings = settings if settings is not None else get_settings()
        if self.settings.llm_timeout_s <= 0:
            raise ValueError("llm_timeout_s must be positive")
        self._http = httpx.Client(
            base_url=self.settings.llm_base_url.rstrip("/") + "/",
            timeout=self.settings.llm_timeout_s,
            transport=transport,
        )
        self._condition = threading.Condition()
        self._active = False
        self._waiting: deque[object] = deque()
        self._inflight: Future[httpx.Response] | None = None

    def close(self) -> None:
        """Call after all users of this client have stopped."""
        self._http.close()

    @contextmanager
    def _slot(self) -> Iterator[float]:
        started = perf_counter()
        ticket = object()
        with self._condition:
            if self._active or self._waiting:
                if len(self._waiting) >= 3:
                    raise LLMBusy()
                self._waiting.append(ticket)
                self._condition.notify_all()
                try:
                    while True:
                        remaining = self.settings.llm_queue_wait_s - (perf_counter() - started)
                        if remaining <= 0:
                            raise LLMBusy()
                        if not self._active and self._waiting[0] is ticket:
                            self._waiting.popleft()
                            break
                        self._condition.wait(remaining)
                except BaseException:
                    self._waiting.remove(ticket)
                    self._condition.notify_all()
                    raise
            self._active = True
        try:
            yield (perf_counter() - started) * 1000
        finally:
            with self._condition:
                if self._inflight is not None and not self._inflight.done():
                    # A caller can time out while Ollama is still generating. Keep
                    # its slot until the HTTP operation ends to avoid overlap.
                    self._inflight.add_done_callback(lambda _: self._release_slot())
                else:
                    self._release_slot()

    def _release_slot(self) -> None:
        with self._condition:
            self._inflight = None
            self._active = False
            self._condition.notify_all()

    chat_path = "api/chat"

    def _payload(
        self, messages: list[ChatMessage], temperature: float, seed: int, max_tokens: int
    ) -> dict[str, Any]:
        return {
            "model": self.settings.llm_model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "seed": seed,
                "num_predict": max_tokens,
                "num_ctx": self.settings.llm_num_ctx,
            },
            "keep_alive": self.settings.llm_keep_alive,
        }

    def _chat_request(self, payload: dict[str, Any]) -> httpx.Response:
        """Bound caller wall time, including a server trickling response bytes.

        httpx timeouts bound individual I/O waits, not the whole response. A
        single worker retains the generation slot if that deadline expires.
        """
        future: Future[httpx.Response] = Future()
        self._inflight = future

        def send() -> None:
            try:
                response = self._request("POST", self.chat_path, json=payload)
            except BaseException as exc:
                future.set_exception(exc)
            else:
                future.set_result(response)

        threading.Thread(target=send, name="ollama-request", daemon=True).start()
        try:
            return future.result(timeout=self.settings.llm_timeout_s)
        except FutureTimeout:
            raise LLMTimeout() from None

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        started = perf_counter()
        try:
            response = self._http.request(method, path, **kwargs)
            if perf_counter() - started >= self.settings.llm_timeout_s:
                raise LLMTimeout()
            response.raise_for_status()
            return response
        except httpx.TimeoutException:
            raise LLMTimeout() from None
        except httpx.HTTPError:
            raise LLMUnavailable() from None

    def generate(
        self,
        messages: list[ChatMessage],
        *,
        temperature: float = 0.0,
        seed: int = 42,
        max_tokens: int = 512,
    ) -> LLMResult:
        started = perf_counter()
        queue_ms = 0.0
        try:
            with self._slot() as queue_ms:
                response = self._chat_request(
                    self._payload(messages, temperature, seed, max_tokens)
                )
                result = self._parse(response, queue_ms)
            logger.info(
                "llm model=%s prompt_tokens=%s completion_tokens=%s load_ms=%.3f "
                "generate_ms=%.3f total_ms=%.3f queue_wait_ms=%.3f code=ok",
                result.model,
                result.prompt_tokens,
                result.completion_tokens,
                result.load_ms,
                result.generate_ms,
                result.total_ms,
                result.queue_wait_ms,
            )
            return result
        except LLMError as exc:
            logger.warning(
                "llm model=%s elapsed_ms=%.3f queue_wait_ms=%.3f code=%s",
                self.settings.llm_model,
                (perf_counter() - started) * 1000,
                queue_ms or (perf_counter() - started) * 1000,
                exc.code,
            )
            raise

    @staticmethod
    def _parse(response: httpx.Response, queue_ms: float) -> LLMResult:
        try:
            data = response.json()
            if (
                not isinstance(data, dict)
                or data.get("done") is not True
                or not isinstance(data.get("model"), str)
                or not data["model"]
                or not isinstance(data.get("message"), dict)
                or data["message"].get("role") != "assistant"
                or not isinstance(data["message"].get("content"), str)
                or "error" in data
            ):
                raise ValueError
            for key in (
                "prompt_eval_count",
                "eval_count",
                "load_duration",
                "eval_duration",
                "total_duration",
            ):
                # Metrics may be omitted by some Ollama versions (e.g. cached prompts):
                # missing means 0, but a present value must be a non-negative int.
                value = data.setdefault(key, 0)
                if type(value) is not int or value < 0 or not math.isfinite(value):
                    raise ValueError
            return LLMResult(
                text=data["message"]["content"],
                model=data["model"],
                prompt_tokens=data["prompt_eval_count"],
                completion_tokens=data["eval_count"],
                load_ms=data["load_duration"] / 1_000_000,
                generate_ms=data["eval_duration"] / 1_000_000,
                total_ms=data["total_duration"] / 1_000_000,
                queue_wait_ms=queue_ms,
            )
        except (ValueError, KeyError, TypeError, OverflowError):
            raise LLMUnavailable() from None

    def warm_up(self) -> LLMResult:
        return self.generate([{"role": "user", "content": "Hi"}], max_tokens=1)

    def ping(self) -> None:
        try:
            version = self._request("GET", "api/version").json()
            tags = self._request("GET", "api/tags").json()
            if not isinstance(version["version"], str) or not version["version"]:
                raise ValueError
            if not any(item["name"] == self.settings.llm_model for item in tags["models"]):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            raise LLMUnavailable() from None


_THINK_BLOCK = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


class OpenAICompatClient(OllamaClient):
    """OpenAI-compatible chat API (e.g. Groq), for the hosted demo only.

    Reuses the single-slot queue and wall-clock timeout of OllamaClient. Experiments
    keep using Ollama; this client exists so the demo can run without a GPU.
    """

    chat_path = "chat/completions"

    def __init__(
        self, settings: Settings | None = None, *, transport: httpx.BaseTransport | None = None
    ) -> None:
        super().__init__(settings, transport=transport)
        key = self.settings.llm_api_key
        if key is None or not key.get_secret_value():
            raise ValueError("llm_api_key is required for the openai provider")
        self._http.headers["Authorization"] = f"Bearer {key.get_secret_value()}"

    def _payload(
        self, messages: list[ChatMessage], temperature: float, seed: int, max_tokens: int
    ) -> dict[str, Any]:
        return {
            "model": self.settings.llm_model,
            "messages": messages,
            "stream": False,
            "temperature": temperature,
            "seed": seed,
            "max_tokens": max_tokens,
        }

    def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        started = perf_counter()
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.TimeoutException:
            raise LLMTimeout() from None
        except httpx.HTTPError:
            raise LLMUnavailable() from None
        if perf_counter() - started >= self.settings.llm_timeout_s:
            raise LLMTimeout()
        if response.status_code == 429:  # provider rate limit (free tiers)
            raise LLMBusy()
        if not response.is_success:
            raise LLMUnavailable()
        return response

    @staticmethod
    def _parse(response: httpx.Response, queue_ms: float) -> LLMResult:
        try:
            data = response.json()
            choice = data["choices"][0]
            message = choice["message"]
            if (
                not isinstance(data.get("model"), str)
                or not data["model"]
                or message.get("role") != "assistant"
                or not isinstance(message.get("content"), str)
            ):
                raise ValueError
            usage = data.get("usage") or {}
            prompt_tokens = usage.get("prompt_tokens", 0)
            completion_tokens = usage.get("completion_tokens", 0)
            for value in (prompt_tokens, completion_tokens):
                if type(value) is not int or value < 0:
                    raise ValueError
            # Reasoning models may prepend a hidden-thought block; never show it.
            text = _THINK_BLOCK.sub("", message["content"]).strip()
            try:
                elapsed_ms = response.elapsed.total_seconds() * 1000
            except RuntimeError:  # response not closed (test transports)
                elapsed_ms = 0.0
            return LLMResult(
                text=text,
                model=data["model"],
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                load_ms=0.0,
                generate_ms=elapsed_ms,
                total_ms=elapsed_ms,
                queue_wait_ms=queue_ms,
            )
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            raise LLMUnavailable() from None

    def ping(self) -> None:
        try:
            models = self._request("GET", "models").json()
            if not any(item["id"] == self.settings.llm_model for item in models["data"]):
                raise ValueError
        except (ValueError, KeyError, TypeError):
            raise LLMUnavailable() from None


def build_llm_client(settings: Settings | None = None) -> OllamaClient:
    provider = (settings if settings is not None else get_settings()).llm_provider
    if provider == "openai":
        return OpenAICompatClient(settings)
    return OllamaClient(settings) if settings is not None else OllamaClient()


@lru_cache(maxsize=1)
def _cached_llm_client() -> OllamaClient:
    return build_llm_client()


_client_lock = threading.Lock()


def get_llm_client() -> OllamaClient:
    # lru_cache alone can construct multiple instances on concurrent first use.
    with _client_lock:
        return _cached_llm_client()


def main() -> int:
    parser = argparse.ArgumentParser(description="Check or warm the configured Ollama model")
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--ping", action="store_true")
    action.add_argument("--warm", action="store_true")
    args = parser.parse_args()
    client = get_llm_client()
    try:
        if args.ping:
            client.ping()
            print(f"Ollama OK; model={client.settings.llm_model}")
        else:
            result = client.warm_up()
            print(f"load_ms={result.load_ms:.3f} total_ms={result.total_ms:.3f}")
        return 0
    except LLMError as exc:
        print(f"{exc.code}: {exc.message}")
        return 1
    finally:
        client.close()
        _cached_llm_client.cache_clear()


if __name__ == "__main__":
    raise SystemExit(main())
