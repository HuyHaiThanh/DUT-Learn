import json
import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

import httpx
import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.config import Settings
from app.rag.fake_llm import FakeLLMClient
from app.rag.llm import (
    ChatMessage,
    LLMBusy,
    LLMClient,
    LLMError,
    LLMTimeout,
    LLMUnavailable,
    OllamaClient,
    _cached_llm_client,
    get_llm_client,
    main,
    register_llm_errors,
)


def payload() -> dict[str, object]:
    return {
        "model": "test-model",
        "message": {"role": "assistant", "content": "private-answer"},
        "done": True,
        "prompt_eval_count": 11,
        "eval_count": 7,
        "load_duration": 1_500_000,
        "eval_duration": 2_250_000,
        "total_duration": 4_000_000,
    }


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, llm_model="test-model", llm_queue_wait_s=2)


@pytest.fixture
def messages() -> list[ChatMessage]:
    return [{"role": "user", "content": "private-prompt"}]


def test_success(settings: Settings, messages: list[ChatMessage], caplog: pytest.LogCaptureFixture):
    def handle(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert str(request.url) == "http://127.0.0.1:11434/api/chat"
        assert json.loads(request.content) == {
            "model": "test-model",
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.2, "seed": 9, "num_predict": 64, "num_ctx": 2048},
            "keep_alive": "5m",
        }
        assert request.extensions["timeout"] == dict.fromkeys(
            ("connect", "read", "write", "pool"), 90
        )
        return httpx.Response(200, json=payload())

    settings.llm_num_ctx = 2048
    settings.llm_keep_alive = "5m"
    client = OllamaClient(settings, transport=httpx.MockTransport(handle))
    with caplog.at_level(logging.INFO):
        result = client.generate(messages, temperature=0.2, seed=9, max_tokens=64)
    client.close()
    assert result.text == "private-answer"
    assert result.model == "test-model"
    assert (result.prompt_tokens, result.completion_tokens) == (11, 7)
    assert (result.load_ms, result.generate_ms, result.total_ms) == (1.5, 2.25, 4)
    assert result.queue_wait_ms >= 0
    assert "code=ok" in caplog.text
    assert "prompt_tokens=11" in caplog.text
    assert "private-prompt" not in caplog.text
    assert "private-answer" not in caplog.text


@pytest.mark.parametrize("kind", ["connect", "500", "404", "json", "shape", "timeout"])
def test_errors_and_slot_recovery(
    kind: str, settings: Settings, messages: list[ChatMessage], caplog: pytest.LogCaptureFixture
):
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls > 1:
            return httpx.Response(200, json=payload())
        if kind == "connect":
            raise httpx.ConnectError("private-prompt", request=request)
        if kind == "timeout":
            raise httpx.ReadTimeout("private-answer", request=request)
        if kind in {"500", "404"}:
            return httpx.Response(int(kind), json={"error": "private-answer"})
        if kind == "json":
            return httpx.Response(200, text="not json: private-answer")
        return httpx.Response(200, json={"message": "wrong"})

    client = OllamaClient(settings, transport=httpx.MockTransport(handle))
    expected = LLMTimeout if kind == "timeout" else LLMUnavailable
    with pytest.raises(expected) as raised:
        client.generate(messages)
    assert raised.value.status_code == (504 if kind == "timeout" else 503)
    assert raised.value.code in caplog.text
    assert "private-prompt" not in caplog.text
    assert "private-answer" not in caplog.text
    assert client.generate(messages).text == "private-answer"
    client.close()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("done", False),
        ("model", None),
        ("message", {"content": "x"}),
        ("eval_count", True),
        ("eval_count", -1),
        ("total_duration", "1"),
        ("load_duration", None),
        ("error", "failure"),
    ],
)
def test_malformed(field: str, value: object, settings: Settings, messages: list[ChatMessage]):
    data = payload()
    data[field] = value
    client = OllamaClient(
        settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data))
    )
    with pytest.raises(LLMUnavailable):
        client.generate(messages)
    client.close()


