from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

CORPUS_ROOT = Path(__file__).resolve().parent
ESSAY_PATH = CORPUS_ROOT / "essays" / "icle_essays_normalized.json"
SCORE_PATH = CORPUS_ROOT / "ICLEplusplus.csv"
OUTPUT_PATH = CORPUS_ROOT / "answers" / "quality_scores.json"
REPORT_PATH = CORPUS_ROOT / "answers" / "score_match_report.json"
SOURCE_DATASET = "ICLE++"
SOURCE_URL = "https://github.com/samlee946/ICLE-PlusPlus"
RAW_SCORE_MIN = 1.0
RAW_SCORE_MAX = 4.0
PRIMARY_SCORE_NAME = "strength_of_argument"

SCORE_COLUMN_MAP = {
    "Overall": "overall_quality_mean",
    "Adherence to Prompt": "adherence_to_prompt",
    "Clarity of Thesis": "clarity_of_thesis",
    "Strength of Argument": "strength_of_argument",
    "Development": "development",
    "Organization": "organization",
    "Coherence": "coherence",
    "Cohesion": "cohesion",
    "Sentence Structure": "sentence_structure",
    "Vocabulary": "vocabulary",
    "Technical Quality": "technical_quality",
}

SCORE_DERIVATION = {
    score_name: f"Linear normalization of '{column_name}' from the ICLE++ 1.0-4.0 rubric onto 0.0-1.0."
    for column_name, score_name in SCORE_COLUMN_MAP.items()
}


def _normalize_score(value: str) -> float | None:
    text = (value or "").strip()
    if not text:
        return None
    raw = float(text)
    if raw < RAW_SCORE_MIN or raw > RAW_SCORE_MAX:
        raise ValueError(f"Unexpected ICLE score '{raw}'")
    return round((raw - RAW_SCORE_MIN) / (RAW_SCORE_MAX - RAW_SCORE_MIN), 6)


def _load_scores() -> dict[str, dict[str, Any]]:
    with SCORE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    scores_by_id: dict[str, dict[str, Any]] = {}
    for row in rows:
        essay_id = str(row.get("EssayID", "")).strip()
        if not essay_id:
            continue
        normalized_scores: dict[str, float] = {}
        raw_scores: dict[str, float] = {}
        for column_name, score_name in SCORE_COLUMN_MAP.items():
            value = row.get(column_name, "")
            normalized = _normalize_score(value)
            if normalized is None:
                continue
            normalized_scores[score_name] = normalized
            raw_scores[score_name] = float(value)
        if not normalized_scores:
            continue
        scores_by_id[essay_id] = {
            "id": essay_id,
            "task": "essay_quality",
            "source_dataset": SOURCE_DATASET,
            "source_url": SOURCE_URL,
            "source_file": str(SCORE_PATH.relative_to(CORPUS_ROOT)),
            "primary_score_name": PRIMARY_SCORE_NAME,
            "score_scale": "normalized_0_to_1",
            "raw_score_scale": "1_to_4",
            "score_derivation": SCORE_DERIVATION,
            "scores": normalized_scores,
            "raw_scores": raw_scores,
        }
    return scores_by_id


def extract_answers() -> dict[str, Any]:
    essays = json.loads(ESSAY_PATH.read_text(encoding="utf-8"))
    scores_by_id = _load_scores()

    answers: list[dict[str, Any]] = []
    missing: list[str] = []
    matched_ids: set[str] = set()
    for record in essays:
        essay_id = str(record.get("id", "")).strip()
        if not essay_id:
            continue
        score = scores_by_id.get(essay_id)
        if score is None:
            missing.append(essay_id)
            continue
        answers.append(score)
        matched_ids.add(essay_id)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(answers, indent=2), encoding="utf-8")
    report = {
        "essay_count": len(essays),
        "essay_file": str(ESSAY_PATH),
        "score_file": str(SCORE_PATH),
        "score_dataset": SOURCE_DATASET,
        "source_answer_count": len(scores_by_id),
        "answer_count": len(answers),
        "matched_count": len(matched_ids),
        "missing_count": len(missing),
        "primary_score_name": PRIMARY_SCORE_NAME,
        "missing": missing,
        "unmatched_source_answer_count": len(set(scores_by_id) - matched_ids),
        "unmatched_source_answer_ids_sample": sorted(set(scores_by_id) - matched_ids)[:50],
        "score_names": sorted(SCORE_COLUMN_MAP.values()),
        "score_derivation": SCORE_DERIVATION,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(extract_answers(), indent=2))
