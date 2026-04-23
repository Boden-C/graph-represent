from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any

CORPUS_ROOT = Path(__file__).resolve().parent
REPO_ROOT = CORPUS_ROOT.parents[2]
GRAPH_PATH = CORPUS_ROOT / "graphs" / "memeargs_normalized.json"
OUTPUT_PATH = CORPUS_ROOT / "answers" / "labels.json"
REPORT_PATH = CORPUS_ROOT / "answers" / "label_match_report.json"
SEMEVAL_ZIPS = [
    REPO_ROOT / "corpus" / "SEMEVAL-2021-task6-corpus" / "data" / "training_set_task3.zip",
    REPO_ROOT / "corpus" / "SEMEVAL-2021-task6-corpus" / "data" / "dev_set_task3.zip",
    REPO_ROOT / "corpus" / "SEMEVAL-2021-task6-corpus" / "data" / "test_set_task3.zip",
]


def _load_json_from_zip(path: Path) -> tuple[str, list[dict[str, Any]]]:
    with zipfile.ZipFile(path) as archive:
        txt_names = sorted(name for name in archive.namelist() if name.endswith(".txt"))
        if not txt_names:
            raise FileNotFoundError(f"No label .txt file found in {path}")
        name = txt_names[0]
        return name, json.loads(archive.read(name).decode("utf-8"))


def _load_semeval_labels() -> dict[str, dict[str, Any]]:
    by_image: dict[str, dict[str, Any]] = {}
    for zip_path in SEMEVAL_ZIPS:
        if not zip_path.exists():
            continue
        source_name, rows = _load_json_from_zip(zip_path)
        split = source_name.split("/", 1)[0]
        for row in rows:
            image = str(row.get("image", "")).strip()
            if not image:
                continue
            by_image[image] = {
                "semeval_id": str(row.get("id", "")),
                "image_filename": image,
                "labels": list(row.get("labels") or []),
                "text": row.get("text"),
                "split": split,
                "source": str(zip_path),
            }
    return by_image


def extract_answers() -> dict[str, Any]:
    graph_records = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    labels_by_image = _load_semeval_labels()
    answers: list[dict[str, Any]] = []
    unmatched: list[dict[str, str]] = []

    for record in graph_records:
        image = str(record.get("image_filename") or "").strip()
        label_record = labels_by_image.get(image)
        if label_record is None:
            unmatched.append({"id": str(record.get("id")), "image_filename": image})
            continue
        answers.append({"id": str(record["id"]), **label_record})

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(answers, indent=2), encoding="utf-8")
    report = {
        "graph_count": len(graph_records),
        "answer_count": len(answers),
        "unmatched_count": len(unmatched),
        "unmatched": unmatched,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(extract_answers(), indent=2))
