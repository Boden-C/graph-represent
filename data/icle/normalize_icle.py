from __future__ import annotations

import json
import re
import csv
from pathlib import Path
from statistics import mean
from typing import Any

CORPUS_ROOT = Path(__file__).resolve().parent
SOURCE_PATH = CORPUS_ROOT / "ICLEplusplus.csv"
OUTPUT_PATH = CORPUS_ROOT / "essays" / "icle_essays_normalized.json"
REPORT_PATH = CORPUS_ROOT / "essays" / "icle_essays_normalization_report.json"


def _normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    return "\n".join(lines).strip()


def _split_title_and_body(text: str) -> tuple[str | None, str]:
    normalized = _normalize_text(text)
    if not normalized:
        return None, ""
    lines = normalized.splitlines()
    first_line = lines[0].strip()
    if first_line.lower().startswith("title:"):
        title = first_line.split(":", maxsplit=1)[1].strip()
        body = "\n".join(lines[1:]).strip()
        return (title or None), body
    return None, normalized


def _paragraphs(text: str) -> list[str]:
    blocks = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    if len(blocks) > 1:
        return blocks
    return [line.strip() for line in text.splitlines() if line.strip()]


def _load_rows() -> list[dict[str, str]]:
    with SOURCE_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            {str(key).strip(): (value or "").strip() for key, value in row.items()}
            for row in reader
        ]


def normalize_icle() -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    paragraph_counts: list[int] = []
    prompt_count = 0

    for row in _load_rows():
        essay_id = str(row.get("EssayID", "")).strip()
        if not essay_id:
            continue
        essay_text = _normalize_text(str(row.get("article_body", "")))
        prompt = _normalize_text(str(row.get("prompt", ""))) or None
        paragraphs = _paragraphs(essay_text)
        if prompt:
            prompt_count += 1
        paragraph_counts.append(len(paragraphs))
        records.append(
            {
                "id": essay_id,
                "source_index": int(row["index"]) if str(row.get("index", "")).strip().isdigit() else None,
                "prompt": prompt,
                "essay": essay_text,
                "paragraphs": paragraphs,
                "source_file": str(SOURCE_PATH.relative_to(CORPUS_ROOT)),
            }
        )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")

    report = {
        "essay_path": str(OUTPUT_PATH),
        "source_csv": str(SOURCE_PATH),
        "source_row_count": len(records),
        "normalized_record_count": len(records),
        "records_with_prompt": prompt_count,
        "normalization_method": (
            "Preserve each ICLE++ row as plain text with prompt and paragraph segmentation. "
            "No argument graph structure is inferred or stored."
        ),
        "paragraph_count_summary": {
            "min": min(paragraph_counts) if paragraph_counts else 0,
            "max": max(paragraph_counts) if paragraph_counts else 0,
            "mean": round(mean(paragraph_counts), 3) if paragraph_counts else 0.0,
        },
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(normalize_icle(), indent=2))
