import csv
import io
import math
import random
from collections.abc import Sequence
from pathlib import Path

from graph_represent.processors.persuasion import compute_persuasion_aggregate
from graph_represent.types.persuasion import PersuasionAggregateScores, PersuasionItemResult
from graph_represent.utils.files import atomic_write_text

SUMMARY_METRICS = (
    "micro_precision",
    "micro_recall",
    "micro_f1",
    "macro_precision",
    "macro_recall",
    "macro_f1",
)


def _percentile(values: Sequence[float], quantile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    rank = (len(ordered) - 1) * quantile
    lower_index = math.floor(rank)
    upper_index = math.ceil(rank)
    if lower_index == upper_index:
        return ordered[lower_index]
    lower_value = ordered[lower_index]
    upper_value = ordered[upper_index]
    weight = rank - lower_index
    return lower_value + (upper_value - lower_value) * weight


def bootstrap_aggregates(
    results: list[PersuasionItemResult],
    *,
    resamples: int,
    seed: int,
) -> list[PersuasionAggregateScores]:
    if not results:
        return []
    if resamples <= 0:
        return [compute_persuasion_aggregate(results)]

    rng = random.Random(seed)
    sample_count = len(results)
    aggregates: list[PersuasionAggregateScores] = []

    for _ in range(resamples):
        sampled_results = [results[rng.randrange(sample_count)] for _ in range(sample_count)]
        aggregates.append(compute_persuasion_aggregate(sampled_results))

    return aggregates


def build_summary_row(
    *,
    method_name: str,
    model_name: str,
    results: list[PersuasionItemResult],
    resamples: int,
    seed: int,
    extra_fields: dict[str, object] | None = None,
) -> dict[str, object]:
    aggregate = compute_persuasion_aggregate(results)
    bootstrap_samples = bootstrap_aggregates(results, resamples=resamples, seed=seed)

    row: dict[str, object] = {
        "method": method_name,
        "model_name": model_name,
    }
    if extra_fields:
        row.update(extra_fields)

    row["item_count"] = len(results)

    for metric_name in SUMMARY_METRICS:
        point_estimate = float(getattr(aggregate, metric_name))
        bootstrap_values = [float(getattr(sample, metric_name)) for sample in bootstrap_samples]
        if len(bootstrap_values) > 1:
            mean_value = sum(bootstrap_values) / len(bootstrap_values)
            variance = sum((value - mean_value) ** 2 for value in bootstrap_values) / (
                len(bootstrap_values) - 1
            )
            stderr = math.sqrt(max(variance, 0.0))
        else:
            stderr = 0.0

        row[f"{metric_name}_summary"] = f"{point_estimate:.5f}±{stderr:.5f}"

    return row


def write_summary_csv(rows: list[dict[str, object]], path: Path) -> None:
    if not rows:
        return

    # Get header from the first row natively, keeping insertion order
    header = list(rows[0].keys())

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    atomic_write_text(path, buffer.getvalue())