def test_missing_metrics_default_to_zero(settings: Settings, messages: list[ChatMessage]):
    data = payload()
    del data["prompt_eval_count"]
    del data["load_duration"]
    client = OllamaClient(
        settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=data))
    )
    result = client.generate(messages)
    assert result.prompt_tokens == 0
    assert result.load_ms == 0
    client.close()


def wait_for_queue(client: OllamaClient, size: int) -> None:
    with client._condition:
        assert client._condition.wait_for(lambda: len(client._waiting) == size, timeout=2)


def test_fifo_capacity(settings: Settings):
    entered = threading.Event()
    release = threading.Event()
    order: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        order.append(json.loads(request.content)["messages"][0]["content"])
        if len(order) == 1:
            entered.set()
            assert release.wait(3)
        return httpx.Response(200, json=payload())

    client = OllamaClient(settings, transport=httpx.MockTransport(handle))
    with ThreadPoolExecutor(max_workers=4) as pool:
        first = pool.submit(client.generate, [{"role": "user", "content": "0"}])
        try:
            assert entered.wait(2)
            waiting = []
            for number in range(1, 4):
                waiting.append(
                    pool.submit(client.generate, [{"role": "user", "content": str(number)}])
                )
                wait_for_queue(client, number)
            started = monotonic()
            with pytest.raises(LLMBusy):
                client.generate([])
            assert monotonic() - started < 0.2
            assert order == ["0"]
        finally:
            release.set()
        first.result(timeout=2)
        for future in waiting:
            assert future.result(timeout=2).queue_wait_ms > 0
    assert order == ["0", "1", "2", "3"]
    client.close()


