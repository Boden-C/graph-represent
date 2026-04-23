from __future__ import annotations

import csv
import json
from pathlib import Path

from graph_represent.format_suite import COMPARISON_FORMATS
from graph_represent.runner import run_task


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
