from __future__ import annotations

import json
import re
from typing import Any

from pydantic import Field, field_validator

from graph_represent.registry import register_type
from graph_represent.types.base import SchemaModel


@register_type("ArgumentQualityScores")
class ArgumentQualityScores(SchemaModel):
    scores: dict[str, float] = Field(default_factory=dict)
    rationale: str

    @classmethod
    def salvage_response_text(cls, text: str) -> dict[str, object] | None:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = None
        if isinstance(parsed, dict):
            if isinstance(parsed.get("scores"), dict):
                if parsed.get("rationale") is None:
                    parsed = {**parsed, "rationale": "No rationale provided by model."}
                return parsed
            numeric_items = {
                str(key): value for key, value in parsed.items() if isinstance(value, int | float)
            }
            if numeric_items:
                rationale = parsed.get("rationale")
                if rationale is None:
                    rationale = "No rationale provided by model."
                return {"scores": numeric_items, "rationale": str(rationale)}

        matches = re.findall(r'"?([A-Za-z][A-Za-z0-9_ -]{1,40})"?\s*[:=]\s*(-?\d+(?:\.\d+)?)', text)
        if not matches:
            return None
        return {
            "scores": {key.strip().lower().replace(" ", "_"): float(value) for key, value in matches},
            "rationale": "No rationale provided by model.",
        }

    @field_validator("scores", mode="before")
    @classmethod
    def normalize_scores(cls, value: Any) -> dict[str, float]:
        if not isinstance(value, dict):
            return {}
        normalized: dict[str, float] = {}
        for key, item in value.items():
            if isinstance(item, bool):
                normalized[str(key)] = float(item)
            elif isinstance(item, int | float):
                normalized[str(key)] = float(item)
            elif isinstance(item, str):
                try:
                    normalized[str(key)] = float(item.strip())
                except ValueError:
                    continue
        return normalized


@register_type("ArgumentQualityVariantResult")
class ArgumentQualityVariantResult(SchemaModel):
    item_id: str
    version_name: str
    input_mode: str
    model_name: str
    scores: ArgumentQualityScores
    gold_scores: dict[str, float] | None = None
    gold_raw_scores: dict[str, float] | None = None
    input_char_count: int | None = None
    input_line_count: int | None = None


@register_type("ArgumentQualitySampleResult")
class ArgumentQualitySampleResult(SchemaModel):
    item_id: str
    gold_scores: dict[str, float] | None = None
    gold_raw_scores: dict[str, float] | None = None
    variants: list[ArgumentQualityVariantResult] = Field(default_factory=list)
