from __future__ import annotations

import json
import zipfile
from pathlib import Path

from graph_represent.dataloaders.base import DataLoader
from graph_represent.registry import register_dataloader
from graph_represent.types.dataset import PersuasionSample
from graph_represent.types.persuasion import PersuasionLabels
from graph_represent.utils.files import image_filename


@register_dataloader("SemEvalPersuasionDataLoader")
class SemEvalPersuasionDataLoader(DataLoader[PersuasionSample]):
    def __init__(self, source: str | Path) -> None:
        source_path = Path(source)
        self._items: list[PersuasionSample] = []
        self._index: dict[str, PersuasionSample] = {}

        if source_path.is_dir():
            payload = self._load_from_directory(source_path)
            image_root = source_path
        elif source_path.is_file() and source_path.suffix in {".json", ".txt"}:
            payload, image_root = self._load_from_manifest_file(source_path)
        elif source_path.is_file() and source_path.suffix == ".zip":
            payload, image_root = self._load_from_zip(source_path)
        else:
            raise ValueError(f"Unsupported SemEval source '{source_path}'")

        for entry in payload:
            item_id = str(entry["id"])
            labels = entry.get("labels")
            raw_image_path = entry.get("image_path") or entry.get("image")
            raw_image_filename = entry.get("image_filename")
            resolved_image_path: Path | None = None
            if isinstance(raw_image_path, str) and raw_image_path.strip():
                candidate = Path(raw_image_path)
                if not candidate.is_absolute():
                    candidate = image_root / candidate
                resolved_image_path = candidate.resolve()
            elif isinstance(raw_image_filename, str) and raw_image_filename.strip():
                resolved_image_path = (image_root / image_filename(raw_image_filename)).resolve()
            sample = PersuasionSample(
                id=item_id,
                image_md5=(
                    str(entry["image_md5"])
                    if isinstance(entry.get("image_md5"), str) and entry["image_md5"].strip()
                    else None
                ),
                image_filename=(
                    image_filename(str(raw_image_filename))
                    if isinstance(raw_image_filename, str) and raw_image_filename.strip()
                    else (
                        image_filename(str(raw_image_path))
                        if isinstance(raw_image_path, str) and raw_image_path.strip()
                        else None
                    )
                ),
                image_path=resolved_image_path,
                text=entry.get("text"),
                gold_labels=PersuasionLabels(reasons={label: "gold" for label in labels or []}),
            )
            self._items.append(sample)
            self._index[item_id] = sample

        self._items.sort(key=lambda sample: sample.id)

    def _load_from_directory(self, path: Path) -> list[dict]:
        txt_files = sorted(path.glob("*.txt"))
        if not txt_files:
            raise FileNotFoundError(f"No .txt label file found in '{path}'")
        return json.loads(txt_files[0].read_text(encoding="utf-8"))

    def _load_from_manifest_file(self, path: Path) -> tuple[list[dict], Path]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise TypeError(f"Expected a list in '{path}'")
        return payload, path.parent

    def _load_from_zip(self, path: Path) -> tuple[list[dict], Path]:
        extract_root = path.parent / path.stem
        extract_root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "r") as archive:
            txt_files = sorted(name for name in archive.namelist() if name.endswith(".txt"))
            if not txt_files:
                raise FileNotFoundError(f"No .txt label file found in '{path}'")
            payload = json.loads(archive.read(txt_files[0]).decode("utf-8"))

            for name in archive.namelist():
                if not name.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                    continue
                target = extract_root / Path(name).name
                if not target.exists():
                    target.write_bytes(archive.read(name))
        return payload, extract_root

    def iter_items(self, limit: int | None = None):
        for count, item in enumerate(self._items):
            if limit is not None and count >= limit:
                break
            yield item

    def get_item(self, item_id: str) -> PersuasionSample | None:
        return self._index.get(str(item_id))
