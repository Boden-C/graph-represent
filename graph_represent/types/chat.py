from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from graph_represent.registry import register_type
from graph_represent.types.base import SchemaModel


class TextContentPart(SchemaModel):
    type: Literal["text"] = "text"
    text: str


class ImageContentPart(SchemaModel):
    type: Literal["image_url"] = "image_url"
    image_path: Path | str


ContentPart = TextContentPart | ImageContentPart


class ChatMessage(SchemaModel):
    role: Literal["system", "user", "assistant"]
    content: list[ContentPart] = Field(default_factory=list)


@register_type("ChatMessagesPayload")
class ChatMessagesPayload(SchemaModel):
    messages: list[ChatMessage] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_non_empty(self) -> ChatMessagesPayload:
        if not self.messages:
            raise ValueError("messages must not be empty")
        return self
