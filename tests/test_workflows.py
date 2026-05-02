from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from graph_represent.format_suite import COMPARISON_FORMATS
from graph_represent.runner import build_parser, run_task, run_tasks


def test_runner_parser_accepts_multiple_tasks():
    parser = build_parser()
    args = parser.parse_args(
        [
            "memeargs_graph_format_comparison",
            "argument_essays_graph_format_comparison",
        ]
    )

    assert args.tasks == [
        "memeargs_graph_format_comparison",
        "argument_essays_graph_format_comparison",
    ]


def test_memeargs_workflow_runs_with_mock_ai(isolated_runner_roots, mock_ai_requests):
    del isolated_runner_roots
    call_counter = mock_ai_requests()
    run_root = run_task("memeargs_graph_format_comparison", runname="memeargs_smoke", limit=2)

    assert call_counter["count"] == 2 * len(COMPARISON_FORMATS)
    output_root = run_root / "output"
    assert (output_root / "threshold_outputs").exists()
    assert (output_root / "raw_stats.json").exists()
    assert (output_root / "optimized_thresholds.json").exists()
    rows = list(csv.DictReader((output_root / "summary.csv").read_text(encoding="utf-8").splitlines()))
    assert {row["graph_format"] for row in rows} == {item.value for item in COMPARISON_FORMATS}
    raw_stats = json.loads((output_root / "raw_stats.json").read_text(encoding="utf-8"))
    assert raw_stats["item_count"] == 2
    assert raw_stats["answered_count"] == 2


def test_argument_essay_workflow_runs_with_mock_ai(isolated_runner_roots, mock_ai_requests):
    del isolated_runner_roots
    call_counter = mock_ai_requests()
    run_root = run_task("argument_essays_graph_format_comparison", runname="essay_smoke", limit=2)

    assert call_counter["count"] == 2 * len(COMPARISON_FORMATS)
    output_root = run_root / "output"
    assert (output_root / "quality_outputs").exists()
    assert (output_root / "raw_stats.json").exists()
    assert (output_root / "predictions.csv").exists()
    raw_stats = json.loads((output_root / "raw_stats.json").read_text(encoding="utf-8"))
    assert raw_stats["item_count"] == 2
    assert raw_stats["answered_count"] == 2
    assert raw_stats["has_gold_metrics"] is True


def test_run_tasks_uses_shared_run_root(isolated_runner_roots, mock_ai_requests):
    del isolated_runner_roots
    call_counter = mock_ai_requests()

    run_roots = run_tasks(
        [
            "memeargs_graph_format_comparison",
            "argument_essays_graph_format_comparison",
        ],
        runname="combined_smoke",
        limit=1,
    )

    assert call_counter["count"] == 2 * len(COMPARISON_FORMATS)
    assert [run_root.parent.name for run_root in run_roots] == [
        "combined_smoke",
        "combined_smoke",
    ]
    assert [run_root.name for run_root in run_roots] == [
        "memeargs_graph_format_comparison",
        "argument_essays_graph_format_comparison",
    ]


def test_script_workflow_resume_skips_completed_items(isolated_runner_roots, mock_ai_requests):
    del isolated_runner_roots
    call_counter = mock_ai_requests()

    run_root = run_task("memeargs_graph_format_comparison", runname="resume_smoke", limit=1)
    assert call_counter["count"] == len(COMPARISON_FORMATS)

    resumed_root = run_task("memeargs_graph_format_comparison", runname="resume_smoke", limit=1)
    assert resumed_root == run_root
    assert call_counter["count"] == len(COMPARISON_FORMATS)


def test_inference_logs_keep_request_response_contract(isolated_runner_roots, mock_ai_requests):
    del isolated_runner_roots
    mock_ai_requests()

    run_root = run_task("argument_essays_graph_format_comparison", runname="log_smoke", limit=1)
    inference_logs = sorted((run_root / "logs").glob("*/*infer_quality__json.log"))
    assert len(inference_logs) == 1
    log_text = inference_logs[0].read_text(encoding="utf-8")

    assert "INPUT_JSON:" in log_text
    assert "OUTPUT_JSON:" in log_text
    assert "REQUEST_JSON:" in log_text
    assert "RESPONSE_JSON:" in log_text


def test_icle_workflow_runs_with_mock_ai_and_qwk_outputs(
    isolated_runner_roots,
    mock_ai_requests,
    monkeypatch,
):
    del isolated_runner_roots
    monkeypatch.setenv("GRAPH_REPRESENT_SAMPLE_SEED", "7")
    call_counter = mock_ai_requests()
    run_root = run_task("icle_graph_format_comparison", runname="icle_smoke", limit=2)

    assert call_counter["count"] == 2 * (len(COMPARISON_FORMATS) + 1)
    output_root = run_root / "output"
    assert (output_root / "quality_outputs").exists()
    assert (output_root / "raw_stats.json").exists()
    assert (output_root / "summary.csv").exists()
    assert (output_root / "run_config.json").exists()
    raw_stats = json.loads((output_root / "raw_stats.json").read_text(encoding="utf-8"))
    assert raw_stats["item_count"] == 2
    assert raw_stats["primary_metric"] == "qwk"
    summary_rows = list(
        csv.DictReader((output_root / "summary.csv").read_text(encoding="utf-8").splitlines())
    )
    assert summary_rows
    assert "qwk" in summary_rows[0]


def test_icle_workflow_fails_on_exemplar_overlap(
    isolated_runner_roots,
    mock_ai_requests,
    monkeypatch,
    tmp_path,
):
    del isolated_runner_roots
    mock_ai_requests()
    monkeypatch.delenv("GRAPH_REPRESENT_SAMPLE_SEED", raising=False)
    monkeypatch.setenv("GRAPH_REPRESENT_EXCLUDE_FEW_SHOT_IDS", "0")
    essays = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data"
            / "icle"
            / "essays"
            / "icle_essays_normalized.json"
        ).read_text(encoding="utf-8")
    )
    answers = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "data"
            / "icle"
            / "answers"
            / "quality_scores.json"
        ).read_text(encoding="utf-8")
    )
    answer_ids = {str(item["id"]) for item in answers if isinstance(item, dict)}
    first_eval_id = min(
        str(item["id"]) for item in essays if isinstance(item, dict) and str(item.get("id")) in answer_ids
    )
    overlap_manifest = tmp_path / "overlap_exemplars.json"
    overlap_manifest.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "item_ids": [first_eval_id],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("GRAPH_REPRESENT_EXEMPLARS_PATH", str(overlap_manifest))
    with pytest.raises(ValueError, match="Few-shot leak detected"):
        run_task("icle_graph_format_comparison", runname="icle_overlap", limit=1)
