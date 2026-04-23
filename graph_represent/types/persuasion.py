from __future__ import annotations

import re
from typing import Any

from pydantic import Field, model_serializer, model_validator

from graph_represent.registry import register_type
from graph_represent.types.base import SchemaModel

TECHNIQUES_TASK3: list[str] = [
    "appeal to authority",
    "appeal to fear/prejudice",
    "black-and-white fallacy/dictatorship",
    "causal oversimplification",
    "doubt",
    "exaggeration/minimisation",
    "flag-waving",
    "glittering generalities (virtue)",
    "loaded language",
    "misrepresentation of someone's position (straw man)",
    "name calling/labeling",
    "obfuscation, intentional vagueness, confusion",
    "presenting irrelevant data (red herring)",
    "reductio ad hitlerum",
    "repetition",
    "slogans",
    "smears",
    "thought-terminating cliché",
    "whataboutism",
    "bandwagon",
    "transfer",
    "appeal to (strong) emotions",
]
TECHNIQUES_TASK3_SET = frozenset(TECHNIQUES_TASK3)


def normalize_technique_name(value: str) -> str:
    return " ".join(value.strip().lower().split())


@register_type("PersuasionLabels")
class PersuasionLabels(SchemaModel):
    labels: list[str] = Field(default_factory=list)
    reasons: dict[str, str | None] = Field(default_factory=dict)

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = "#/$defs/{model}",
    ) -> dict[str, Any]:
        del by_alias, ref_template
        reasons_properties: dict[str, Any] = {}
        for technique in TECHNIQUES_TASK3:
            reasons_properties[technique] = {"anyOf": [{"type": "string"}, {"type": "null"}]}
        return {
            "type": "object",
            "properties": {
                "reasons": {
                    "type": "object",
                    "properties": reasons_properties,
                    "required": TECHNIQUES_TASK3,
                    "additionalProperties": False,
                }
            },
            "required": ["reasons"],
            "additionalProperties": False,
        }

    @staticmethod
    def _normalize_reason(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        trimmed = value.strip()
        return trimmed or None

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if isinstance(data, dict) and isinstance(data.get("reasons"), dict):
            reasons: dict[str, str | None] = {}
            for key, value in data["reasons"].items():
                if isinstance(key, str):
                    reasons[normalize_technique_name(key)] = cls._normalize_reason(value)
            labels = [label for label, reason in reasons.items() if reason is not None]
            return {"labels": labels, "reasons": reasons}
        return data

    @model_validator(mode="after")
    def normalize_output(self) -> PersuasionLabels:
        normalized_labels: list[str] = []
        seen: set[str] = set()
        for label in self.labels:
            normalized = normalize_technique_name(label)
            if normalized and normalized not in seen:
                seen.add(normalized)
                normalized_labels.append(normalized)

        normalized_reasons: dict[str, str | None] = {}
        for label in TECHNIQUES_TASK3:
            normalized_reasons[label] = None

        for label, reason in self.reasons.items():
            normalized_label = normalize_technique_name(label)
            if normalized_label in TECHNIQUES_TASK3_SET:
                normalized_reasons[normalized_label] = self._normalize_reason(reason)

        for label in normalized_labels:
            if label in TECHNIQUES_TASK3_SET:
                normalized_reasons[label] = normalized_reasons.get(label)

        self.labels = [label for label in TECHNIQUES_TASK3 if label in set(normalized_labels)]
        self.reasons = normalized_reasons
        return self

    @model_serializer
    def serialize(self) -> dict[str, Any]:
        selected = set(self.labels)
        return {
            "schema_version": self.schema_version,
            "labels": [label for label in TECHNIQUES_TASK3 if label in selected],
            "reasons": {label: self.reasons.get(label) for label in TECHNIQUES_TASK3},
        }


@register_type("PersuasionItemResult")
class PersuasionItemResult(SchemaModel):
    item_id: str
    predicted: PersuasionLabels
    gold: PersuasionLabels | None = None
    tp_labels: list[str] = Field(default_factory=list)
    fp_labels: list[str] = Field(default_factory=list)
    tn_labels: list[str] = Field(default_factory=list)
    fn_labels: list[str] = Field(default_factory=list)


@register_type("PersuasionGraphFormatVariantResult")
class PersuasionGraphFormatVariantResult(SchemaModel):
    item_id: str
    version_name: str
    graph_format: str
    model_name: str
    result: PersuasionItemResult


@register_type("PersuasionGraphFormatSampleResult")
class PersuasionGraphFormatSampleResult(SchemaModel):
    item_id: str
    gold: PersuasionLabels | None = None
    variants: list[PersuasionGraphFormatVariantResult] = Field(default_factory=list)


@register_type("PersuasionAggregateScores")
class PersuasionAggregateScores(SchemaModel):
    micro_precision: float
    micro_recall: float
    micro_f1: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    tp: int
    fp: int
    tn: int
    fn: int
    invalid_labels: list[str] = Field(default_factory=list)


@register_type("PersuasionTechniqueScores")
class PersuasionTechniqueScores(SchemaModel):
    scores: dict[str, float] = Field(default_factory=dict)

    @classmethod
    def salvage_response_text(cls, text: str) -> dict[str, object] | None:
        salvaged_scores: dict[str, float] = {label: 0.0 for label in TECHNIQUES_TASK3}
        found_any = False
        for label in TECHNIQUES_TASK3:
            pattern = rf'"{re.escape(label)}"\s*:\s*(-?\d+(?:\.\d+)?)'
            match = re.search(pattern, text)
            if match is None:
                continue
            found_any = True
            salvaged_scores[label] = cls._normalize_score(match.group(1))
        if not found_any:
            return None
        return {"scores": salvaged_scores}

    @classmethod
    def model_json_schema(
        cls,
        by_alias: bool = True,
        ref_template: str = "#/$defs/{model}",
    ) -> dict[str, Any]:
        del by_alias, ref_template
        return {
            "type": "object",
            "properties": {
                "scores": {
                    "type": "object",
                    "properties": {
                        technique: {
                            "type": "number",
                            "minimum": 0.0,
                            "maximum": 1.0,
                        }
                        for technique in TECHNIQUES_TASK3
                    },
                    "required": TECHNIQUES_TASK3,
                    "additionalProperties": False,
                }
            },
            "required": ["scores"],
            "additionalProperties": False,
        }

    @staticmethod
    def _normalize_score(value: Any) -> float:
        if isinstance(value, bool):
            return float(value)
        if isinstance(value, int | float):
            return max(0.0, min(1.0, float(value)))
        if isinstance(value, str):
            return max(0.0, min(1.0, float(value.strip())))
        raise TypeError(f"Unsupported score value: {value!r}")

    @model_validator(mode="before")
    @classmethod
    def normalize_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        if isinstance(data.get("scores"), dict):
            raw_scores = data["scores"]
        else:
            raw_scores = {
                key: value
                for key, value in data.items()
                if isinstance(key, str) and normalize_technique_name(key) in TECHNIQUES_TASK3_SET
            }
        normalized_scores: dict[str, float] = {label: 0.0 for label in TECHNIQUES_TASK3}
        for key, value in raw_scores.items():
            if isinstance(key, str):
                normalized_key = normalize_technique_name(key)
                if normalized_key in TECHNIQUES_TASK3_SET:
                    normalized_scores[normalized_key] = cls._normalize_score(value)
        return {"scores": normalized_scores}

    @model_validator(mode="after")
    def normalize_output(self) -> PersuasionTechniqueScores:
        normalized_scores: dict[str, float] = {label: 0.0 for label in TECHNIQUES_TASK3}
        for label, value in self.scores.items():
            normalized_label = normalize_technique_name(label)
            if normalized_label in TECHNIQUES_TASK3_SET:
                normalized_scores[normalized_label] = self._normalize_score(value)
        self.scores = normalized_scores
        return self


@register_type("PersuasionThresholdVariantResult")
class PersuasionThresholdVariantResult(SchemaModel):
    item_id: str
    version_name: str
    input_mode: str
    model_name: str
    scores: PersuasionTechniqueScores
    gold: PersuasionLabels | None = None
    gold_split: str | None = None
    input_char_count: int | None = None
    input_line_count: int | None = None


@register_type("PersuasionThresholdSampleResult")
class PersuasionThresholdSampleResult(SchemaModel):
    item_id: str
    gold: PersuasionLabels | None = None
    variants: list[PersuasionThresholdVariantResult] = Field(default_factory=list)


@register_type("PersuasionPredictionRecord")
class PersuasionPredictionRecord(SchemaModel):
    item_id: str
    labels: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def normalize_labels(self) -> PersuasionPredictionRecord:
        seen: set[str] = set()
        normalized: list[str] = []
        for label in self.labels:
            normalized_label = normalize_technique_name(label)
            if normalized_label in TECHNIQUES_TASK3_SET and normalized_label not in seen:
                seen.add(normalized_label)
                normalized.append(normalized_label)
        self.labels = [label for label in TECHNIQUES_TASK3 if label in seen]
        return self


@register_type("PersuasionThresholdSpec")
class PersuasionThresholdSpec(SchemaModel):
    version_name: str
    input_mode: str
    thresholds: dict[str, float] = Field(default_factory=dict)
    label_f1: dict[str, float] = Field(default_factory=dict)


@register_type("PersuasionThresholdEvaluationSummary")
class PersuasionThresholdEvaluationSummary(SchemaModel):
    version_name: str
    input_mode: str
    micro_f1: float
    macro_f1: float
    item_count: int


@register_type("PersuasionThresholdPredictions")
class PersuasionThresholdPredictions(SchemaModel):
    version_name: str
    input_mode: str
    predictions: list[PersuasionPredictionRecord] = Field(default_factory=list)


@register_type("PersuasionThresholdOptimizationInput")
class PersuasionThresholdOptimizationInput(SchemaModel):
    samples: list[PersuasionThresholdSampleResult] = Field(default_factory=list)


@register_type("PersuasionThresholdOptimizationResult")
class PersuasionThresholdOptimizationResult(SchemaModel):
    thresholds: list[PersuasionThresholdSpec] = Field(default_factory=list)
    summaries: list[PersuasionThresholdEvaluationSummary] = Field(default_factory=list)
    predictions: list[PersuasionThresholdPredictions] = Field(default_factory=list)
