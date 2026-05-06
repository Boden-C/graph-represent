#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
from pathlib import Path
from xml.sax.saxutils import escape


FORMAT_COLORS = [
    "#0f766e",
    "#2563eb",
    "#7c3aed",
    "#db2777",
    "#ea580c",
    "#16a34a",
    "#111827",
]


def _load_predictions(predictions_path: Path) -> tuple[list[str], list[str], dict[str, list[float]], list[float]]:
    with predictions_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)

    if not rows:
        raise ValueError(f"No rows found in {predictions_path}")

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
    return item_order, formats, series, gold_series


def _cumulative_mean(values: list[float]) -> list[float]:
    running_total = 0.0
    cumulative: list[float] = []
    for index, value in enumerate(values, start=1):
        running_total += value
        cumulative.append(running_total / index)
    return cumulative


def _svg_line(points: list[tuple[float, float]], color: str, width: float = 1.8) -> str:
    segments = [f"{x:.1f},{y:.1f}" for x, y in points]
    return (
        f'<polyline fill="none" stroke="{color}" stroke-width="{width}" '
        f'stroke-linejoin="round" stroke-linecap="round" points="{" ".join(segments)}" />'
    )


def _render_svg(run_root: Path) -> str:
    predictions_path = run_root / "output" / "predictions.csv"
    item_order, formats, series, gold_series = _load_predictions(predictions_path)
    cumulative_series = {graph_format: _cumulative_mean(values) for graph_format, values in series.items()}
    cumulative_gold = _cumulative_mean(gold_series)

    width = 1800
    height = 900
    margin_left = 90
    margin_right = 40
    margin_top = 70
    margin_bottom = 120
    plot_width = width - margin_left - margin_right
    plot_height = height - margin_top - margin_bottom
    x_min = 1
    x_max = max(1, len(item_order))
    y_min = 1.0
    y_max = 4.0

    def x_scale(index: int) -> float:
        if x_max == x_min:
            return margin_left + plot_width / 2.0
        return margin_left + ((index - x_min) / (x_max - x_min)) * plot_width

    def y_scale(value: float) -> float:
        return margin_top + (y_max - value) / (y_max - y_min) * plot_height

    def render_series(values: list[float]) -> list[tuple[float, float]]:
        return [(x_scale(index + 1), y_scale(value)) for index, value in enumerate(values)]

    axis_lines = [
        f'<line x1="{margin_left}" y1="{margin_top}" x2="{margin_left}" y2="{margin_top + plot_height}" stroke="#111827" stroke-width="1.4" />',
        f'<line x1="{margin_left}" y1="{margin_top + plot_height}" x2="{margin_left + plot_width}" y2="{margin_top + plot_height}" stroke="#111827" stroke-width="1.4" />',
    ]

    grid_lines: list[str] = []
    for tick in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]:
        y = y_scale(tick)
        grid_lines.append(
            f'<line x1="{margin_left}" y1="{y:.1f}" x2="{margin_left + plot_width}" y2="{y:.1f}" stroke="#e5e7eb" stroke-width="1" />'
        )
        grid_lines.append(
            f'<text x="{margin_left - 12}" y="{y + 4:.1f}" text-anchor="end" font-size="13" fill="#374151">{tick:.1f}</text>'
        )

    step = max(1, len(item_order) // 24)
    x_ticks: list[str] = []
    for index, item_id in enumerate(item_order, start=1):
        if index == 1 or index == len(item_order) or (index - 1) % step == 0:
            x = x_scale(index)
            x_ticks.append(
                f'<line x1="{x:.1f}" y1="{margin_top + plot_height}" x2="{x:.1f}" y2="{margin_top + plot_height + 7}" stroke="#111827" stroke-width="1" />'
            )
            x_ticks.append(
                f'<text x="{x:.1f}" y="{margin_top + plot_height + 24}" text-anchor="end" font-size="11" fill="#374151" transform="rotate(45 {x:.1f} {margin_top + plot_height + 24})">{escape(item_id)}</text>'
            )

    legend_entries: list[str] = []
    legend_x = margin_left
    legend_y = height - 48
    all_formats = formats + ["gold"]
    for idx, name in enumerate(all_formats):
        color = "#111827" if name == "gold" else FORMAT_COLORS[idx % len(FORMAT_COLORS)]
        x = legend_x + (idx * 245)
        legend_entries.append(
            f'<line x1="{x}" y1="{legend_y}" x2="{x + 26}" y2="{legend_y}" stroke="{color}" stroke-width="3" />'
        )
        legend_entries.append(
            f'<text x="{x + 34}" y="{legend_y + 5}" font-size="14" fill="#111827">{escape(name)}</text>'
        )

    plotted = []
    for idx, graph_format in enumerate(formats):
        plotted.append(
            _svg_line(render_series(cumulative_series[graph_format]), FORMAT_COLORS[idx % len(FORMAT_COLORS)], 2.0)
        )
    plotted.append(_svg_line(render_series(cumulative_gold), "#111827", 3.2))

    title = "ICLE cumulative strength_of_argument by graph format"
    subtitle = f"Running mean over {len(item_order)} items on the raw 1.0-4.0 scale"

    return f"""<svg xmlns=\"http://www.w3.org/2000/svg\" width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\" role=\"img\" aria-label=\"{escape(title)}\">
  <rect width=\"100%\" height=\"100%\" fill=\"#ffffff\" />
  <text x=\"{margin_left}\" y=\"34\" font-size=\"26\" font-weight=\"700\" fill=\"#111827\">{escape(title)}</text>
  <text x=\"{margin_left}\" y=\"56\" font-size=\"14\" fill=\"#4b5563\">{escape(subtitle)}</text>
  {''.join(grid_lines)}
  {''.join(axis_lines)}
  <text x=\"20\" y=\"{margin_top + plot_height / 2:.1f}\" font-size=\"14\" fill=\"#111827\" transform=\"rotate(-90 20 {margin_top + plot_height / 2:.1f})\">raw strength_of_argument</text>
  <text x=\"{margin_left + plot_width / 2:.1f}\" y=\"{height - 24}\" text-anchor=\"middle\" font-size=\"14\" fill=\"#111827\">item index (sorted by item_id)</text>
  {''.join(x_ticks)}
  {''.join(plotted)}
  {''.join(legend_entries)}
</svg>
"""


def create_plot(run_root: Path, output_path: Path) -> None:
    svg = _render_svg(run_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(svg, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot ICLE cumulative scores by graph format")
    parser.add_argument("run_root", type=Path, help="Run root containing output/predictions.csv")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output SVG path; defaults to <run_root>/output/item_cumulative_score_plot.svg",
    )
    args = parser.parse_args()

    output_path = args.output or (args.run_root / "output" / "item_cumulative_score_plot.svg")
    create_plot(args.run_root, output_path)
    print(f"wrote {output_path}")


if __name__ == "__main__":
    main()