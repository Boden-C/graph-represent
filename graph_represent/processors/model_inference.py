from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from graph_represent.processors.base import Processor, ProcessorContext
from graph_represent.types.chat import ChatMessage, ChatMessagesPayload, TextContentPart


class ModelInference(Processor):
    def validate_types(self) -> None:
        if self.input_type is not ChatMessagesPayload:
            raise ValueError("ModelInference requires input_type ChatMessagesPayload")
        if not issubclass(self.output_type, BaseModel):
            raise ValueError("ModelInference requires a Pydantic output_type")

    def _load_system_prompt(self) -> str | None:
        prompt_text = self.config.get("system_prompt")
        prompt_path = self.config.get("system_prompt_file")
        if prompt_text and prompt_path:
            raise ValueError("Specify only one of system_prompt or system_prompt_file")
        if prompt_path:
            return Path(prompt_path).read_text(encoding="utf-8")
        return prompt_text

    def _validate_response_text(self, response_text: str) -> BaseModel:
        try:
            return self.output_type.model_validate_json(response_text)
        except Exception:
            salvage_method = getattr(self.output_type, "salvage_response_text", None)
            if not callable(salvage_method):
                raise
            salvaged_payload = salvage_method(response_text)
            if salvaged_payload is None:
                raise
            return self.output_type.model_validate(salvaged_payload)

    def process(self, input_data: BaseModel, context: ProcessorContext) -> BaseModel:
        payload = ChatMessagesPayload.model_validate(input_data.model_dump())
        provider = context.runtime.get_provider(
            str(self.config["provider"]),
            base_url=self.config.get("base_url"),
            base_urls=self.config.get("base_urls"),
            api_key=self.config.get("api_key"),
            model=str(self.config.get("model")) if self.config.get("model") is not None else None,
        )

        messages = list(payload.messages)
        system_prompt = self._load_system_prompt()
        if system_prompt:
            messages = [
                ChatMessage(role="system", content=[TextContentPart(text=system_prompt)]),
                *messages,
            ]

        create_kwargs: dict[str, object] = {}
        if self.config.get("temperature") is not None:
            create_kwargs["temperature"] = self.config["temperature"]
        if self.config.get("max_tokens") is not None:
            create_kwargs["max_completion_tokens"] = self.config["max_tokens"]
        if self.config.get("top_p") is not None:
            create_kwargs["top_p"] = self.config["top_p"]
        if self.config.get("extra_create_kwargs"):
            create_kwargs.update(dict(self.config["extra_create_kwargs"]))

        openai_messages = provider.build_openai_messages(messages)
        request_kwargs = {
            "model": str(self.config["model"]),
            "messages": openai_messages,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": self.output_type.__name__,
                    "schema": self.output_type.model_json_schema(),
                },
            },
            **create_kwargs,
        }
        normalized_request = provider.normalize_request_for_cache(
            model=str(self.config["model"]),
            messages=openai_messages,
            response_type=self.output_type,
            create_kwargs=request_kwargs,
        )
        cache_key = context.runtime.inference_cache.build_cache_key(normalized_request)
        cached_response = context.runtime.inference_cache.load(cache_key)
        if cached_response is not None:
            return self._validate_response_text(cached_response)

        normalized_request, response_text = provider.invoke(
            model=str(self.config["model"]),
            messages=messages,
            response_type=self.output_type,
            create_kwargs=create_kwargs,
        )
        cache_key = context.runtime.inference_cache.build_cache_key(normalized_request)
        context.runtime.inference_cache.store(
            cache_key=cache_key,
            provider=provider.provider,
            model=str(self.config["model"]),
            request_payload=normalized_request,
            response_text=response_text,
        )
        return self._validate_response_text(response_text)
