from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any
from xml.sax.saxutils import escape

from graph_represent.types.quality import ArgumentQualitySampleResult, ArgumentQualityVariantResult

JSON_BASELINE_FORMAT = "json"
RAW_LABELS = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]

FORMAT_COLORS = [
    "#0f766e",
    "#2563eb",
    "#7c3aed",
    "#db2777",
    "#ea580c",
    "#16a34a",
    "#111827",
]

# Middle-sensitive bins: tighten intervals around the center so
# values near 0.6-0.7 separate more strongly (e.g., 0.6->2.5, 0.7->3.0).
NORMALIZED_TO_RAW_BINS: list[tuple[float, float]] = [
    (0.15, 1.0),
    (0.32, 1.5),
    (0.50, 2.0),
    (0.62, 2.5),
    (0.74, 3.0),
    (0.86, 3.5),
    (1.0, 4.0),
]

BIN_LABELS = RAW_LABELS


def _load_predictions_for_plot(predictions_path: Path) -> tuple[list[str], dict[str, list[float]], list[float]]:
    """Load prediction data for cumulative QWK plot."""
    with predictions_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if not rows:
        return [], {}, []

    item_order = sorted({row["item_id"] for row in rows})
    formats = sorted({row["graph_format"] for row in rows})

    by_item_and_format: dict[tuple[str, str], float] = {}
    gold_by_item: dict[str, float] = {}
    for row in rows:
        item_id = row["item_id"]
        graph_format = row["graph_format"]
        by_item_and_format[(item_id, graph_format)] = float(row["pred_strength_of_argument_raw"])
        gold_by_item[item_id] = float(row["gold_strength_of_argument_raw"])

    series: dict[str, list[float]] = {}
    for graph_format in formats:
        series[graph_format] = [by_item_and_format[(item_id, graph_format)] for item_id in item_order]

    gold_series = [gold_by_item[item_id] for item_id in item_order]
    return formats, series, gold_series


def _cumulative_qwk_for_plot(values: list[float], gold: list[float]) -> list[float | None]:
    """Calculate cumulative QWK values."""
    qwk_values: list[float | None] = []
    for end in range(1, len(values) + 1):
        qwk_val = _qwk(values[:end], gold[:end])
        qwk_values.append(qwk_val)
    return qwk_values


def _segment_polylines(points: list[tuple[float, float | None]]) -> list[list[tuple[float, float]]]:
    """Segment polylines by None values."""
    segments: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    for x, y in points:
        if y is None:
            if current:
                segments.append(current)
                current = []
            continue
        current.append((x, y))
    if current:
        segments.append(current)
    return segments


def _svg_polyline(points: list[tuple[float, float]], color: str, width: float = 1.8) -> str:
    """Generate SVG polyline element."""
    segments = [f"{x:.1f},{y:.1f}" for x, y in points]
    return (
        f'<polyline fill="none" stroke="{color}" stroke-width="{width}" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{" ".join(segments)}" />'
    )


