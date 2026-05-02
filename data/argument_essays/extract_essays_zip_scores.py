from __future__ import annotations

import csv
import json
import re
import zipfile
from pathlib import Path
from statistics import mean

CORPUS_ROOT = Path(__file__).resolve().parent
ZIP_PATH = CORPUS_ROOT / "raw" / "essays.zip"
CSV_OUTPUT_PATH = CORPUS_ROOT / "answers" / "essays_zip_scores.csv"
REPORT_OUTPUT_PATH = CORPUS_ROOT / "answers" / "essays_zip_scores_report.json"

NUMERIC_SCORE_NAMES = [
    "persuasiveness",
    "strength",
    "eloquence",
    "relevance",
    "specificity",
    "evidence",
]
BOOLEAN_SCORE_NAMES = ["logos", "ethos", "pathos"]
ATTRIBUTE_NAMES = {
    "Persuasiveness": "persuasiveness",
    "Strength": "strength",
    "Eloquence": "eloquence",
    "Relevance": "relevance",
    "Specificity": "specificity",
    "Evidence": "evidence",
    "Logos": "logos",
    "Ethos": "ethos",
    "Pathos": "pathos",
}
ATTRIBUTE_LINE_RE = re.compile(r"^A\d+\t(\w+)\s+T\d+\s+(.*)$")
NUMERIC_MIN = 1.0
NUMERIC_MAX = 6.0


def _normalized_numeric(value: float) -> float:
    return round((value - NUMERIC_MIN) / (NUMERIC_MAX - NUMERIC_MIN), 6)


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return round(mean(values), 6)


def _iter_ann_members(archive: zipfile.ZipFile) -> list[str]:
    return sorted(
        name
        for name in archive.namelist()
        if name.lower().endswith(".ann") and "/__macosx/" not in name.lower()
    )


def _parse_scores(text: str) -> dict[str, list[float]]:
    collected = {name: [] for name in [*NUMERIC_SCORE_NAMES, *BOOLEAN_SCORE_NAMES]}
    for line in text.splitlines():
        match = ATTRIBUTE_LINE_RE.match(line)
        if match is None:
            continue
        raw_name, raw_value = match.groups()
        score_name = ATTRIBUTE_NAMES.get(raw_name)
        if score_name is None:
            continue
        value = raw_value.strip()
        if score_name in NUMERIC_SCORE_NAMES:
            if value.isdigit():
                collected[score_name].append(float(value))
            continue
        if value == "yes":
            collected[score_name].append(1.0)
        elif value == "no":
            collected[score_name].append(0.0)
    return collected


def _row_for_essay(essay_id: str, scores: dict[str, list[float]]) -> dict[str, object]:
    row: dict[str, object] = {
        "id": essay_id,
        "source": str(ZIP_PATH.relative_to(CORPUS_ROOT)),
    }

    numeric_means: list[float] = []
    for score_name in NUMERIC_SCORE_NAMES:
        raw_mean = _safe_mean(scores[score_name])
        row[f"{score_name}_count"] = len(scores[score_name])
        row[f"{score_name}_mean_raw"] = raw_mean if raw_mean is not None else ""
        row[f"{score_name}_mean_norm"] = (
            _normalized_numeric(raw_mean) if raw_mean is not None else ""
        )
        if raw_mean is not None:
            numeric_means.append(raw_mean)

    for score_name in BOOLEAN_SCORE_NAMES:
        raw_mean = _safe_mean(scores[score_name])
        row[f"{score_name}_count"] = len(scores[score_name])
        row[f"{score_name}_rate"] = raw_mean if raw_mean is not None else ""

    overall_raw = _safe_mean(numeric_means)
    row["overall_quality_mean_raw"] = overall_raw if overall_raw is not None else ""
    row["overall_quality_mean_norm"] = (
        _normalized_numeric(overall_raw) if overall_raw is not None else ""
    )
    row["annotated_component_count"] = max(len(values) for values in scores.values())
    return row


def extract_scores() -> dict[str, object]:
    with zipfile.ZipFile(ZIP_PATH) as archive:
        rows = []
        for member_name in _iter_ann_members(archive):
            essay_id = Path(member_name).stem
            text = archive.read(member_name).decode("utf-8")
            rows.append(_row_for_essay(essay_id, _parse_scores(text)))

    rows.sort(key=lambda item: str(item["id"]))
    CSV_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with CSV_OUTPUT_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)

    report = {
        "source_zip": str(ZIP_PATH),
        "essay_count": len(rows),
        "numeric_score_names": NUMERIC_SCORE_NAMES,
        "boolean_score_names": BOOLEAN_SCORE_NAMES,
        "numeric_scale": {"min": NUMERIC_MIN, "max": NUMERIC_MAX},
        "output_csv": str(CSV_OUTPUT_PATH),
        "missing_strength_essays": [
            str(row["id"]) for row in rows if row.get("strength_count", 0) == 0
        ],
    }
    REPORT_OUTPUT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(extract_scores(), indent=2))
