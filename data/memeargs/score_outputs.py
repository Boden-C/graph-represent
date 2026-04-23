from __future__ import annotations

import csv
import json
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from graph_represent.graph_formats import GraphTextFormat, numeric_summary_stats
from graph_represent.processors.persuasion import (
    _binary_f1,
    compute_semeval_f1,
    optimize_label_threshold,
    threshold_scores_to_labels,
)
from graph_represent.types.persuasion import (
    TECHNIQUES_TASK3,
    PersuasionThresholdSampleResult,
    PersuasionThresholdVariantResult,
)

TEMPORARY_THRESHOLDS_PATH = Path(__file__).with_name("temporary_thresholds.json")


def _summary_stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "mean": 0.0, "median": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
    return numeric_summary_stats(values)


def _write_rows(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _bootstrap_ci(values: list[float], lower: float = 0.025, upper: float = 0.975) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    ordered = sorted(values)
    lower_index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * lower)))
    upper_index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * upper)))
    return float(ordered[lower_index]), float(ordered[upper_index])


def _split_bucket(split_name: str | None) -> str:
    if split_name is None:
        return "unknown"
    value = split_name.lower()
    if "dev" in value:
        return "dev"
    if "test" in value:
        return "test"
    if "train" in value:
        return "train"
    return "other"


