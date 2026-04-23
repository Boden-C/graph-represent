from __future__ import annotations

import base64
import os
import time
from pathlib import Path
from typing import IO, Any

from dotenv import load_dotenv
from openai import APIConnectionError, APIError, APITimeoutError, OpenAI, RateLimitError
from pydantic import BaseModel

from graph_represent.exceptions import PermanentProcessorError, RetryableProcessorError
from graph_represent.types.chat import ChatMessage, ImageContentPart, TextContentPart
from graph_represent.utils.json_utils import fingerprint_data_url
from graph_represent.utils.logging_utils import maybe_json_value, pretty_json_for_log

load_dotenv()


def image_to_data_url(image_path: Path | str) -> str:
    path = Path(image_path)
    mime_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
    }
    mime_type = mime_types.get(path.suffix.lower(), "image/png")
    encoded = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


class OpenAICompatibleProvider:
    RETRYABLE_ERRORS = (APIConnectionError, APIError, APITimeoutError, RateLimitError)

    def __init__(
        self, provider: str, base_url: str | None = None, api_key: str | None = None
    ) -> None:
        self.provider = provider
        self.base_url = base_url or self._default_base_url(provider)
        self.api_key = api_key or self._default_api_key(provider)
        timeout_value = os.getenv("GRAPH_REPRESENT_OPENAI_TIMEOUT_SECONDS")
        if timeout_value is None:
            timeout_value = os.getenv("graph_represent" + "_OPENAI_TIMEOUT_SECONDS")
        self._timeout_seconds = float(timeout_value or "180")
        self._client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=self._timeout_seconds,
        )
        self.log_file: IO[str] | None = None

    def _log(self, message: str) -> None:
        if self.log_file is not None:
            print(message, file=self.log_file, flush=True)

    def close(self) -> None:
        close = getattr(self._client, "close", None)
        if callable(close):
            close()

    @staticmethod
    def _default_base_url(provider: str) -> str:
        defaults = {
            "vllm": os.getenv("LOCAL_VLM_URL", "http://localhost:8000/v1"),
            "openrouter": os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
            "gemini": os.getenv(
                "GEMINI_OPENAI_BASE_URL",
                "https://generativelanguage.googleapis.com/v1beta/openai/",
            ),
        }
        if provider not in defaults:
            raise ValueError(f"Unsupported provider '{provider}'")
        return defaults[provider]

    @staticmethod
    def _default_api_key(provider: str) -> str:
        env_names = {
            "vllm": "LOCAL_VLM_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "gemini": "GEMINI_API_KEY",
        }
        env_name = env_names.get(provider)
        return os.getenv(env_name, "-") if env_name is not None else "-"

    def build_openai_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for message in messages:
            content: list[dict[str, Any]] = []
            for part in message.content:
                if isinstance(part, TextContentPart):
                    content.append({"type": "text", "text": part.text})
                    continue
                if isinstance(part, ImageContentPart):
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {"url": image_to_data_url(part.image_path)},
                        }
                    )
                    continue
                raise TypeError(f"Unsupported content part '{type(part).__name__}'")
            result.append({"role": message.role, "content": content})
        return result

    def normalize_request_for_cache(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        response_type: type[BaseModel],
        create_kwargs: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_messages: list[dict[str, Any]] = []
        for message in messages:
            normalized_content: list[dict[str, Any]] = []
            for part in message.get("content", []):
                if part.get("type") == "image_url":
                    image_url = str(part["image_url"]["url"])
                    normalized_content.append(
                        {
                            "type": "image_url",
                            "image_fingerprint": fingerprint_data_url(image_url),
                        }
                    )
                    continue
                normalized_content.append(part)
            normalized_messages.append({"role": message.get("role"), "content": normalized_content})

        normalized_kwargs = dict(create_kwargs)
        normalized_kwargs.pop("messages", None)
        return {
            "provider": self.provider,
            "base_url": self.base_url,
            "model": model,
            "response_type": response_type.__name__,
            "messages": normalized_messages,
            "kwargs": normalized_kwargs,
        }

    def invoke(
        self,
        *,
        model: str,
        messages: list[ChatMessage],
        response_type: type[BaseModel],
        create_kwargs: dict[str, Any],
    ) -> tuple[dict[str, Any], str]:
        openai_messages = self.build_openai_messages(messages)
        request_kwargs = {
            "model": model,
            "messages": openai_messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": response_type.__name__,
                    "schema": response_type.model_json_schema(),
                },
            },
            **create_kwargs,
        }
        normalized_request = self.normalize_request_for_cache(
            model=model,
            messages=openai_messages,
            response_type=response_type,
            create_kwargs=request_kwargs,
        )
        self._log("REQUEST_JSON:")
        self._log(pretty_json_for_log(normalized_request))

        try:
            completion = self._client.chat.completions.create(**request_kwargs)
        except self.RETRYABLE_ERRORS as exc:
            raise RetryableProcessorError(str(exc)) from exc
        except Exception as exc:
            raise PermanentProcessorError(str(exc)) from exc

        content = completion.choices[0].message.content
        if content is None:
            raise RetryableProcessorError("Provider returned an empty completion body")
        self._log("RESPONSE_JSON:")
        self._log(maybe_json_value(str(content)))
        return normalized_request, str(content)


def sleep_with_backoff(base_delay_seconds: float, attempt: int) -> None:
    time.sleep(base_delay_seconds * (2 ** max(attempt - 1, 0)))
