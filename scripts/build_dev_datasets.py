from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

from pydantic import TypeAdapter

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from graph_represent.types.dataset import ArgumentGraphRecord

MAX_ITEMS = 100


def _load_records(path: Path) -> list[ArgumentGraphRecord]:
    return TypeAdapter(list[ArgumentGraphRecord]).validate_json(path.read_text(encoding="utf-8"))


def _load_answers(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return {str(item["id"]): dict(item) for item in payload}
    if isinstance(payload, dict):
        raw_items = payload.get("items", payload)
        if isinstance(raw_items, dict):
            return {str(key): dict(value) for key, value in raw_items.items()}
    raise TypeError(f"Unsupported answers format in '{path}'")


def _graph_features(record: ArgumentGraphRecord) -> dict[str, int]:
    graph = record.data.graph
    edge_count = sum(len(argument.premises) for argument in graph.arguments)
    claim_count = sum(1 for node in graph.nodes if node.type.value == "claim")
    return {
        "node_count": len(graph.nodes),
        "edge_count": edge_count,
        "claim_count": claim_count,
    }


def _spread_pick(candidates: list[dict[str, Any]], count: int, sort_keys: list[str]) -> list[dict[str, Any]]:
    if count <= 0 or not candidates:
        return []
    ordered = sorted(candidates, key=lambda item: tuple(item[key] for key in sort_keys))
    if count >= len(ordered):
        return ordered
    indexes = {
        round(position * (len(ordered) - 1) / (count - 1))
        for position in range(count)
    }
    return [ordered[index] for index in sorted(indexes)]


def _round_robin_by_label(candidates: list[dict[str, Any]], target_count: int) -> list[dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    labels = sorted({label for item in candidates for label in item["labels"]})
    by_label = {
        label: _spread_pick(
            [item for item in candidates if label in item["labels"]],
            min(target_count, len(candidates)),
            ["label_count", "node_count", "edge_count", "id"],
        )
        for label in labels
    }
    while len(selected) < target_count:
        changed = False
        for label in labels:
            while by_label[label] and by_label[label][0]["id"] in selected:
                by_label[label].pop(0)
            if not by_label[label]:
                continue
            item = by_label[label].pop(0)
            selected[item["id"]] = item
            changed = True
            if len(selected) >= target_count:
                break
        if not changed:
            break
    if len(selected) < target_count:
        for item in _spread_pick(candidates, target_count, ["node_count", "edge_count", "id"]):
            selected[item["id"]] = item
            if len(selected) >= target_count:
                break
    return list(selected.values())


def _interleave_by_field(candidates: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    buckets = {
        value: sorted(
            [item for item in candidates if item[field] == value],
            key=lambda item: (item["node_count"], item["edge_count"], item["id"]),
        )
        for value in sorted({item[field] for item in candidates})
    }
    ordered: list[dict[str, Any]] = []
    while any(buckets.values()):
        for value in sorted(buckets):
            if buckets[value]:
                ordered.append(buckets[value].pop(0))
    return ordered


def _quality_bucket(value: float, bucket_count: int = 10) -> int:
    return max(0, min(bucket_count - 1, int(value * bucket_count)))


def _write_manifest(path: Path, manifest: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")


def build_memeargs_dev_set() -> dict[str, Any]:
    graph_path = REPO_ROOT / "data" / "memeargs" / "graphs" / "memeargs_normalized.json"
    answers_path = REPO_ROOT / "data" / "memeargs" / "answers" / "labels.json"
    answers = _load_answers(answers_path)
    candidates: list[dict[str, Any]] = []
    for record in _load_records(graph_path):
        answer = answers.get(record.id)
        if answer is None:
            continue
        features = _graph_features(record)
        labels = sorted(str(label) for label in answer.get("labels", []))
        candidates.append(
            {
                "id": record.id,
                "split": str(answer.get("split", "unknown")),
                "labels": labels,
                "label_count": len(labels),
                **features,
            }
        )

    dev_candidates = [item for item in candidates if item["split"] == "dev_set_task3_labeled"]
    training_candidates = [item for item in candidates if item["split"] == "training_set_task3"]
    selected = {item["id"]: item for item in dev_candidates}
    for item in _round_robin_by_label(training_candidates, MAX_ITEMS - len(selected)):
        selected[item["id"]] = item
    selected_items = _round_robin_by_label(list(selected.values()), MAX_ITEMS)[:MAX_ITEMS]
    label_counts = Counter(label for item in selected_items for label in item["labels"])
    split_counts = Counter(item["split"] for item in selected_items)
    return {
        "schema_version": 1,
        "name": "dev_set",
        "corpus": "memeargs",
        "description": "Representative development subset. Includes all local SemEval Task 3 dev items, then fills to 100 from training items by label and graph-size diversity.",
        "source_graph_path": "data/memeargs/graphs/memeargs_normalized.json",
        "source_answers_path": "data/memeargs/answers/labels.json",
        "max_items": MAX_ITEMS,
        "source_counts": {
            "graphs": len(_load_records(graph_path)),
            "answered": len(candidates),
            "splits": dict(sorted(Counter(item["split"] for item in candidates).items())),
        },
        "selected_counts": {
            "items": len(selected_items),
            "splits": dict(sorted(split_counts.items())),
            "labels": dict(sorted(label_counts.items())),
        },
        "feature_summary": {
            "node_count_mean": round(mean(item["node_count"] for item in selected_items), 3),
            "edge_count_mean": round(mean(item["edge_count"] for item in selected_items), 3),
            "label_count_mean": round(mean(item["label_count"] for item in selected_items), 3),
        },
        "item_ids": [item["id"] for item in selected_items],
        "items": selected_items,
    }


def build_argument_essays_dev_set() -> dict[str, Any]:
    graph_path = REPO_ROOT / "data" / "argument_essays" / "graphs" / "essays_normalized.json"
    answers_path = REPO_ROOT / "data" / "argument_essays" / "answers" / "quality_scores.json"
    answers = _load_answers(answers_path)
    candidates: list[dict[str, Any]] = []
    for record in _load_records(graph_path):
        answer = answers.get(record.id)
        if answer is None:
            continue
        scores = answer.get("scores", {})
        overall = float(scores["overall_quality_mean"])
        features = _graph_features(record)
        candidates.append(
            {
                "id": record.id,
                "overall_quality_mean": round(overall, 6),
                "quality_bucket": _quality_bucket(overall),
                **features,
            }
        )

    selected: dict[str, dict[str, Any]] = {}
    for bucket in range(10):
        bucket_items = [item for item in candidates if item["quality_bucket"] == bucket]
        for item in _spread_pick(bucket_items, 10, ["node_count", "edge_count", "id"]):
            selected[item["id"]] = item
    if len(selected) < MAX_ITEMS:
        for item in _spread_pick(candidates, MAX_ITEMS, ["node_count", "edge_count", "id"]):
            selected[item["id"]] = item
            if len(selected) >= MAX_ITEMS:
                break
    selected_items = _interleave_by_field(list(selected.values()), "quality_bucket")[:MAX_ITEMS]
    quality_counts = Counter(str(item["quality_bucket"]) for item in selected_items)
    return {
        "schema_version": 1,
        "name": "dev_set",
        "corpus": "argument_essays",
        "description": "Representative development subset selected across overall-quality buckets and graph-size diversity.",
        "source_graph_path": "data/argument_essays/graphs/essays_normalized.json",
        "source_answers_path": "data/argument_essays/answers/quality_scores.json",
        "max_items": MAX_ITEMS,
        "source_counts": {
            "graphs": len(_load_records(graph_path)),
            "answered": len(candidates),
        },
        "selected_counts": {
            "items": len(selected_items),
            "quality_buckets": dict(sorted(quality_counts.items())),
        },
        "feature_summary": {
            "node_count_mean": round(mean(item["node_count"] for item in selected_items), 3),
            "edge_count_mean": round(mean(item["edge_count"] for item in selected_items), 3),
            "overall_quality_mean": round(mean(item["overall_quality_mean"] for item in selected_items), 3),
        },
        "item_ids": [item["id"] for item in selected_items],
        "items": selected_items,
    }


def main() -> None:
    manifests = {
        REPO_ROOT / "data" / "memeargs" / "datasets" / "dev_set.json": build_memeargs_dev_set(),
        REPO_ROOT / "data" / "argument_essays" / "datasets" / "dev_set.json": build_argument_essays_dev_set(),
    }
    for path, manifest in manifests.items():
        _write_manifest(path, manifest)
        print(f"Wrote {path.relative_to(REPO_ROOT)} ({len(manifest['item_ids'])} items)")


if __name__ == "__main__":
    main()
