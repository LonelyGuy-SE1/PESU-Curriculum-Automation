import importlib
import sys

import httpx
import pytest


def load_openrouter(monkeypatch):
    monkeypatch.setenv("OPENROUTER_URL", "https://openrouter.test")
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    monkeypatch.setenv("OPENROUTER_MODEL", "test-model")
    sys.modules.pop("app.services.openrouter", None)
    return importlib.import_module("app.services.openrouter")


def test_stream_token_reads_content_delta(monkeypatch):
    openrouter = load_openrouter(monkeypatch)
    line = 'data: {"choices":[{"delta":{"content":"hello"}}]}'

    assert openrouter._stream_token(line) == "hello"


def test_env_values_are_stripped(monkeypatch):
    monkeypatch.setenv("OPENROUTER_URL", "https://openrouter.test\n")
    monkeypatch.setenv("OPENROUTER_API_KEY", " test-key\n")
    monkeypatch.setenv("OPENROUTER_MODEL", " test-model\n")
    sys.modules.pop("app.services.openrouter", None)
    openrouter = importlib.import_module("app.services.openrouter")

    assert openrouter.URL == "https://openrouter.test"
    assert openrouter.KEY == "test-key"
    assert openrouter.MODEL == "test-model"


def test_stream_token_ignores_comments_and_done(monkeypatch):
    openrouter = load_openrouter(monkeypatch)

    assert openrouter._stream_token(": OPENROUTER PROCESSING") == ""
    assert openrouter._stream_token("data: [DONE]") == ""


def test_stream_chat_falls_back_to_normal_completion(monkeypatch):
    openrouter = load_openrouter(monkeypatch)
    request = httpx.Request("POST", "https://openrouter.test")

    class StreamResponse:
        def __enter__(self):
            return httpx.Response(400, text="stream unsupported", request=request)

        def __exit__(self, *_):
            return False

    class FakeClient:
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def stream(self, *_, **__):
            return StreamResponse()

        def post(self, *_, **__):
            return httpx.Response(200, json={"choices": [{"message": {"content": "fallback reply"}}]}, request=request)

    monkeypatch.setattr(openrouter, "Client", FakeClient)

    assert "".join(openrouter.stream_chat("system", [{"role": "user", "content": "hello"}])) == "fallback reply"


def test_rate_limit_error_includes_retry_after(monkeypatch):
    openrouter = load_openrouter(monkeypatch)
    request = httpx.Request("POST", "https://openrouter.test")

    class FakeClient:
        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, *_, **__):
            return httpx.Response(429, headers={"retry-after": "60"}, request=request)

    monkeypatch.setattr(openrouter, "Client", FakeClient)

    with pytest.raises(openrouter.OpenRouterError) as error:
        openrouter._chat_text([{"role": "user", "content": "hello"}])

    assert error.value.status_code == 429
    assert error.value.message == "Model provider is rate limited. Try again in 60 seconds."