def _generate_cumulative_qwk_svg(predictions_path: Path) -> str:
    """Generate SVG plot of cumulative QWK by graph format."""
    formats, series, gold_series = _load_predictions_for_plot(predictions_path)
    
    if not formats or not series:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="400"><text x="50" y="200">No data available</text></svg>'
    
    qwk_series = {graph_format: _cumulative_qwk_for_plot(values, gold_series) for graph_format, values in series.items()}

    width = 1800
    height = 900
    margin_left = 90
    margin_right = 40
    margin_top = 70
    margin_bottom = 120
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    y_min = -1.0
    y_max = 1.0
    item_count = len(gold_series)

    def x_scale(index: int) -> float:
        if item_count <= 1:
            return margin_left + plot_width / 2.0
        return margin_left + ((index - 1) / (item_count - 1)) * plot_width

    def y_scale(value: float) -> float:
        return margin_top + (y_max - value) / (y_max - y_min) * plot_height

    axis_lines = [
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" stroke="#111827" stroke-width="1.4" />',
        f'<line x1="{margin_left}" y1="{margin_top + plot_height}" x2="{margin_left + plot_width}" y2="{margin_top + plot_height}" stroke="#111827" stroke-width="1.4" />',
    ]

    grid_lines: list[str] = []
    for tick in [1.0, 0.5, 0.0, -0.5, -1.0]:
        y = y_scale(tick)
        stroke = "#cbd5e1" if tick == 0.0 else "#e5e7eb"
        grid_lines.append(
            f'<line x1="{margin_left}" y1="{y:.1f}" x2="{margin_left + plot_width}" y2="{y:.1f}" stroke="{stroke}" stroke-width="1" />'
        )
        grid_lines.append(
            f'<text x="{margin_left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="13" fill="#374151">{tick:.1f}</text>'
        )

    step = max(1, item_count // 24)
    x_ticks: list[str] = []
    for index in range(1, item_count + 1):
        if index == 1 or index == item_count or (index - 1) % step == 0:
            x = x_scale(index)
            x_ticks.append(
                f'<line x1="{x:.1f}" y1="{margin_top + plot_height}" x2="{x:.1f}" y2="{margin_top + plot_height + 7}" stroke="#111827" stroke-width="1" />'
            )
            x_ticks.append(
                f'<text x="{x:.1f}" y="{margin_top + plot_height + 24}" text-anchor="end" font-size="11" fill="#374151" transform="rotate(45 {x:.1f} {margin_top + plot_height + 24})">{index}</text>'
            )

    legend_entries: list[str] = []
    legend_x = margin_left
    legend_y = height - 48
    for idx, name in enumerate(formats):
        color = FORMAT_COLORS[idx % len(FORMAT_COLORS)]
        x = legend_x + (idx * 245)
        legend_entries.append(
            f'<line x1="{x}" y1="{legend_y}" x2="{x + 26}" y2="{legend_y}" stroke="{color}" stroke-width="3" />'
        )
        legend_entries.append(
            f'<text x="{x + 34}" y="{legend_y + 5}" font-size="14" fill="#111827">{escape(name)}</text>'
        )

    plotted: list[str] = []
    for idx, graph_format in enumerate(formats):
        points = [(x_scale(index), y_scale(value) if value is not None else None) for index, value in enumerate(qwk_series[graph_format], start=1)]
        for segment in _segment_polylines(points):
            plotted.append(_svg_polyline(segment, FORMAT_COLORS[idx % len(FORMAT_COLORS)], 2.0))

    title = "ICLE cumulative QWK by graph format"
    subtitle = f"Prefix QWK over {item_count} items, using raw 1.0-4.0 scores"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
  <rect width="100%" height="100%" fill="#ffffff" />
  <text x="{margin_left}" y="34" font-size="26" font-weight="700" fill="#111827">{escape(title)}</text>
  <text x="{margin_left}" y="56" font-size="14" fill="#4b5563">{escape(subtitle)}</text>
  {''.join(grid_lines)}
  {''.join(axis_lines)}
  <text x="20" y="{margin_top + plot_height / 2:.1f}" font-size="14" fill="#111827" transform="rotate(-90 20 {margin_top + plot_height / 2:.1f})">cumulative QWK</text>
  <text x="{margin_left + plot_width / 2:.1f}" y="{height - 24}" text-anchor="middle" font-size="14" fill="#111827">items scored</text>
  {''.join(x_ticks)}
  {''.join(plotted)}
  {''.join(legend_entries)}
</svg>
"""


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


def _raw_from_normalized_with_bins(value: float, bins: list[tuple[float, float]]) -> float:
    numeric = float(value)

    # Accept accidental raw-scale outputs directly (e.g., 2.5 or 3.0).
    if 1.0 <= numeric <= 4.0:
        return float(min(RAW_LABELS, key=lambda item: abs(item - numeric)))

    normalized = max(0.0, min(1.0, numeric))
    for upper_bound, label in bins:
        if normalized <= upper_bound:
            return float(label)
    return 4.0


def _raw_from_normalized(value: float) -> float:
    return _raw_from_normalized_with_bins(value, NORMALIZED_TO_RAW_BINS)


def _qwk_for_bins(
    predicted_normalized: list[float],
    gold_raw: list[float],
    bins: list[tuple[float, float]],
) -> float:
    predicted_raw = [_raw_from_normalized_with_bins(value, bins) for value in predicted_normalized]
    score = _qwk(predicted_raw, gold_raw)
    return float(score if score is not None else -1.0)


def _candidate_thresholds(predicted_normalized: list[float]) -> list[float]:
    candidates = {
        0.0,
        1.0,
        *[upper for upper, _ in NORMALIZED_TO_RAW_BINS[:-1]],
    }
    for value in predicted_normalized:
        numeric = float(value)
        if 1.0 <= numeric <= 4.0:
            continue
        candidates.add(max(0.0, min(1.0, numeric)))
    return sorted(candidates)


def _optimize_bins(predicted_normalized: list[float], gold_raw: list[float]) -> list[tuple[float, float]]:
    if not predicted_normalized:
        return list(NORMALIZED_TO_RAW_BINS)

    thresholds = [upper for upper, _ in NORMALIZED_TO_RAW_BINS[:-1]]
    candidates = _candidate_thresholds(predicted_normalized)

    current_bins = [
        (thresholds[index], BIN_LABELS[index])
        for index in range(len(BIN_LABELS) - 1)
    ] + [(1.0, BIN_LABELS[-1])]
    best_score = _qwk_for_bins(predicted_normalized, gold_raw, current_bins)

    for _ in range(8):
        improved = False
        for index in range(len(thresholds)):
            lower = thresholds[index - 1] if index > 0 else 0.0
            upper = thresholds[index + 1] if index < (len(thresholds) - 1) else 1.0
            best_threshold = thresholds[index]

            for candidate in candidates:
                if candidate < lower or candidate > upper:
                    continue
                trial = list(thresholds)
                trial[index] = candidate
                trial_bins = [
                    (trial[idx], BIN_LABELS[idx])
                    for idx in range(len(BIN_LABELS) - 1)
                ] + [(1.0, BIN_LABELS[-1])]
                score = _qwk_for_bins(predicted_normalized, gold_raw, trial_bins)
                if score > best_score + 1e-12:
                    best_score = score
                    best_threshold = candidate

            if best_threshold != thresholds[index]:
                thresholds[index] = best_threshold
                improved = True

        if not improved:
            break

    return [
        (thresholds[index], BIN_LABELS[index])
        for index in range(len(BIN_LABELS) - 1)
    ] + [(1.0, BIN_LABELS[-1])]


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


def score_run(run_root: str | Path, *, optimize_thresholds: bool = False) -> dict[str, Any]:
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
    thresholds_by_variant: dict[tuple[str, str], list[tuple[float, float]]] = {}
    threshold_rows: list[dict[str, Any]] = []
    for sample in samples:
        for variant in sample.variants:
            grouped[(variant.version_name, variant.input_mode)].append(variant)
            variant_key = f"{variant.version_name}::{variant.input_mode}"
            if variant.input_char_count is not None:
                length_chars[variant_key].append(float(variant.input_char_count))
            if variant.input_line_count is not None:
                length_lines[variant_key].append(float(variant.input_line_count))

    metric_rows: list[dict[str, Any]] = []
    metric_map: dict[tuple[str, str], tuple[list[float], list[float]]] = {}
    for (version_name, graph_format), variants in sorted(grouped.items()):
        predicted_raw: list[float] = []
        gold_raw: list[float] = []
        pred_normalized: list[float] = []
        for variant in variants:
            gold_map = variant.gold_raw_scores or {}
            if "strength_of_argument" not in gold_map:
                continue
            gold = float(gold_map["strength_of_argument"])
            pred_norm = float(variant.scores.scores.get("strength_of_argument", 0.0))
            pred_normalized.append(pred_norm)
            gold_raw.append(gold)
        if not pred_normalized:
            continue
        bins = _optimize_bins(pred_normalized, gold_raw) if optimize_thresholds else list(NORMALIZED_TO_RAW_BINS)
        thresholds_by_variant[(version_name, graph_format)] = bins
        predicted_raw = [_raw_from_normalized_with_bins(value, bins) for value in pred_normalized]
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
        threshold_rows.append(
            {
                "version_name": version_name,
                "graph_format": graph_format,
                "threshold_1_0": bins[0][0],
                "threshold_1_5": bins[1][0],
                "threshold_2_0": bins[2][0],
                "threshold_2_5": bins[3][0],
                "threshold_3_0": bins[4][0],
                "threshold_3_5": bins[5][0],
                "threshold_source": "optimized" if optimize_thresholds else "fixed",
            }
        )

    for sample in samples:
        for variant in sample.variants:
            predicted_normalized = float(variant.scores.scores.get("strength_of_argument", 0.0))
            bins = thresholds_by_variant.get(
                (variant.version_name, variant.input_mode),
                list(NORMALIZED_TO_RAW_BINS),
            )
            predicted_raw = _raw_from_normalized_with_bins(predicted_normalized, bins)
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
                }
            )

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



    raw_stats = {
        "item_count": len(samples),
        "answered_count": len(samples),
        "variant_count": sum(len(sample.variants) for sample in samples),
        "primary_metric": "qwk",
        "threshold_source": "optimized" if optimize_thresholds else "fixed",
        "raw_score_scale": RAW_LABELS,
    }

    (output_root / "raw_stats.json").write_text(json.dumps(raw_stats, indent=2), encoding="utf-8")
    _write_rows(prediction_rows, output_root / "predictions.csv")
    _write_rows(metric_rows, output_root / "summary.csv")
    _write_rows(length_rows, output_root / "format_lengths.csv")
    _write_rows(threshold_rows, output_root / "optimized_thresholds.csv")
    (output_root / "optimized_thresholds.json").write_text(
        json.dumps(
            {
                "threshold_source": "optimized" if optimize_thresholds else "fixed",
                "thresholds": threshold_rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    
    # Generate cumulative QWK plot SVG
    predictions_csv = output_root / "predictions.csv"
    if predictions_csv.exists():
        svg_content = _generate_cumulative_qwk_svg(predictions_csv)
        (output_root / "item_cumulative_qwk_plot.svg").write_text(svg_content, encoding="utf-8")
    
    return raw_stats


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("run_root")
    parser.add_argument("--optimize-thresholds", action="store_true")
    args = parser.parse_args()
    print(json.dumps(score_run(args.run_root, optimize_thresholds=args.optimize_thresholds), indent=2))
