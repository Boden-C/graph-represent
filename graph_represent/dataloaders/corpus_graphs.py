from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from graph_represent.dataloaders.base import DataLoader
from graph_represent.registry import register_dataloader
from graph_represent.types.corpus import CorpusGraphSample
from graph_represent.types.dataset import ArgumentGraphRecord


@register_dataloader("CorpusGraphDataLoader")
class CorpusGraphDataLoader(DataLoader[CorpusGraphSample]):
    def __init__(
        self,
        *,
        corpus: str,
        graph_path: str | Path,
        graph_version: str | None = None,
        answers_path: str | Path | None = None,
        dataset_path: str | Path | None = None,
    ) -> None:
        self.corpus = corpus
        self.graph_path = Path(graph_path)
        self.graph_version = graph_version or self.graph_path.stem
        self.answers_path = Path(answers_path) if answers_path is not None else None
        self.dataset_path = Path(dataset_path) if dataset_path is not None else None
        self._answers = self._load_answers(self.answers_path)
        dataset_ids = self._load_dataset_ids(self.dataset_path)
        dataset_id_set = set(dataset_ids) if dataset_ids is not None else None
        records = TypeAdapter(list[ArgumentGraphRecord]).validate_json(
            self.graph_path.read_text(encoding="utf-8")
        )

        self._items: list[CorpusGraphSample] = []
        self._index: dict[str, CorpusGraphSample] = {}
        for record in records:
            if dataset_id_set is not None and record.id not in dataset_id_set:
                continue
            answer = self._answers.get(record.id)
            sample = CorpusGraphSample(
                id=record.id,
                corpus=corpus,
                graph=record.data.graph,
                graph_version=self.graph_version,
                image_filename=record.image_filename or None,
                text=answer.get("text") if isinstance(answer, dict) else None,
                gold=answer,
                metadata={
                    "image_md5": record.image_md5,
                    "source_graph_path": str(self.graph_path),
                    "dataset_path": str(self.dataset_path) if self.dataset_path is not None else None,
                },
            )
            self._items.append(sample)
            self._index[sample.id] = sample
        if dataset_ids is None:
            self._items.sort(key=lambda item: item.id)
        else:
            order = {item_id: index for index, item_id in enumerate(dataset_ids)}
            self._items.sort(key=lambda item: order[item.id])

    @staticmethod
    def _load_answers(path: Path | None) -> dict[str, dict[str, Any]]:
        if path is None or not path.exists():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            raw_items = payload.get("items", payload)
            if isinstance(raw_items, dict):
                return {str(key): dict(value) for key, value in raw_items.items() if isinstance(value, dict)}
        if isinstance(payload, list):
            return {
                str(item["id"]): dict(item)
                for item in payload
                if isinstance(item, dict) and item.get("id") is not None
            }
        raise TypeError(f"Unsupported answers format in '{path}'")

    @staticmethod
    def _load_dataset_ids(path: Path | None) -> list[str] | None:
        if path is None:
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            if isinstance(payload.get("item_ids"), list):
                return [str(item_id) for item_id in payload["item_ids"]]
            if isinstance(payload.get("items"), list):
                return [
                    str(item["id"] if isinstance(item, dict) else item)
                    for item in payload["items"]
                ]
        if isinstance(payload, list):
            return [
                str(item["id"] if isinstance(item, dict) else item)
                for item in payload
            ]
        raise TypeError(f"Unsupported dataset format in '{path}'")

    def iter_items(self, limit: int | None = None):
        for count, item in enumerate(self._items):
            if limit is not None and count >= limit:
                break
            yield item

    def get_item(self, item_id: str) -> CorpusGraphSample | None:
        return self._index.get(str(item_id))