def _load_temporary_thresholds() -> dict[str, float] | None:
    if not TEMPORARY_THRESHOLDS_PATH.exists():
        return None
    payload = json.loads(TEMPORARY_THRESHOLDS_PATH.read_text(encoding="utf-8"))
    thresholds = payload.get("thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError(f"{TEMPORARY_THRESHOLDS_PATH} does not contain a thresholds object")
    return {str(label): float(value) for label, value in thresholds.items()}


def _label_metrics(
    *,
    variants: list[PersuasionThresholdVariantResult],
    thresholds: dict[str, float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label in TECHNIQUES_TASK3:
        tp = fp = fn = tn = 0
        for variant in variants:
            predicted = threshold_scores_to_labels(variant.scores, thresholds)
            predicted_set = set(predicted.labels)
            gold_set = set(variant.gold.labels if variant.gold is not None else [])
            in_pred = label in predicted_set
            in_gold = label in gold_set
            if in_pred and in_gold:
                tp += 1
            elif in_pred and not in_gold:
                fp += 1
            elif not in_pred and in_gold:
                fn += 1
            else:
                tn += 1
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        rows.append(
            {
                "label": label,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "tn": tn,
                "precision": round(precision, 6),
                "recall": round(recall, 6),
                "f1": round(_binary_f1(tp, fp, fn), 6),
            }
        )
    return rows


def score_run(run_root: str | Path) -> dict[str, Any]:
    run_root = Path(run_root)
    output_root = run_root / "output"
    sample_dir = output_root / "threshold_outputs"
    samples = [
        PersuasionThresholdSampleResult.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(sample_dir.glob("*.json"))
    ]

    grouped_results: dict[tuple[str, str], list[PersuasionThresholdVariantResult]] = defaultdict(list)
    scores_by_variant_label: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    gold_counts: dict[str, int] = {label: 0 for label in TECHNIQUES_TASK3}
    length_chars: dict[str, list[float]] = defaultdict(list)
    length_lines: dict[str, list[float]] = defaultdict(list)
    split_counts: dict[str, int] = defaultdict(int)

    for sample in samples:
        for variant in sample.variants:
            grouped_results[(variant.version_name, variant.input_mode)].append(variant)
            variant_key = f"{variant.version_name}::{variant.input_mode}"
            for label, score in variant.scores.scores.items():
                scores_by_variant_label[variant_key][label].append(float(score))
            if variant.gold is not None:
                for label in variant.gold.labels:
                    if label in gold_counts:
                        gold_counts[label] += 1
            if variant.input_char_count is not None:
                length_chars[variant_key].append(float(variant.input_char_count))
            if variant.input_line_count is not None:
                length_lines[variant_key].append(float(variant.input_line_count))
            split_counts[_split_bucket(variant.gold_split)] += 1

    summary_rows: list[dict[str, Any]] = []
    threshold_rows: list[dict[str, Any]] = []
    label_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    bootstrap_rows: list[dict[str, Any]] = []
    metric_points: dict[tuple[str, str], tuple[float, float]] = {}
    temporary_thresholds = _load_temporary_thresholds()
    rng = random.Random(7)
    bootstrap_rounds = 1000

    for version_name, input_mode in sorted(grouped_results):
        variants = sorted(grouped_results[(version_name, input_mode)], key=lambda item: item.item_id)
        dev_variants = [item for item in variants if _split_bucket(item.gold_split) == "dev"]
        test_variants = [item for item in variants if _split_bucket(item.gold_split) == "test"]
        tune_variants = dev_variants or variants
        eval_variants = test_variants or variants

        thresholds: dict[str, float] = {}
        label_f1: dict[str, float] = {}
        for label in TECHNIQUES_TASK3:
            label_scores = [variant.scores.scores[label] for variant in tune_variants]
            gold_binary = [
                1 if variant.gold is not None and label in set(variant.gold.labels) else 0
                for variant in tune_variants
            ]
            if temporary_thresholds is None:
                threshold, best_f1 = optimize_label_threshold(label_scores, gold_binary)
            else:
                threshold = temporary_thresholds.get(label, 0.5)
                best_f1 = _binary_f1(
                    sum(1 for score, gold in zip(label_scores, gold_binary) if score >= threshold and gold == 1),
                    sum(1 for score, gold in zip(label_scores, gold_binary) if score >= threshold and gold == 0),
                    sum(1 for score, gold in zip(label_scores, gold_binary) if score < threshold and gold == 1),
                )
            thresholds[label] = threshold
            label_f1[label] = round(best_f1, 5)
            threshold_rows.append(
                {
                    "version_name": version_name,
                    "graph_format": input_mode,
                    "label": label,
                    "threshold": round(threshold, 6),
                    "tune_f1": round(best_f1, 6),
                    "tune_count": len(tune_variants),
                    "threshold_source": "temporary" if temporary_thresholds is not None else "optimized",
                }
            )

        predicted_sets: list[list[str]] = []
        gold_sets: list[list[str]] = []
        for variant in eval_variants:
            predicted_labels = threshold_scores_to_labels(variant.scores, thresholds).labels
            gold_labels = variant.gold.labels if variant.gold is not None else []
            predicted_sets.append(predicted_labels)
            gold_sets.append(gold_labels)
            prediction_rows.append(
                {
                    "item_id": variant.item_id,
                    "version_name": version_name,
                    "graph_format": input_mode,
                    "eval_split": "test" if test_variants else "all",
                    "gold_split": variant.gold_split,
                    "predicted_labels": json.dumps(predicted_labels),
                    "gold_labels": json.dumps(gold_labels),
                    "input_char_count": variant.input_char_count,
                    "input_line_count": variant.input_line_count,
                }
            )

        macro_f1, micro_f1 = compute_semeval_f1(predicted_sets, gold_sets)
        summary_rows.append(
            {
                "version_name": version_name,
                "graph_format": input_mode,
                "micro_f1": round(micro_f1, 5),
                "macro_f1": round(macro_f1, 5),
                "item_count": len(eval_variants),
                "tune_split": "dev" if dev_variants else "all",
                "eval_split": "test" if test_variants else "all",
                "threshold_source": "temporary" if temporary_thresholds is not None else "optimized",
            }
        )
        metric_points[(version_name, input_mode)] = (micro_f1, macro_f1)
        for row in _label_metrics(variants=eval_variants, thresholds=thresholds):
            label_rows.append(
                {
                    "version_name": version_name,
                    "graph_format": input_mode,
                    "eval_split": "test" if test_variants else "all",
                    **row,
                }
            )

    for (version_name, input_mode), (micro_f1, macro_f1) in sorted(metric_points.items()):
        if input_mode == GraphTextFormat.JSON.value:
            continue
        baseline = metric_points.get((version_name, GraphTextFormat.JSON.value))
        if baseline is None:
            continue
        baseline_micro, baseline_macro = baseline
        variants = sorted(grouped_results[(version_name, input_mode)], key=lambda item: item.item_id)
        baseline_variants = sorted(
            grouped_results[(version_name, GraphTextFormat.JSON.value)], key=lambda item: item.item_id
        )
        if len(variants) != len(baseline_variants):
            continue
        deltas_micro: list[float] = []
        deltas_macro: list[float] = []
        for _ in range(bootstrap_rounds):
            indexes = [rng.randrange(len(variants)) for _ in range(len(variants))]
            sample_variants = [variants[index] for index in indexes]
            sample_baseline = [baseline_variants[index] for index in indexes]
            sample_predicted = [
                threshold_scores_to_labels(item.scores, {label: 0.5 for label in TECHNIQUES_TASK3}).labels
                for item in sample_variants
            ]
            sample_gold = [item.gold.labels if item.gold is not None else [] for item in sample_variants]
            base_predicted = [
                threshold_scores_to_labels(item.scores, {label: 0.5 for label in TECHNIQUES_TASK3}).labels
                for item in sample_baseline
            ]
            base_gold = [item.gold.labels if item.gold is not None else [] for item in sample_baseline]
            sample_macro, sample_micro = compute_semeval_f1(sample_predicted, sample_gold)
            base_macro, base_micro = compute_semeval_f1(base_predicted, base_gold)
            deltas_micro.append(sample_micro - base_micro)
            deltas_macro.append(sample_macro - base_macro)
        micro_ci_low, micro_ci_high = _bootstrap_ci(deltas_micro)
        macro_ci_low, macro_ci_high = _bootstrap_ci(deltas_macro)
        bootstrap_rows.extend(
            [
                {
                    "version_name": version_name,
                    "graph_format": input_mode,
                    "metric": "micro_f1_delta_vs_json",
                    "point_delta": round(micro_f1 - baseline_micro, 6),
                    "ci_low": round(micro_ci_low, 6),
                    "ci_high": round(micro_ci_high, 6),
                },
                {
                    "version_name": version_name,
                    "graph_format": input_mode,
                    "metric": "macro_f1_delta_vs_json",
                    "point_delta": round(macro_f1 - baseline_macro, 6),
                    "ci_low": round(macro_ci_low, 6),
                    "ci_high": round(macro_ci_high, 6),
                },
            ]
        )

    raw_stats = {
        "item_count": len(samples),
        "answered_count": sum(1 for sample in samples if sample.gold is not None),
        "variant_count": sum(len(sample.variants) for sample in samples),
        "gold_label_counts": gold_counts,
        "split_counts": dict(sorted(split_counts.items())),
        "score_stats": {
            variant: {label: _summary_stats(values) for label, values in labels.items()}
            for variant, labels in sorted(scores_by_variant_label.items())
        },
        "length_stats": {
            variant: {
                "char_count": numeric_summary_stats(values),
                "line_count": numeric_summary_stats(length_lines.get(variant, [])),
            }
            for variant, values in sorted(length_chars.items())
        },
    }
    (output_root / "raw_stats.json").write_text(json.dumps(raw_stats, indent=2), encoding="utf-8")
    _write_rows(summary_rows, output_root / "summary.csv")
    _write_rows(prediction_rows, output_root / "predictions.csv")
    _write_rows(threshold_rows, output_root / "optimized_thresholds.csv")
    (output_root / "optimized_thresholds.json").write_text(
        json.dumps(threshold_rows, indent=2), encoding="utf-8"
    )
    _write_rows(label_rows, output_root / "label_metrics.csv")
    _write_rows(bootstrap_rows, output_root / "bootstrap_deltas.csv")

    length_rows = []
    for variant, char_values in sorted(length_chars.items()):
        version_name, graph_format = variant.split("::", maxsplit=1)
        char_stats = numeric_summary_stats(char_values)
        line_stats = numeric_summary_stats(length_lines.get(variant, []))
        length_rows.append(
            {
                "version_name": version_name,
                "graph_format": graph_format,
                "char_mean": char_stats["mean"],
                "char_median": char_stats["median"],
                "char_p95": char_stats["p95"],
                "line_mean": line_stats["mean"],
                "line_median": line_stats["median"],
                "line_p95": line_stats["p95"],
            }
        )
    _write_rows(length_rows, output_root / "format_lengths.csv")

    researcher_rows: list[dict[str, Any]] = []
    if summary_rows:
        best = max(summary_rows, key=lambda item: float(item["micro_f1"]))
        researcher_rows.append(
            {
                "selection": "best_micro_f1_format",
                "version_name": best["version_name"],
                "graph_format": best["graph_format"],
                "micro_f1": best["micro_f1"],
                "macro_f1": best["macro_f1"],
                "eval_split": best["eval_split"],
            }
        )
    _write_rows(researcher_rows, output_root / "researcher_summary.csv")
    return raw_stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("run_root")
    args = parser.parse_args()
    print(json.dumps(score_run(args.run_root), indent=2))
