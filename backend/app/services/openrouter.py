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

_context_length: int | None = None


def fetch_context_length() -> int:
    global _context_length
    if _context_length is not None:
        return _context_length
    api_base = URL.rsplit("/chat/completions", 1)[0]
    try:
        with Client(timeout=10) as client:
            resp = client.get(f"{api_base}/model/{MODEL}", headers=_headers())
            resp.raise_for_status()
            data = resp.json().get("data") or {}
            _context_length = int(data.get("context_length") or 128000)
            logger.info("Model %s context_length=%d", MODEL, _context_length)
            return _context_length
    except Exception as exc:
        logger.warning("Failed to fetch context_length for %s: %s", MODEL, exc)
        _context_length = 128000
        return _context_length


def context_length() -> int:
    return _context_length or 128000


_TOOL_LABELS = {
    "get_course_codes": "Looking up courses",
    "get_current_course_json": "Reading course data",
    "get_course_syllabus": "Reading syllabus",
    "get_course_textbooks": "Reading textbooks",
    "get_course_deterministic": "Reading course properties",
    "get_course_lab": "Reading lab details",
    "get_course_fields": "Reading course fields",
    "batch_read_courses": "Reading courses",
    "get_curriculum_json": "Loading curriculum",
    "get_curriculum_stats": "Computing statistics",
    "create_course_draft": "Creating draft",
    "create_document_draft": "Creating document draft",
    "create_report": "Generating report",
    "create_spreadsheet": "Generating spreadsheet",
    "diff_course_json": "Comparing courses",
    "diff_versions": "Comparing versions",
    "get_version": "Loading snapshot",
    "update_course_field": "Updating course",
    "update_deterministic_fields": "Updating course",
    "get_attachment_text": "Reading attachment",
    "list_specializations": "Loading specializations",
    "define_specialization": "Creating specialization",
    "assign_elective_to_tracks": "Categorizing elective",
    "get_course_assignments": "Reading elective assignments",
    "fetch_url": "Fetching URL",
    "web_search": "Searching the web",
    "signal_done": "Finalizing",
}


def tool_status_label(name: str) -> str:
    return _TOOL_LABELS.get(name, name.replace("_", " ").title())


class OpenRouterError(RuntimeError):
    def __init__(self, status_code: int, retry_after: str | None = None, message: str | None = None, provider_message: str = ""):
        self.status_code = status_code
        self.retry_after = retry_after
        self._message = message
        self.provider_message = provider_message
        super().__init__(self.message)

    @property
    def message(self) -> str:
        if self._message:
            return self._message
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
        return _assistant_message(data)["content"].strip()
    except (KeyError, TypeError, AttributeError) as exc:
        raise OpenRouterError(502, message="Model provider returned an invalid response. Please try again later.", provider_message=str(data.get("error") or data)[:500]) from exc


def _raise_for_status(response) -> None:
    try:
        response.raise_for_status()
    except HTTPStatusError as exc:
        raise OpenRouterError(
            exc.response.status_code,
            exc.response.headers.get("retry-after"),
            provider_message=exc.response.text[:500],
        ) from exc


def _provider_error(data: dict) -> str:
    error = data.get("error") if isinstance(data, dict) else None
    if isinstance(error, dict):
        return str(error.get("message") or error)
    return str(error or data)[:500]


def _public_shape_error(provider_message: str) -> str:
    lowered = provider_message.lower()
    if "tool" in lowered and ("support" in lowered or "unsupported" in lowered):
        return "The selected model does not support editor tools. Switch to a tool-calling model and try again."
    if "rate" in lowered or "quota" in lowered:
        return "Model provider is rate limited. Please try again shortly."
    return "Model provider returned an invalid response. Please try again later."


def _assistant_message(data: dict) -> dict:
    try:
        message = data["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        provider_message = _provider_error(data)
        raise OpenRouterError(502, message=_public_shape_error(provider_message), provider_message=provider_message) from exc
    if not isinstance(message, dict):
        raise OpenRouterError(502, message="Model provider returned an invalid response. Please try again later.", provider_message=str(message)[:500])
    return message


def call(system: str, user: str) -> dict:
    with Client(timeout=120) as c:
        r = c.post(
            URL,
            headers=_headers(),
            json={"model": MODEL, "messages": _messages(system, [{"role": "user", "content": user}])},
        )
        _raise_for_status(r)
        data = r.json()
        text = _message_content(data)
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(text)


def stream_chat(system: str, messages: list[dict], tools: list[dict] | None = None, tool_runner=None, on_tool_result=None):
    chat_messages = _messages(system, messages)
    if tools and tool_runner:
        yield from _chat_with_tools(chat_messages, tools, tool_runner, on_tool_result)
        return

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


def _chat_message(messages: list[dict], tools: list[dict]) -> tuple[dict, int]:
    with Client(timeout=120) as client:
        response = client.post(URL, headers=_headers(), json={"model": MODEL, "messages": messages, "tools": tools})
        _raise_for_status(response)
        data = response.json()
        prompt_tokens = (data.get("usage") or {}).get("prompt_tokens") or 0
        return _assistant_message(data), prompt_tokens


def _chat_with_tools(messages: list[dict], tools: list[dict], tool_runner, on_tool_result=None):
    last_prompt_tokens = 0
    for i in range(15):
        yield {"$status": f"Thinking (step {i + 1})..."}
        message, prompt_tokens = _chat_message(messages, tools)
        if prompt_tokens:
            last_prompt_tokens = prompt_tokens
        tool_calls = message.get("tool_calls") or []
        if not tool_calls:
            text = str(message.get("content") or "").strip()
            if text:
                yield text
            if last_prompt_tokens:
                yield {"$usage": {"prompt_tokens": last_prompt_tokens, "context_length": context_length()}}
            return

        messages.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": tool_calls})
        for tool_call in tool_calls:
            name = (tool_call.get("function") or {}).get("name") or ""
            arguments = _tool_arguments(tool_call)
            yield {"$status": f"{tool_status_label(name)}..."}
            yield {"$event": "tool_call", "name": name, "arguments": arguments}
            try:
                result = _run_tool(tool_runner, name, arguments)
            except ValueError as exc:
                result = {"error": str(exc)}
            yield {"$event": "tool_result", "name": name, "status": "ok" if "error" not in result else "error"}
            if on_tool_result:
                on_tool_result(name, result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.get("id") or name,
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
    yield "I created tool results, but could not finish the response. Please check the Review panel."
    if last_prompt_tokens:
        yield {"$usage": {"prompt_tokens": last_prompt_tokens, "context_length": context_length()}}


def _tool_arguments(tool_call: dict) -> dict:
    raw = (tool_call.get("function") or {}).get("arguments") or "{}"
    arguments = json.loads(raw) if isinstance(raw, str) else raw
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be an object")
    return arguments


def _run_tool(tool_runner, name: str, arguments: dict) -> dict:
    try:
        return tool_runner(name, arguments)
    except Exception as exc:
        return {"error": str(exc)}


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


try:
    fetch_context_length()
except Exception:
    pass
