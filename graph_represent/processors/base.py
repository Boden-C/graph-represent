from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

from graph_represent.exceptions import RetryableProcessorError
from graph_represent.providers.openai_compatible import sleep_with_backoff
from graph_represent.types.pipeline import RetryPolicyConfig

SourceT = TypeVar("SourceT", bound=BaseModel)
InputT = TypeVar("InputT", bound=BaseModel)
OutputT = TypeVar("OutputT", bound=BaseModel)


@dataclass(frozen=True)
class ProcessorContext(Generic[SourceT]):
    item_id: str
    source_item: SourceT
    runtime: RuntimeProtocol


class RuntimeProtocol(ABC):
    @abstractmethod
    def get_provider(
        self,
        provider: str,
        *,
        base_url: str | None,
        base_urls: list[str] | None,
        api_key: str | None,
        model: str | None,
    ):
        raise NotImplementedError

    @property
    @abstractmethod
    def inference_cache(self):
        raise NotImplementedError


class Processor(ABC, Generic[InputT, OutputT, SourceT]):
    def __init__(
        self,
        *,
        name: str,
        config: dict[str, Any],
        input_type: type[InputT],
        output_type: type[OutputT],
        retry: RetryPolicyConfig,
    ) -> None:
        self.name = name
        self.config = config
        self.input_type = input_type
        self.output_type = output_type
        self.retry = retry
        self.validate_types()

    def validate_types(self) -> None:
        return None

    def __call__(self, input_data: InputT, context: ProcessorContext[SourceT]) -> OutputT:
        validated_input = self.input_type.model_validate(input_data.model_dump())
        last_error: Exception | None = None
        for attempt in range(1, self.retry.max_attempts + 1):
            try:
                output = self.process(validated_input, context)
                return self.output_type.model_validate(output.model_dump())
            except RetryableProcessorError as exc:
                last_error = exc
                if attempt >= self.retry.max_attempts:
                    raise
                sleep_with_backoff(self.retry.base_delay_seconds, attempt)
        assert last_error is not None
        raise last_error

    @abstractmethod
    def process(self, input_data: InputT, context: ProcessorContext[SourceT]) -> OutputT:
        raise NotImplementedError
