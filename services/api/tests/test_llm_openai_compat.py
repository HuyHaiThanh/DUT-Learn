import json
from collections.abc import Callable

import httpx
import pytest

from app.config import Settings
from app.rag.llm import (
    ChatMessage,
    LLMBusy,
    LLMTimeout,
    LLMUnavailable,
    OllamaClient,
    OpenAICompatClient,
    build_llm_client,
)

BASE = "https://llm.example.test/openai/v1"


def settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "_env_file": None,
        "llm_provider": "openai",
        "llm_base_url": BASE,
        "llm_api_key": "sk-test",
        "llm_model": "demo-model",
        "llm_queue_wait_s": 2,
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def completion(content: str = "Trả lời [1]", **extra: object) -> dict[str, object]:
    body: dict[str, object] = {
        "model": "demo-model",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 30},
    }
    body.update(extra)
    return body


MESSAGES: list[ChatMessage] = [
    {"role": "system", "content": "sys"},
    {"role": "user", "content": "q"},
]


def client_for(
    handler: Callable[[httpx.Request], httpx.Response], **overrides: object
) -> OpenAICompatClient:
    return OpenAICompatClient(settings(**overrides), transport=httpx.MockTransport(handler))


def test_success_payload_and_parse() -> None:
    seen: dict[str, object] = {}

    def handle(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers.get("Authorization")
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=completion())

    result = client_for(handle).generate(MESSAGES, temperature=0.0, seed=42, max_tokens=64)
    assert seen["url"] == f"{BASE}/chat/completions"
    assert seen["auth"] == "Bearer sk-test"
    assert seen["body"] == {
        "model": "demo-model",
        "messages": MESSAGES,
        "stream": False,
        "temperature": 0.0,
        "seed": 42,
        "max_tokens": 64,
    }
    assert result.text == "Trả lời [1]"
    assert (result.model, result.prompt_tokens, result.completion_tokens) == ("demo-model", 120, 30)
    assert result.load_ms == 0.0


def test_reasoning_block_is_removed() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=completion("<think>\nnội bộ\n</think>\n\nĐáp án [2]"))

    assert client_for(handle).generate(MESSAGES).text == "Đáp án [2]"


def test_missing_usage_defaults_to_zero() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        body = completion()
        del body["usage"]
        return httpx.Response(200, json=body)

    result = client_for(handle).generate(MESSAGES)
    assert (result.prompt_tokens, result.completion_tokens) == (0, 0)


@pytest.mark.parametrize(
    ("status", "error"),
    [(429, LLMBusy), (401, LLMUnavailable), (500, LLMUnavailable), (503, LLMUnavailable)],
)
def test_http_errors(status: int, error: type[Exception]) -> None:
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(status, json={"error": {"message": "x"}})
        return httpx.Response(200, json=completion())

    client = client_for(handle)
    with pytest.raises(error):
        client.generate(MESSAGES)
    # The slot is released: the next request goes through.
    assert client.generate(MESSAGES).text == "Trả lời [1]"


def test_timeout_maps_to_llm_timeout() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(LLMTimeout):
        client_for(handle).generate(MESSAGES)


def test_connection_error_maps_to_unavailable() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    with pytest.raises(LLMUnavailable):
        client_for(handle).generate(MESSAGES)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"model": "demo-model", "choices": []},
        {"model": "", "choices": [{"message": {"role": "assistant", "content": "a"}}]},
        {"model": "demo-model", "choices": [{"message": {"role": "user", "content": "a"}}]},
        {"model": "demo-model", "choices": [{"message": {"role": "assistant", "content": None}}]},
        completion(usage={"prompt_tokens": -1, "completion_tokens": 0}),
        completion(usage={"prompt_tokens": "1", "completion_tokens": 0}),
    ],
)
def test_malformed_response(body: dict[str, object]) -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=body)

    with pytest.raises(LLMUnavailable):
        client_for(handle).generate(MESSAGES)


@pytest.mark.parametrize("key", [None, ""])
def test_api_key_required(key: str | None) -> None:
    with pytest.raises(ValueError):
        OpenAICompatClient(settings(llm_api_key=key))


def test_ping_checks_model_list() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == f"{BASE}/models"
        return httpx.Response(200, json={"data": [{"id": "other"}, {"id": "demo-model"}]})

    client_for(handle).ping()

    def missing(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"data": [{"id": "other"}]})

    with pytest.raises(LLMUnavailable):
        client_for(missing).ping()


def test_build_llm_client_selects_provider() -> None:
    assert type(build_llm_client(settings())) is OpenAICompatClient
    ollama = build_llm_client(Settings(_env_file=None))  # type: ignore[call-arg]
    assert type(ollama) is OllamaClient
    ollama.close()


def test_api_key_is_not_in_repr() -> None:
    assert "sk-test" not in repr(settings())
