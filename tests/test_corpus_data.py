from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from graph_represent.dataloaders.corpus_graphs import CorpusGraphDataLoader
from graph_represent.graph_formats import GraphTextFormat, canonical_graph_payload, parse_graph, render_graph

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_memeargs_answers_extract_and_match_all_items():
    module = _load_module(REPO_ROOT / "data" / "memeargs" / "extract_answers.py", "memeargs_extract")
    report = module.extract_answers()
    assert report["graph_count"] == 466
    assert report["answer_count"] == 466
    assert report["unmatched_count"] == 0


def test_argument_essay_answer_extraction_matches_quality_scores():
    module = _load_module(
        REPO_ROOT / "data" / "argument_essays" / "extract_answers.py",
        "argument_essays_extract",
    )
    report = module.extract_answers()
    assert report["graph_count"] == 402
    assert report["answer_count"] == 400
    assert report["missing"] == ["essay212", "essay213"]
    assert report["component_score_count"] == 1902
    assert report["matched_component_score_count"] == 1902
    assert report["unmatched_component_score_count"] == 0
    payload = json.loads(
        (REPO_ROOT / "data" / "argument_essays" / "answers" / "quality_scores.json").read_text(
            encoding="utf-8"
        )
    )
    assert len(payload) == 400
    assert payload[0]["id"] == "essay001"
    assert "cogency_mean" in payload[0]["scores"]
    assert payload[0]["component_scores"][0]["node_idx"] is not None


def test_icle_answer_extraction_matches_text_release():
    normalize_module = _load_module(REPO_ROOT / "data" / "icle" / "normalize_icle.py", "icle_normalize")
    normalize_report = normalize_module.normalize_icle()
    assert normalize_report["normalized_record_count"] == 1006

    extract_module = _load_module(REPO_ROOT / "data" / "icle" / "extract_answers.py", "icle_extract")
    report = extract_module.extract_answers()
    assert report["essay_count"] == 1006
    assert report["source_answer_count"] == 1006
    assert report["answer_count"] == 1006
    assert report["missing_count"] == 0
    assert report["primary_score_name"] == "strength_of_argument"

    essays = json.loads(
        (REPO_ROOT / "data" / "icle" / "essays" / "icle_essays_normalized.json").read_text(encoding="utf-8")
    )
    assert len(essays) == 1006
    assert essays[0]["prompt"] is not None
    assert essays[0]["paragraphs"]

    payload = json.loads(
        (REPO_ROOT / "data" / "icle" / "answers" / "quality_scores.json").read_text(encoding="utf-8")
    )
    assert len(payload) == 1006
    assert "strength_of_argument" in payload[0]["scores"]
    assert "raw_scores" in payload[0]


def test_corpus_loader_reads_graphs_and_labels():
    loader = CorpusGraphDataLoader(
        corpus="memeargs",
        graph_path=REPO_ROOT / "data" / "memeargs" / "graphs" / "memeargs_normalized.json",
        answers_path=REPO_ROOT / "data" / "memeargs" / "answers" / "labels.json",
    )
    item = next(iter(loader.iter_items(limit=1)))
    assert item.graph.nodes
    assert item.gold is not None
    assert isinstance(item.gold.get("labels"), list)


def test_corpus_loader_filters_by_dataset_manifest():
    dataset_path = REPO_ROOT / "data" / "memeargs" / "datasets" / "dev_set.json"
    manifest = json.loads(dataset_path.read_text(encoding="utf-8"))
    loader = CorpusGraphDataLoader(
        corpus="memeargs",
        graph_path=REPO_ROOT / "data" / "memeargs" / "graphs" / "memeargs_normalized.json",
        answers_path=REPO_ROOT / "data" / "memeargs" / "answers" / "labels.json",
        dataset_path=dataset_path,
    )
    items = list(loader.iter_items())
    assert len(items) == 100
    assert {item.id for item in items} == set(manifest["item_ids"])
    assert all(item.gold is not None for item in items)


def test_graph_formats_round_trip_for_essay_graph():
    loader = CorpusGraphDataLoader(
        corpus="argument_essays",
        graph_path=REPO_ROOT / "data" / "argument_essays" / "graphs" / "essays_normalized.json",
    )
    graph = next(iter(loader.iter_items(limit=1))).graph
    expected = canonical_graph_payload(graph)
    for format_name in GraphTextFormat:
        rendered = render_graph(graph, format_name)
        parsed = parse_graph(rendered, format_name)
        assert canonical_graph_payload(parsed) == expected


def test_icle_few_shot_manifest_matches_raw_score_extremes():
    answers = json.loads(
        (REPO_ROOT / "data" / "icle" / "answers" / "quality_scores.json").read_text(encoding="utf-8")
    )
    exemplar_manifest = json.loads(
        (REPO_ROOT / "data" / "icle" / "datasets" / "few_shot_exemplars.json").read_text(encoding="utf-8")
    )
    answers_by_id = {str(item["id"]): item for item in answers if isinstance(item, dict)}
    exemplar_ids = [str(item) for item in exemplar_manifest["item_ids"]]

    assert exemplar_ids == ["CZPR2001", "BGSU1012"]
    raw_values = [
        float(item["raw_scores"]["strength_of_argument"])
        for item in answers
        if isinstance(item, dict) and isinstance(item.get("raw_scores"), dict)
    ]
    low_id, high_id = exemplar_ids
    assert float(answers_by_id[low_id]["raw_scores"]["strength_of_argument"]) == min(raw_values)
    assert float(answers_by_id[high_id]["raw_scores"]["strength_of_argument"]) == max(raw_values)
