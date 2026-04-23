from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Iterable

CORPUS_ROOT = Path(__file__).resolve().parent
GRAPH_PATH = CORPUS_ROOT / "graphs" / "essays_normalized.json"
OUTPUT_PATH = CORPUS_ROOT / "answers" / "quality_scores.json"
REPORT_PATH = CORPUS_ROOT / "answers" / "score_match_report.json"
QUALITY_TABLE_PATH = (
    CORPUS_ROOT / "raw" / "argument_quality_dataset" / "quality_annotation_table.csv"
)
ORIGINAL_ANN_ROOT = (
    CORPUS_ROOT / "raw" / "extracted_essays" / "brat_data" / "brat-project-final"
)
SOURCE_DATASET = "persuasive-essays-argument-quality-dataset"
SOURCE_URL = "https://gitlab.com/santimarro/persuasive-essays-argument-quality-dataset"
SCORE_SCALE_MAX = 25.0
RHETORIC_WITH_STRATEGY = {"Logos", "Pathos", "Ethos"}
SCORE_DERIVATION = {
    "cogency_mean": "Mean Cogency_* component score divided by 25.",
    "rhetoric_strategy_rate": "Share of components labeled Logos, Pathos, or Ethos.",
    "reasonableness_counterargument_mean": (
        "Mean Reasonableness_counterargument_* score divided by 25, "
        "only where the source dataset annotates the field."
    ),
    "reasonableness_rebuttal_mean": (
        "Mean Reasonableness_rebuttal_* score divided by 25, "
        "only where the source dataset annotates the field."
    ),
    "overall_quality_mean": "Mean of the available essay-level aggregate scores above.",
}


