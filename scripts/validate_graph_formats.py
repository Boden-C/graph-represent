from __future__ import annotations

import argparse
import random
from pathlib import Path

from pydantic import TypeAdapter

from graph_represent.format_suite import COMPARISON_FORMATS
from graph_represent.graph_formats import GraphTextFormat, canonical_graph_payload, parse_graph
from graph_represent.types.dataset import ArgumentGraphRecord, ArgumentGraphTextRecord

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data"
TARGET_FORMATS = [item for item in COMPARISON_FORMATS if item is not GraphTextFormat.JSON]


def _load_source_records(path: Path) -> list[ArgumentGraphRecord]:
    adapter = TypeAdapter(list[ArgumentGraphRecord])
    return adapter.validate_json(path.read_text(encoding="utf-8"))


def _load_rendered_records(path: Path) -> list[ArgumentGraphTextRecord]:
    adapter = TypeAdapter(list[ArgumentGraphTextRecord])
    return adapter.validate_json(path.read_text(encoding="utf-8"))


def validate_file(source_path: Path) -> None:
    graph_root = source_path.parent
    source_records = _load_source_records(source_path)
    source_by_id = {record.id: record for record in source_records}
    for format_name in TARGET_FORMATS:
        rendered_path = graph_root / format_name.value / source_path.name
        rendered_records = _load_rendered_records(rendered_path)
        if set(source_by_id) != {record.id for record in rendered_records}:
            raise ValueError(f"Mismatched ids in '{rendered_path}'")
        for rendered in rendered_records:
            source_payload = canonical_graph_payload(source_by_id[rendered.id].data.graph)
            parsed_payload = canonical_graph_payload(
                parse_graph(rendered.data.graph_text, format_name)
            )
            if source_payload != parsed_payload:
                raise ValueError(
                    f"Round-trip mismatch for '{rendered.id}' in '{rendered_path.name}' ({format_name.value})"
                )


def _sample_outputs(source_path: Path, sample_count: int) -> None:
    source_records = _load_source_records(source_path)
    sampled = random.sample(source_records, k=min(sample_count, len(source_records)))
    for record in sampled:
        print(f"[{source_path.name}] sample {record.id}")
        for format_name in TARGET_FORMATS:
            rendered_path = source_path.parent / format_name.value / source_path.name
            rendered_records = _load_rendered_records(rendered_path)
            rendered = next(item for item in rendered_records if item.id == record.id)
            preview = rendered.data.graph_text.splitlines()[:8]
            print(f"  format={format_name.value}")
            for line in preview:
                print(f"    {line}")


def _default_graph_paths() -> list[Path]:
    return sorted(DATA_ROOT.glob("*/graphs/*.json"))


def _resolve_path(value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        return raw
    candidate = (REPO_ROOT / raw).resolve()
    if candidate.exists():
        return candidate
    return (DATA_ROOT / value).resolve()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "files",
        nargs="*",
        help="Specific graph JSON files. Defaults to all data/*/graphs/*.json.",
    )
    parser.add_argument("--sample-count", type=int, default=0)
    parser.add_argument("--seed", type=int, default=7)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    random.seed(args.seed)
    source_paths = [_resolve_path(item) for item in args.files] if args.files else _default_graph_paths()
    for source_path in source_paths:
        validate_file(source_path)
        print(f"validated {source_path.relative_to(REPO_ROOT).as_posix()}")
        if args.sample_count > 0:
            _sample_outputs(source_path, args.sample_count)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
