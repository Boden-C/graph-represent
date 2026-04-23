from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field, model_validator

from graph_represent.registry import register_type
from graph_represent.types.base import SchemaModel
from graph_represent.types.graph import Graph
from graph_represent.types.persuasion import PersuasionLabels
from graph_represent.utils.files import image_filename


@register_type("PersuasionSample")
class PersuasionSample(SchemaModel):
    id: str = Field(validation_alias=AliasChoices("id", "item_id"))
    image_md5: str | None = None
    image_filename: str | None = Field(
        default=None,
        validation_alias=AliasChoices("image_filename", "file_name"),
    )
    image_path: Path | str | None = Field(
        default=None,
        validation_alias=AliasChoices("image_path", "image"),
    )
    text: str | None = None
    gold_labels: PersuasionLabels | None = None

    @model_validator(mode="after")
    def normalize_image_fields(self) -> PersuasionSample:
        if self.image_filename is None and self.image_path is not None:
            self.image_filename = image_filename(self.image_path)
        return self

    @property
    def item_id(self) -> str:
        return self.id


@register_type("PersuasionEvaluationSample")
class PersuasionEvaluationSample(PersuasionSample):
    graphs_by_version: dict[str, Graph] = Field(default_factory=dict)


@register_type("JsonObject")
class JsonObject(SchemaModel):
    data: dict[str, object] = Field(default_factory=dict)


@register_type("ArgumentGraphInterpretation")
class ArgumentGraphInterpretation(SchemaModel):
    essay: str


@register_type("ArgumentGraphData")
class ArgumentGraphData(SchemaModel):
    interpretation: ArgumentGraphInterpretation | None = None
    graph: Graph


@register_type("ArgumentGraphTextData")
class ArgumentGraphTextData(SchemaModel):
    graph_format: str
    graph_text: str
    graph_signature: str


@register_type("ArgumentGraphRecord")
class ArgumentGraphRecord(SchemaModel):
    id: str
    image_md5: str | None = None
    image_filename: str = Field(validation_alias=AliasChoices("image_filename", "file_name"))
    data: ArgumentGraphData

    @model_validator(mode="before")
    @classmethod
    def normalize_legacy_fields(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data
        payload = dict(data)
        semeval_name = payload.get("semeval_name")
        legacy_id = payload.get("id")
        if isinstance(semeval_name, str):
            if payload.get("image_md5") is None and isinstance(legacy_id, str):
                payload["image_md5"] = legacy_id
            payload["id"] = semeval_name
        if payload.get("image_filename") is None and payload.get("file_name") is not None:
            payload["image_filename"] = payload["file_name"]
        return payload

    @model_validator(mode="after")
    def normalize_image_filename_field(self) -> ArgumentGraphRecord:
        self.image_filename = image_filename(self.image_filename)
        return self

    @property
    def semeval_name(self) -> str:
        return self.id

    @property
    def file_name(self) -> str:
        return self.image_filename


@register_type("ArgumentGraphTextRecord")
class ArgumentGraphTextRecord(SchemaModel):
    id: str
    image_md5: str | None = None
    image_filename: str = Field(validation_alias=AliasChoices("image_filename", "file_name"))
    data: ArgumentGraphTextData

    @model_validator(mode="after")
    def normalize_image_filename_field(self) -> ArgumentGraphTextRecord:
        self.image_filename = image_filename(self.image_filename)
        return self


@register_type("PersuasionGraphFormatSample")
class PersuasionGraphFormatSample(PersuasionSample):
    graph_texts_by_variant: dict[str, ArgumentGraphTextData] = Field(default_factory=dict)
