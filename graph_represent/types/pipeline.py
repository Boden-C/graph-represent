from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class RetryPolicyConfig(BaseModel):
    max_attempts: int = 3
    base_delay_seconds: float = 2.0


class DataLoaderSpec(BaseModel):
    name: str
    item_type: str
    config: dict[str, Any] = Field(default_factory=dict)


class ProcessorStageSpec(BaseModel):
    name: str
    processor: str
    input_type: str
    output_type: str
    config: dict[str, Any] = Field(default_factory=dict)
    retry: RetryPolicyConfig = Field(default_factory=RetryPolicyConfig)
    save_output: bool = True


class JsonPipelineSpec(BaseModel):
    version: int = 1
    pipeline_name: str
    dataloader: DataLoaderSpec
    stages: list[ProcessorStageSpec]

    @field_validator("stages")
    @classmethod
    def validate_stages_non_empty(cls, value: list[ProcessorStageSpec]) -> list[ProcessorStageSpec]:
        if not value:
            raise ValueError("stages must not be empty")
        return value


class OutputRecord(BaseModel):
    item_id: str
    stage_name: str
    path: Path
    sha256: str


class InferenceCacheEntry(BaseModel):
    cache_key: str
    provider: str
    model: str
    request_payload: dict[str, Any]
    response_text: str