def _normalize_id(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith("essay"):
        return Path(text).stem
    return f"essay{int(text):03d}" if text.isdigit() else Path(text).stem


def _score_suffix(value: str, prefix: str) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    match = re.fullmatch(rf"{re.escape(prefix)}_(\d+)", text)
    if match is None:
        return None
    return float(match.group(1)) / SCORE_SCALE_MAX


def _rhetoric_score(value: str) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    if text == "No_Rethorics":
        return 0.0
    if text in RHETORIC_WITH_STRATEGY:
        return 1.0
    return None


def _load_quality_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t", skipinitialspace=True)
        return [
            {str(key).strip(): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def _node_index_by_component_id(essay_id: str) -> dict[str, dict[str, Any]]:
    ann_path = ORIGINAL_ANN_ROOT / f"{essay_id}.ann"
    if not ann_path.exists():
        return {}

    node_index: dict[str, dict[str, Any]] = {}
    current_index = 0
    for line in ann_path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("T"):
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        component_id = parts[0]
        type_and_span = parts[1].split(" ", maxsplit=1)
        node_index[component_id] = {
            "node_idx": current_index,
            "node_type": type_and_span[0],
            "text": parts[2],
        }
        current_index += 1
    return node_index


def _safe_mean(values: Iterable[float | None]) -> float | None:
    clean_values = [value for value in values if value is not None]
    if not clean_values:
        return None
    return round(mean(clean_values), 6)


def _essay_scores(component_scores: list[dict[str, Any]]) -> dict[str, float]:
    cogency = _safe_mean(item["scores"].get("cogency") for item in component_scores)
    rhetoric = _safe_mean(
        item["scores"].get("rhetoric_strategy_rate") for item in component_scores
    )
    counterargument = _safe_mean(
        item["scores"].get("reasonableness_counterargument")
        for item in component_scores
    )
    rebuttal = _safe_mean(
        item["scores"].get("reasonableness_rebuttal") for item in component_scores
    )

    scores: dict[str, float] = {}
    if cogency is not None:
        scores["cogency_mean"] = cogency
    if rhetoric is not None:
        scores["rhetoric_strategy_rate"] = rhetoric
    if counterargument is not None:
        scores["reasonableness_counterargument_mean"] = counterargument
    if rebuttal is not None:
        scores["reasonableness_rebuttal_mean"] = rebuttal

    overall = _safe_mean(scores.values())
    if overall is not None:
        scores["overall_quality_mean"] = overall
    return scores


def _component_score(row: dict[str, str], node_index: dict[str, dict[str, Any]]) -> dict[str, Any]:
    component_id = row["component_id"]
    graph_node = node_index.get(component_id, {})
    scores = {
        "cogency": _score_suffix(row["cogency_score"], "Cogency"),
        "rhetoric_strategy_rate": _rhetoric_score(row["rhetorical_strategy"]),
        "reasonableness_counterargument": _score_suffix(
            row["reasonableness_counterargument"],
            "Reasonableness_counterargument",
        ),
        "reasonableness_rebuttal": _score_suffix(
            row["reasonableness_rebuttal"],
            "Reasonableness_rebuttal",
        ),
    }
    return {
        "component_id": component_id,
        "node_idx": graph_node.get("node_idx"),
        "node_type": graph_node.get("node_type"),
        "text": graph_node.get("text"),
        "labels": {
            "cogency_score": row["cogency_score"],
            "rhetorical_strategy": row["rhetorical_strategy"],
            "reasonableness_counterargument": row["reasonableness_counterargument"],
            "reasonableness_rebuttal": row["reasonableness_rebuttal"],
        },
        "scores": {key: value for key, value in scores.items() if value is not None},
    }


def _build_answers(path: Path) -> dict[str, dict[str, Any]]:
    rows_by_essay: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in _load_quality_rows(path):
        essay_id = _normalize_id(row["essay_number"])
        if essay_id:
            rows_by_essay[essay_id].append(row)

    answers: dict[str, dict[str, Any]] = {}
    for essay_id, rows in rows_by_essay.items():
        node_index = _node_index_by_component_id(essay_id)
        component_scores = [_component_score(row, node_index) for row in rows]
        answers[essay_id] = {
            "id": essay_id,
            "task": "argument_quality",
            "source_dataset": SOURCE_DATASET,
            "source_url": SOURCE_URL,
            "source_file": str(path.relative_to(CORPUS_ROOT)),
            "score_scale": "normalized_0_to_1",
            "score_derivation": SCORE_DERIVATION,
            "scores": _essay_scores(component_scores),
            "component_scores": component_scores,
        }
    return answers


def extract_answers() -> dict[str, Any]:
    """Extract matched argument-quality answers for normalized essay graphs."""
    graphs = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    answers_by_id = _build_answers(QUALITY_TABLE_PATH) if QUALITY_TABLE_PATH.exists() else {}

    answers: list[dict[str, Any]] = []
    missing: list[str] = []
    matched_component_count = 0
    unmatched_component_count = 0
    for record in graphs:
        essay_id = str(record.get("id"))
        answer = answers_by_id.get(essay_id)
        if answer is None:
            missing.append(essay_id)
            continue
        for component in answer["component_scores"]:
            if component["node_idx"] is None:
                unmatched_component_count += 1
            else:
                matched_component_count += 1
        answers.append(answer)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(answers, indent=2), encoding="utf-8")
    report = {
        "graph_count": len(graphs),
        "score_file": str(QUALITY_TABLE_PATH) if QUALITY_TABLE_PATH.exists() else None,
        "score_dataset": SOURCE_DATASET,
        "answer_count": len(answers),
        "missing_count": len(missing),
        "missing": missing,
        "source_answer_count": len(answers_by_id),
        "unmatched_source_answer_count": len(
            set(answers_by_id) - {str(item.get("id")) for item in graphs}
        ),
        "component_score_count": matched_component_count + unmatched_component_count,
        "matched_component_score_count": matched_component_count,
        "unmatched_component_score_count": unmatched_component_count,
        "score_names": sorted({name for answer in answers for name in answer["scores"]}),
        "score_derivation": SCORE_DERIVATION,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(extract_answers(), indent=2))
