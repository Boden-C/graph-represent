from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any

from graph_represent.types.quality import ArgumentQualitySampleResult, ArgumentQualityVariantResult

JSON_BASELINE_FORMAT = "json"
RAW_LABELS = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]


def _write_rows(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(mean(values))


def _raw_from_normalized(value: float) -> float:
    value = max(0.0, min(1.0, float(value)))
    raw = 1.0 + (3.0 * value)
    nearest = min(RAW_LABELS, key=lambda item: abs(item - raw))
    return float(nearest)


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 2 or len(xs) != len(ys):
        return None
    x_mean = mean(xs)
    y_mean = mean(ys)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True))
    x_den = math.sqrt(sum((x - x_mean) ** 2 for x in xs))
    y_den = math.sqrt(sum((y - y_mean) ** 2 for y in ys))
    if x_den == 0 or y_den == 0:
        return None
    return float(numerator / (x_den * y_den))


def _rank(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    idx = 0
    while idx < len(indexed):
        end = idx
        while end + 1 < len(indexed) and indexed[end + 1][1] == indexed[idx][1]:
            end += 1
        rank = (idx + end + 2) / 2.0
        for offset in range(idx, end + 1):
            ranks[indexed[offset][0]] = rank
        idx = end + 1
    return ranks


def _mae(predicted: list[float], gold: list[float]) -> float:
    return float(mean(abs(left - right) for left, right in zip(predicted, gold, strict=True)))


def _qwk(predicted: list[float], gold: list[float]) -> float | None:
    if len(predicted) != len(gold) or not predicted:
        return None
    labels = RAW_LABELS
    label_to_idx = {label: idx for idx, label in enumerate(labels)}
    matrix_size = len(labels)
    observed = [[0.0 for _ in range(matrix_size)] for _ in range(matrix_size)]
    hist_pred = [0.0 for _ in range(matrix_size)]
    hist_gold = [0.0 for _ in range(matrix_size)]
    for pred, target in zip(predicted, gold, strict=True):
        pred_idx = label_to_idx[pred]
        target_idx = label_to_idx[target]
        observed[pred_idx][target_idx] += 1.0
        hist_pred[pred_idx] += 1.0
        hist_gold[target_idx] += 1.0
    total = float(len(predicted))
    expected = [
        [(hist_pred[row] * hist_gold[col]) / total for col in range(matrix_size)]
        for row in range(matrix_size)
    ]
    numerator = 0.0
    denominator = 0.0
    scale = float((matrix_size - 1) ** 2)
    for row in range(matrix_size):
        for col in range(matrix_size):
            weight = ((row - col) ** 2) / scale
            numerator += weight * observed[row][col]
            denominator += weight * expected[row][col]
    if denominator == 0.0:
        return None
    return float(1.0 - (numerator / denominator))


def score_run(run_root: str | Path) -> dict[str, Any]:
    run_root = Path(run_root)
    output_root = run_root / "output"
    sample_dir = output_root / "quality_outputs"
    samples = [
        ArgumentQualitySampleResult.model_validate_json(path.read_text(encoding="utf-8"))
        for path in sorted(sample_dir.glob("*.json"))
    ]
    grouped: dict[tuple[str, str], list[ArgumentQualityVariantResult]] = defaultdict(list)
    length_chars: dict[str, list[float]] = defaultdict(list)
    length_lines: dict[str, list[float]] = defaultdict(list)
    prediction_rows: list[dict[str, Any]] = []
    for sample in samples:
        for variant in sample.variants:
            grouped[(variant.version_name, variant.input_mode)].append(variant)
            variant_key = f"{variant.version_name}::{variant.input_mode}"
            if variant.input_char_count is not None:
                length_chars[variant_key].append(float(variant.input_char_count))
            if variant.input_line_count is not None:
                length_lines[variant_key].append(float(variant.input_line_count))
            predicted_normalized = float(variant.scores.scores.get("strength_of_argument", 0.0))
            predicted_raw = _raw_from_normalized(predicted_normalized)
            gold_normalized = None
            if variant.gold_scores is not None:
                gold_normalized = variant.gold_scores.get("strength_of_argument")
            gold_raw = None
            if variant.gold_raw_scores is not None:
                gold_raw = variant.gold_raw_scores.get("strength_of_argument")
            prediction_rows.append(
                {
                    "item_id": variant.item_id,
                    "version_name": variant.version_name,
                    "graph_format": variant.input_mode,
                    "pred_strength_of_argument": round(predicted_normalized, 6),
                    "pred_strength_of_argument_raw": predicted_raw,
                    "gold_strength_of_argument": gold_normalized,
                    "gold_strength_of_argument_raw": gold_raw,
                    "rationale": variant.scores.rationale,
                }
            )

    metric_rows: list[dict[str, Any]] = []
    metric_map: dict[tuple[str, str], tuple[list[float], list[float]]] = {}
    for (version_name, graph_format), variants in sorted(grouped.items()):
        predicted_raw: list[float] = []
        gold_raw: list[float] = []
        for variant in variants:
            gold_map = variant.gold_raw_scores or {}
            if "strength_of_argument" not in gold_map:
                continue
            gold = float(gold_map["strength_of_argument"])
            pred_norm = float(variant.scores.scores.get("strength_of_argument", 0.0))
            predicted_raw.append(_raw_from_normalized(pred_norm))
            gold_raw.append(gold)
        if not predicted_raw:
            continue
        qwk = _qwk(predicted_raw, gold_raw)
        spearman = _pearson(_rank(predicted_raw), _rank(gold_raw))
        mae = _mae(predicted_raw, gold_raw)
        metric_rows.append(
            {
                "version_name": version_name,
                "graph_format": graph_format,
                "sample_count": len(predicted_raw),
                "qwk": round(qwk, 6) if qwk is not None else None,
                "mae": round(mae, 6),
                "spearman": round(spearman, 6) if spearman is not None else None,
                "qwk_delta_vs_json": None,
                "mae_delta_vs_json": None,
                "spearman_delta_vs_json": None,
                "primary_metric": "qwk",
            }
        )
        metric_map[(version_name, graph_format)] = (predicted_raw, gold_raw)

    baseline_by_version = {
        key[0]: values
        for key, values in metric_map.items()
        if key[1] == JSON_BASELINE_FORMAT
    }
    for row in metric_rows:
        baseline = baseline_by_version.get(str(row["version_name"]))
        if baseline is None or row["graph_format"] == JSON_BASELINE_FORMAT:
            continue
        predicted, gold = metric_map[(str(row["version_name"]), str(row["graph_format"]))]
        base_predicted, base_gold = baseline
        qwk = _qwk(predicted, gold)
        base_qwk = _qwk(base_predicted, base_gold)
        spearman = _pearson(_rank(predicted), _rank(gold))
        base_spearman = _pearson(_rank(base_predicted), _rank(base_gold))
        row["qwk_delta_vs_json"] = (
            round(float(qwk - base_qwk), 6) if qwk is not None and base_qwk is not None else None
        )
        row["mae_delta_vs_json"] = round(_mae(predicted, gold) - _mae(base_predicted, base_gold), 6)
        row["spearman_delta_vs_json"] = (
            round(float(spearman - base_spearman), 6)
            if spearman is not None and base_spearman is not None
            else None
        )

    length_rows: list[dict[str, Any]] = []
    for variant, char_values in sorted(length_chars.items()):
        version_name, graph_format = variant.split("::", maxsplit=1)
        line_values = length_lines.get(variant, [])
        length_rows.append(
            {
                "version_name": version_name,
                "graph_format": graph_format,
                "char_mean": round(_safe_mean(char_values) or 0.0, 6),
                "line_mean": round(_safe_mean(line_values) or 0.0, 6),
            }
        )

    best_rows = [row for row in metric_rows if row["qwk"] is not None]
    researcher_rows: list[dict[str, Any]] = []
    if best_rows:
        best = max(best_rows, key=lambda item: float(item["qwk"]))
        researcher_rows.append(
            {
                "selection": "best_qwk_format",
                "version_name": best["version_name"],
                "graph_format": best["graph_format"],
                "qwk": best["qwk"],
                "mae": best["mae"],
                "spearman": best["spearman"],
            }
        )

    raw_stats = {
        "item_count": len(samples),
        "answered_count": len(samples),
        "variant_count": sum(len(sample.variants) for sample in samples),
        "primary_metric": "qwk",
        "raw_score_scale": RAW_LABELS,
    }

    (output_root / "raw_stats.json").write_text(json.dumps(raw_stats, indent=2), encoding="utf-8")
    _write_rows(prediction_rows, output_root / "predictions.csv")
    _write_rows(metric_rows, output_root / "summary.csv")
    _write_rows(length_rows, output_root / "format_lengths.csv")
    _write_rows(researcher_rows, output_root / "researcher_summary.csv")
    return raw_stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("run_root")
    args = parser.parse_args()
    print(json.dumps(score_run(args.run_root), indent=2))
