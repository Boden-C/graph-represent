from __future__ import annotations

import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, pstdev
from typing import Any

CORPUS_ROOT = Path(__file__).resolve().parent
ANSWERS_PATH = CORPUS_ROOT / "answers" / "quality_scores.json"
JSON_BASELINE_FORMAT = "json"

CALCULATED_COMPONENT_SCORES = [
    "cogency_mean",
    "rhetoric_strategy_rate",
    "reasonableness_counterargument_mean",
    "reasonableness_rebuttal_mean",
]


def _summary_stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0}
    return {
        "count": len(values),
        "mean": round(mean(values), 6),
        "std": round(pstdev(values), 6),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
    }


def numeric_summary_stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "mean": 0.0, "median": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95))))
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 0:
        median = (ordered[midpoint - 1] + ordered[midpoint]) / 2.0
    else:
        median = ordered[midpoint]
    return {
        "count": len(values),
        "mean": round(sum(values) / len(values), 6),
        "median": round(float(median), 6),
        "p95": round(float(ordered[p95_index]), 6),
        "min": round(float(ordered[0]), 6),
        "max": round(float(ordered[-1]), 6),
    }


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
    return round(numerator / (x_den * y_den), 6)


def _rank(values: list[float]) -> list[float]:
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(indexed):
        j = i
        while j + 1 < len(indexed) and indexed[j + 1][1] == indexed[i][1]:
            j += 1
        rank = (i + j + 2) / 2.0
        for k in range(i, j + 1):
            ranks[indexed[k][0]] = rank
        i = j + 1
    return ranks


def _write_rows(rows: list[dict[str, Any]], path: Path) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _mae(predicted: list[float], gold: list[float]) -> float:
    return mean(abs(item - target) for item, target in zip(predicted, gold, strict=True))


def _bootstrap_ci(values: list[float], lower: float = 0.025, upper: float = 0.975) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    ordered = sorted(values)
    lower_index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * lower)))
    upper_index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * upper)))
    return float(ordered[lower_index]), float(ordered[upper_index])


def _load_gold_scores() -> dict[str, dict[str, float]]:
    payload = json.loads(ANSWERS_PATH.read_text(encoding="utf-8"))
    gold_by_id: dict[str, dict[str, float]] = {}
    for item in payload:
        if not isinstance(item, dict):
            continue
        item_id = str(item.get("id", "")).strip()
        raw_scores = item.get("scores")
        if not item_id or not isinstance(raw_scores, dict):
            continue
        normalized: dict[str, float] = {}
        for key, value in raw_scores.items():
            if isinstance(value, int | float):
                normalized[str(key)] = float(value)
        if normalized:
            gold_by_id[item_id] = normalized
    return gold_by_id


def _safe_mean(values: list[float]) -> float | None:
    if not values:
        return None
    return float(mean(values))


def _normalize_predicted_scores(raw_scores: dict[str, float]) -> dict[str, float]:
    normalized = {str(key): float(value) for key, value in raw_scores.items()}
    if "overall_quality_mean" in normalized:
        normalized["self_reported_quality"] = normalized["overall_quality_mean"]
    calculated_inputs = [
        normalized[score_name]
        for score_name in CALCULATED_COMPONENT_SCORES
        if score_name in normalized
    ]
    calculated = _safe_mean(calculated_inputs)
    if calculated is not None:
        normalized["calculated_overall_quality"] = calculated
    normalized.pop("overall_quality_mean", None)
    return normalized


def _load_samples(sample_dir: Path) -> list[dict[str, Any]]:
    return [json.loads(path.read_text(encoding="utf-8")) for path in sorted(sample_dir.glob("*.json"))]


