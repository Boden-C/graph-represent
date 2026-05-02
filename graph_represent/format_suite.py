from __future__ import annotations

from graph_represent.graph_formats import GraphTextFormat


COMPARISON_FORMATS: tuple[GraphTextFormat, ...] = (
    GraphTextFormat.PYTHON_DSL,
    GraphTextFormat.XML,
    GraphTextFormat.JSON,
    GraphTextFormat.CLAIM_BUNDLES_INLINE,
    GraphTextFormat.INLINE_PYTHON_DSL,
    GraphTextFormat.COMPACT_JSON,
    GraphTextFormat.FORMAL_PROOF,
)
