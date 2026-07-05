import json
import logging
import os

from dotenv import load_dotenv
from httpx import Client, HTTPError, HTTPStatusError

load_dotenv("../.env")

URL = os.environ["OPENROUTER_URL"].strip()
KEY = os.environ["OPENROUTER_API_KEY"].strip()
MODEL = os.environ["OPENROUTER_MODEL"].strip()
logger = logging.getLogger(__name__)


class OpenRouterError(RuntimeError):
    def __init__(self, status_code: int, retry_after: str | None = None):
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(self.message)

    @property
    def message(self) -> str:
        if self.status_code in {429, 503}:
            if self.retry_after:
                return f"Model provider is rate limited. Try again in {self.retry_after} seconds."
            return "Model provider is rate limited. Please try again shortly."
        return "Model provider request failed. Please try again later."


def _messages(system: str, messages: list[dict]) -> list[dict]:
    return [{"role": "system", "content": system}, *messages]


def _headers() -> dict:
    return {"Authorization": f"Bearer {KEY}"}


def _message_content(data: dict) -> str:
    try:
        return data["choices"][0]["message"]["content"].strip()
    except (KeyError, IndexError, TypeError, AttributeError) as exc:
        raise RuntimeError(f"OpenRouter response missing assistant message: {data.get('error') or data}") from exc


def _raise_for_status(response) -> None:
    try:
        response.raise_for_status()
    except HTTPStatusError as exc:
        raise OpenRouterError(exc.response.status_code, exc.response.headers.get("retry-after")) from exc


def call(system: str, user: str) -> dict:
    with Client(timeout=120) as c:
        r = c.post(
            URL,
            headers=_headers(),
            json={"model": MODEL, "messages": _messages(system, [{"role": "user", "content": user}])},
        )
        _raise_for_status(r)
        data = r.json()
        if "choices" not in data:
            raise RuntimeError(f"OpenRouter response missing choices: {data.get('error') or data}")
        text = _message_content(data)
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)


def stream_chat(system: str, messages: list[dict]):
    chat_messages = _messages(system, messages)
    emitted = False
    try:
        for token in _stream_chat(chat_messages):
            emitted = True
            yield token
    except (HTTPError, json.JSONDecodeError) as exc:
        _log_stream_fallback(exc)

    if emitted:
        return

    text = _chat_text(chat_messages)
    if text:
        yield text


def _stream_chat(messages: list[dict]):
    payload = {"model": MODEL, "messages": messages, "stream": True}
    with Client(timeout=120) as client:
        with client.stream("POST", URL, headers=_headers(), json=payload) as response:
            if response.is_error:
                response.read()
            response.raise_for_status()
            for line in response.iter_lines():
                token = _stream_token(line)
                if token:
                    yield token


def _chat_text(messages: list[dict]) -> str:
    with Client(timeout=120) as client:
        response = client.post(URL, headers=_headers(), json={"model": MODEL, "messages": messages})
        _raise_for_status(response)
        return _message_content(response.json())


def _log_stream_fallback(exc: Exception) -> None:
    if isinstance(exc, HTTPStatusError):
        response = exc.response
        logger.warning(
            "OpenRouter streaming failed; retrying without stream. status=%s model=%s body=%s",
            response.status_code,
            MODEL,
            response.text[:500],
        )
        return
    logger.warning("OpenRouter streaming failed; retrying without stream. error=%s model=%s", exc.__class__.__name__, MODEL)


def _stream_token(line: str) -> str:
    if not line or line.startswith(":"):
        return ""
    if not line.startswith("data:"):
        return ""
    data = line.removeprefix("data:").strip()
    if data == "[DONE]":
        return ""
    chunk = json.loads(data)
    choice = (chunk.get("choices") or [{}])[0]
    delta = choice.get("delta") or {}
    return delta.get("content") or ""