def score_run(run_root: str | Path) -> dict[str, Any]:
    run_root = Path(run_root)
    output_root = run_root / "output"
    sample_dir = output_root / "quality_outputs"
    samples = _load_samples(sample_dir)
    gold_by_id = _load_gold_scores()

    score_values: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    metric_rows: list[dict[str, Any]] = []
    prediction_rows: list[dict[str, Any]] = []
    length_chars: dict[str, list[float]] = defaultdict(list)
    length_lines: dict[str, list[float]] = defaultdict(list)

    paired: dict[tuple[str, str, str], tuple[list[float], list[float], list[str]]] = defaultdict(
        lambda: ([], [], [])
    )
    for sample in samples:
        sample_item_id = str(sample["item_id"])
        sample_gold_scores = gold_by_id.get(sample_item_id, sample.get("gold_scores") or {})
        for variant in sample.get("variants", []):
            variant_key = f"{variant['version_name']}::{variant['input_mode']}"
            input_char_count = variant.get("input_char_count")
            input_line_count = variant.get("input_line_count")
            if input_char_count is not None:
                length_chars[variant_key].append(float(input_char_count))
            if input_line_count is not None:
                length_lines[variant_key].append(float(input_line_count))
            predicted_scores = _normalize_predicted_scores(variant["scores"]["scores"])
            for score_name, value in predicted_scores.items():
                score_values[variant_key][score_name].append(float(value))
                prediction_rows.append(
                    {
                        "item_id": sample_item_id,
                        "version_name": variant["version_name"],
                        "graph_format": variant["input_mode"],
                        "score_name": score_name,
                        "predicted": value,
                        "gold": sample_gold_scores.get(score_name, ""),
                        "input_char_count": input_char_count,
                        "input_line_count": input_line_count,
                    }
                )
                if score_name in sample_gold_scores:
                    key = (variant["version_name"], variant["input_mode"], score_name)
                    xs, ys, ids = paired[key]
                    xs.append(float(value))
                    ys.append(float(sample_gold_scores[score_name]))
                    ids.append(sample_item_id)

    for (version_name, graph_format, score_name), (predicted, gold, _) in sorted(paired.items()):
        errors = [p - g for p, g in zip(predicted, gold, strict=True)]
        metric_rows.append(
            {
                "version_name": version_name,
                "graph_format": graph_format,
                "score_name": score_name,
                "item_count": len(predicted),
                "mae": round(_mae(predicted, gold), 6),
                "rmse": round(math.sqrt(mean(item * item for item in errors)), 6),
                "mean_error": round(mean(errors), 6),
                "pearson": _pearson(predicted, gold),
                "spearman": _pearson(_rank(predicted), _rank(gold)),
            }
        )

    raw_stats = {
        "item_count": len(samples),
        "answered_count": sum(1 for sample in samples if str(sample.get("item_id", "")) in gold_by_id),
        "variant_count": sum(len(sample.get("variants", [])) for sample in samples),
        "score_stats": {
            variant: {score: _summary_stats(values) for score, values in scores.items()}
            for variant, scores in sorted(score_values.items())
        },
        "length_stats": {
            variant: {
                "char_count": numeric_summary_stats(values),
                "line_count": numeric_summary_stats(length_lines.get(variant, [])),
            }
            for variant, values in sorted(length_chars.items())
        },
        "has_gold_metrics": bool(metric_rows),
    }
    (output_root / "raw_stats.json").write_text(json.dumps(raw_stats, indent=2), encoding="utf-8")
    _write_rows(prediction_rows, output_root / "predictions.csv")
    _write_rows(metric_rows, output_root / "summary.csv")

    length_rows = []
    for variant, char_values in sorted(length_chars.items()):
        line_values = length_lines.get(variant, [])
        version_name, graph_format = variant.split("::", maxsplit=1)
        char_stats = numeric_summary_stats(char_values)
        line_stats = numeric_summary_stats(line_values)
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

    bootstrap_rows: list[dict[str, Any]] = []
    rng = random.Random(7)
    bootstrap_rounds = 1000
    metric_map = {
        (version_name, graph_format, score_name): (predicted, gold)
        for (version_name, graph_format, score_name), (predicted, gold, _) in paired.items()
    }
    target_score = "calculated_overall_quality"
    for (version_name, graph_format, score_name), (predicted, gold) in sorted(metric_map.items()):
        if graph_format == JSON_BASELINE_FORMAT or score_name != target_score:
            continue
        baseline = metric_map.get((version_name, JSON_BASELINE_FORMAT, score_name))
        if baseline is None:
            continue
        base_predicted, base_gold = baseline
        if len(predicted) != len(base_predicted) or len(gold) != len(base_gold):
            continue
        if len(predicted) < 2:
            continue
        mae_deltas: list[float] = []
        rho_deltas: list[float] = []
        for _ in range(bootstrap_rounds):
            indices = [rng.randrange(len(predicted)) for _ in range(len(predicted))]
            sample_pred = [predicted[index] for index in indices]
            sample_gold = [gold[index] for index in indices]
            base_sample_pred = [base_predicted[index] for index in indices]
            base_sample_gold = [base_gold[index] for index in indices]
            mae_deltas.append(_mae(sample_pred, sample_gold) - _mae(base_sample_pred, base_sample_gold))
            rho_value = _pearson(_rank(sample_pred), _rank(sample_gold))
            base_rho = _pearson(_rank(base_sample_pred), _rank(base_sample_gold))
            if rho_value is not None and base_rho is not None:
                rho_deltas.append(rho_value - base_rho)
        mae_ci_low, mae_ci_high = _bootstrap_ci(mae_deltas)
        rho_ci_low, rho_ci_high = _bootstrap_ci(rho_deltas)
        point_mae_delta = _mae(predicted, gold) - _mae(base_predicted, base_gold)
        point_rho_delta = (
            (_pearson(_rank(predicted), _rank(gold)) or 0.0)
            - (_pearson(_rank(base_predicted), _rank(base_gold)) or 0.0)
        )
        bootstrap_rows.extend(
            [
                {
                    "version_name": version_name,
                    "graph_format": graph_format,
                    "score_name": score_name,
                    "metric": "mae_delta_vs_json",
                    "point_delta": round(point_mae_delta, 6),
                    "ci_low": round(mae_ci_low, 6),
                    "ci_high": round(mae_ci_high, 6),
                    "sample_count": len(predicted),
                },
                {
                    "version_name": version_name,
                    "graph_format": graph_format,
                    "score_name": score_name,
                    "metric": "spearman_delta_vs_json",
                    "point_delta": round(point_rho_delta, 6),
                    "ci_low": round(rho_ci_low, 6),
                    "ci_high": round(rho_ci_high, 6),
                    "sample_count": len(predicted),
                },
            ]
        )
    _write_rows(bootstrap_rows, output_root / "bootstrap_deltas.csv")

    researcher_rows: list[dict[str, Any]] = []
    overall_rows = [
        row for row in metric_rows if row["score_name"] == "calculated_overall_quality" and row["mae"] is not None
    ]
    if overall_rows:
        best = min(overall_rows, key=lambda item: float(item["mae"]))
        researcher_rows.append(
            {
                "selection": "best_overall_quality_format",
                "version_name": best["version_name"],
                "graph_format": best["graph_format"],
                "mae": best["mae"],
                "spearman": best["spearman"],
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
