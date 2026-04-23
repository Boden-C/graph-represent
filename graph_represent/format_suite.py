from __future__ import annotations

from graph_represent.graph_formats import GraphTextFormat


COMPARISON_FORMATS: tuple[GraphTextFormat, ...] = (
    GraphTextFormat.JSON,
    GraphTextFormat.XML,
    GraphTextFormat.PYTHON_DSL,
    GraphTextFormat.MERMAID,
    GraphTextFormat.NESTED_JSON,
    GraphTextFormat.EDGE_TABLE,
    GraphTextFormat.FACTS,
    GraphTextFormat.CLAIM_BUNDLES_INLINE,
    GraphTextFormat.RELATION_XML,
    GraphTextFormat.INLINE_PYTHON_DSL,
    GraphTextFormat.COMPACT_JSON,
    GraphTextFormat.EDGE_SENTENCES,
)