def test_queue_expiry(settings: Settings):
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def handle(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            assert release.wait(3)
        return httpx.Response(200, json=payload())

    settings.llm_queue_wait_s = 0.03
    client = OllamaClient(settings, transport=httpx.MockTransport(handle))
    with ThreadPoolExecutor(max_workers=1) as pool:
        active = pool.submit(client.generate, [])
        try:
            assert entered.wait(2)
            with pytest.raises(LLMBusy):
                client.generate([])
            assert calls == 1
            wait_for_queue(client, 0)
        finally:
            release.set()
        active.result(timeout=2)
    assert client.generate([]).text == "private-answer"
    client.close()


def test_total_timeout_retains_slot(settings: Settings):
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def handle(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            assert release.wait(3)
        return httpx.Response(200, json=payload())

    settings.llm_timeout_s = 0.05
    settings.llm_queue_wait_s = 0.02
    client = OllamaClient(settings, transport=httpx.MockTransport(handle))
    try:
        with pytest.raises(LLMTimeout):
            client.generate([])
        assert entered.is_set()
        with pytest.raises(LLMBusy):
            client.generate([])
        assert calls == 1
    finally:
        release.set()
        with client._condition:
            assert client._condition.wait_for(lambda: not client._active, timeout=2)
    assert client.generate([]).text == "private-answer"
    client.close()


def test_failed_active_wakes_waiter(settings: Settings):
    entered = threading.Event()
    release = threading.Event()
    calls = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            entered.set()
            assert release.wait(3)
            raise httpx.ConnectError("offline", request=request)
        return httpx.Response(200, json=payload())

    client = OllamaClient(settings, transport=httpx.MockTransport(handle))
    with ThreadPoolExecutor(max_workers=2) as pool:
        active = pool.submit(client.generate, [])
        try:
            assert entered.wait(2)
            waiting = pool.submit(client.generate, [])
            wait_for_queue(client, 1)
        finally:
            release.set()
        with pytest.raises(LLMUnavailable):
            active.result(timeout=2)
        assert waiting.result(timeout=2).text == "private-answer"
    client.close()


@pytest.mark.parametrize("error", [LLMBusy(), LLMUnavailable(), LLMTimeout()])
@pytest.mark.parametrize("request_id", [None, "test-request"])
def test_handler(error: LLMError, request_id: str | None):
    app = FastAPI()
    register_llm_errors(app)

    @app.get("/fail")
    def fail(request: Request):
        if request_id:
            request.state.request_id = request_id
        raise error

    with TestClient(app) as client:
        response = client.get("/fail")
    assert response.status_code == error.status_code
    body = response.json()["error"]
    assert body == {
        "code": error.code,
        "message": error.message,
        "request_id": response.headers["X-Request-ID"],
    }
    assert body["request_id"]
    if request_id:
        assert body["request_id"] == request_id


def test_fake(messages: list[ChatMessage]):
    fake = FakeLLMClient(lambda received: received[0]["content"], delay_s=0.001)
    client: LLMClient = fake
    assert client.generate(messages).text == "private-prompt"
    messages[0]["content"] = "changed"
    assert fake.messages[0][0]["content"] == "private-prompt"
    assert FakeLLMClient("fixed").generate([]).text == "fixed"


@pytest.mark.parametrize("error", [LLMBusy(), LLMUnavailable(), LLMTimeout()])
def test_fake_errors(error: LLMError, messages: list[ChatMessage]):
    fake = FakeLLMClient(error=error)
    with pytest.raises(type(error)):
        fake.generate(messages)
    assert fake.messages == [messages]


def test_cached_dependency_override():
    _cached_llm_client.cache_clear()
    original = get_llm_client()
    try:
        assert get_llm_client() is original
        app = FastAPI()
        fake = FakeLLMClient("override")
        app.dependency_overrides[get_llm_client] = lambda: fake

        @app.get("/generate")
        def generate(client: LLMClient = Depends(get_llm_client)):
            return {"text": client.generate([]).text}

        with TestClient(app) as client:
            assert client.get("/generate").json() == {"text": "override"}
    finally:
        original.close()
        _cached_llm_client.cache_clear()


def test_concurrent_initialization(settings: Settings, monkeypatch: pytest.MonkeyPatch):
    _cached_llm_client.cache_clear()
    barrier = threading.Barrier(8)
    calls = 0
    original_class = OllamaClient

    def create():
        nonlocal calls
        calls += 1
        return original_class(
            settings, transport=httpx.MockTransport(lambda _: httpx.Response(200, json=payload()))
        )

    monkeypatch.setattr("app.rag.llm.OllamaClient", create)

    def get():
        barrier.wait(timeout=2)
        return get_llm_client()

    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            clients = list(pool.map(lambda _: get(), range(8)))
        assert calls == 1
        assert all(client is clients[0] for client in clients)
    finally:
        get_llm_client().close()
        _cached_llm_client.cache_clear()


def test_warm_and_ping(settings: Settings):
    paths: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        if request.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.1"})
        if request.url.path == "/api/tags":
            return httpx.Response(200, json={"models": [{"name": "test-model"}]})
        data = json.loads(request.content)
        assert data["options"]["num_predict"] == 1
        assert data["keep_alive"] == "30m"
        assert len(data["messages"]) == 1
        return httpx.Response(200, json=payload())

    client = OllamaClient(settings, transport=httpx.MockTransport(handle))
    client.ping()
    assert client.warm_up().load_ms == 1.5
    assert paths == ["/api/version", "/api/tags", "/api/chat"]
    client.close()


@pytest.mark.parametrize("tags", [{"models": []}, {}, {"models": None}])
def test_ping_missing_model(tags: object, settings: Settings):
    client = OllamaClient(
        settings,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json=({"version": "1"} if request.url.path == "/api/version" else tags)
            )
        ),
    )
    with pytest.raises(LLMUnavailable):
        client.ping()
    client.close()


@pytest.mark.parametrize("argument", ["--ping", "--warm"])
def test_cli(
    argument: str,
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    client = OllamaClient(
        settings,
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=(
                    {"version": "1"}
                    if request.url.path == "/api/version"
                    else {"models": [{"name": "test-model"}]}
                    if request.url.path == "/api/tags"
                    else payload()
                ),
            )
        ),
    )
    _cached_llm_client.cache_clear()
    monkeypatch.setattr("app.rag.llm.OllamaClient", lambda: client)
    monkeypatch.setattr("sys.argv", ["llm", argument])
    assert main() == 0
    output = capsys.readouterr().out
    assert ("Ollama OK" if argument == "--ping" else "load_ms=1.500 total_ms=4.000") in output
    assert client._http.is_closed
