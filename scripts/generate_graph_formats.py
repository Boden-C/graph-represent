from __future__ import annotations

import argparse
import json
from pathlib import Path

from pydantic import TypeAdapter

from graph_represent.format_suite import COMPARISON_FORMATS
from graph_represent.graph_formats import (
    GraphTextFormat,
    canonical_graph_signature,
    graph_file_path,
    render_graph,
)
from graph_represent.types.dataset import (
    ArgumentGraphRecord,
    ArgumentGraphTextData,
    ArgumentGraphTextRecord,
)
from graph_represent.utils.files import atomic_write_text

REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_ROOT = REPO_ROOT / "data"
TARGET_FORMATS = [item for item in COMPARISON_FORMATS if item is not GraphTextFormat.JSON]


def _load_records(path: Path) -> list[ArgumentGraphRecord]:
    adapter = TypeAdapter(list[ArgumentGraphRecord])
    return adapter.validate_json(path.read_text(encoding="utf-8"))


def _write_records(path: Path, records: list[ArgumentGraphTextRecord]) -> None:
    payload = [record.model_dump(mode="json") for record in records]
    atomic_write_text(path, json.dumps(payload, indent=2))


def generate_file(source_path: Path) -> list[Path]:
    records = _load_records(source_path)
    graph_root = source_path.parent
    written_paths: list[Path] = []
    for format_name in TARGET_FORMATS:
        rendered_records = [
            ArgumentGraphTextRecord(
                id=record.id,
                image_md5=record.image_md5,
                image_filename=record.image_filename,
                data=ArgumentGraphTextData(
                    graph_format=format_name.value,
                    graph_text=render_graph(record.data.graph, format_name),
                    graph_signature=canonical_graph_signature(record.data.graph),
                ),
            )
            for record in records
        ]
        output_path = graph_file_path(graph_root, format_name, source_path.name)
        _write_records(output_path, rendered_records)
        written_paths.append(output_path)
    return written_paths


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
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    source_paths = [_resolve_path(item) for item in args.files] if args.files else _default_graph_paths()
    for source_path in source_paths:
        for written_path in generate_file(source_path):
            print(written_path.relative_to(REPO_ROOT).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
