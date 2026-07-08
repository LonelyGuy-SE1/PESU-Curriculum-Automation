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


def test_stream_chat_runs_tool_calls(monkeypatch):
    openrouter = load_openrouter(monkeypatch)
    request = httpx.Request("POST", "https://openrouter.test")
    calls = []

    class FakeClient:
        count = 0

        def __init__(self, *_, **__):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def post(self, *_, json=None, **__):
            FakeClient.count += 1
            if FakeClient.count == 1:
                return httpx.Response(
                    200,
                    json={
                        "choices": [
                            {
                                "message": {
                                    "content": "",
                                    "tool_calls": [
                                        {
                                            "id": "call_1",
                                            "type": "function",
                                            "function": {"name": "create_course_draft", "arguments": '{"refined_id": 1, "fields": {"prelude": "Updated"}}'},
                                        }
                                    ],
                                }
                            }
                        ]
                    },
                    request=request,
                )
            assert json["messages"][-1]["role"] == "tool"
            return httpx.Response(200, json={"choices": [{"message": {"content": "Draft 9 is ready for review."}}]}, request=request)

    monkeypatch.setattr(openrouter, "Client", FakeClient)

    def tool_runner(name, arguments):
        calls.append((name, arguments))
        return {"draft": {"id": 9, "status": "proposed"}}

    results = []
    text = "".join(item for item in openrouter.stream_chat("system", [{"role": "user", "content": "update prelude"}], [{"type": "function"}], tool_runner, lambda n, r: results.append((n, r))) if isinstance(item, str))

    assert text == "Draft 9 is ready for review."
    assert calls == [("create_course_draft", {"refined_id": 1, "fields": {"prelude": "Updated"}})]
    assert results == [("create_course_draft", {"draft": {"id": 9, "status": "proposed"}})]


def test_tool_arguments_must_be_an_object(monkeypatch):
    openrouter = load_openrouter(monkeypatch)

    with pytest.raises(ValueError):
        openrouter._tool_arguments({"function": {"arguments": "[]"}})


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


def test_missing_choices_is_openrouter_error(monkeypatch):
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
            return httpx.Response(200, json={"error": {"message": "tools are unsupported by this model"}}, request=request)

    monkeypatch.setattr(openrouter, "Client", FakeClient)

    with pytest.raises(openrouter.OpenRouterError) as error:
        openrouter._chat_message([{"role": "user", "content": "hello"}], [{"type": "function"}])

    assert error.value.status_code == 502
    assert error.value.message == "The selected model does not support editor tools. Switch to a tool-calling model and try again."
