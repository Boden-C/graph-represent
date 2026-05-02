from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import Field

from graph_represent.registry import register_type
from graph_represent.types.base import SchemaModel
from graph_represent.types.graph import Graph


@register_type("CorpusGraphSample")
class CorpusGraphSample(SchemaModel):
    id: str
    corpus: str
    graph: Graph
    graph_version: str
    image_filename: str | None = None
    text: str | None = None
    gold: dict[str, Any] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def item_id(self) -> str:
        return self.id


@register_type("GraphCorpusManifest")
class GraphCorpusManifest(SchemaModel):
    corpus: str
    graph_path: Path
    answers_path: Path | None = None
    item_count: int
    answered_count: int


@register_type("IcleEssaySample")
class IcleEssaySample(SchemaModel):
    id: str
    corpus: str
    prompt: str | None = None
    essay: str
    paragraphs: list[str] = Field(default_factory=list)
    scores: dict[str, float] = Field(default_factory=dict)
    raw_scores: dict[str, float] = Field(default_factory=dict)

    @property
    def item_id(self) -> str:
        return self.id
