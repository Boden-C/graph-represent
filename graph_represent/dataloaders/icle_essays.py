from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Any

from graph_represent.dataloaders.base import DataLoader
from graph_represent.registry import register_dataloader
from graph_represent.types.corpus import IcleEssaySample


def _strength_bucket(value: float) -> int:
    return max(0, min(9, int(value * 10)))


@register_dataloader("IcleEssayDataLoader")
class IcleEssayDataLoader(DataLoader[IcleEssaySample]):
    def __init__(
        self,
        *,
        essays_path: str | Path,
        answers_path: str | Path,
        score_name: str = "strength_of_argument",
        sample_seed: int | None = None,
        excluded_ids: set[str] | None = None,
    ) -> None:
        self.essays_path = Path(essays_path)
        self.answers_path = Path(answers_path)
        self.score_name = score_name
        self.sample_seed = sample_seed
        self.excluded_ids = {str(item) for item in (excluded_ids or set())}
        self._items = self._build_items()
        self._index = {item.id: item for item in self._items}
        self._last_selected_ids: list[str] = []

    def _build_items(self) -> list[IcleEssaySample]:
        essays = json.loads(self.essays_path.read_text(encoding="utf-8"))
        answers = json.loads(self.answers_path.read_text(encoding="utf-8"))
        answers_by_id = {
            str(item["id"]): item
            for item in answers
            if isinstance(item, dict) and item.get("id") is not None
        }
        items: list[IcleEssaySample] = []
        for row in essays:
            if not isinstance(row, dict):
                continue
            item_id = str(row.get("id", "")).strip()
            if not item_id:
                continue
            if item_id in self.excluded_ids:
                continue
            answer = answers_by_id.get(item_id)
            if answer is None:
                continue
            scores_raw = answer.get("scores", {})
            raw_scores_raw = answer.get("raw_scores", {})
            if not isinstance(scores_raw, dict) or not isinstance(raw_scores_raw, dict):
                continue
            scores = {
                str(key): float(value)
                for key, value in scores_raw.items()
                if isinstance(value, int | float)
            }
            raw_scores = {
                str(key): float(value)
                for key, value in raw_scores_raw.items()
                if isinstance(value, int | float)
            }
            if self.score_name not in scores or self.score_name not in raw_scores:
                continue
            items.append(
                IcleEssaySample(
                    id=item_id,
                    corpus="icle",
                    prompt=str(row.get("prompt")) if row.get("prompt") is not None else None,
                    essay=str(row.get("essay", "")),
                    paragraphs=[str(part) for part in row.get("paragraphs", []) if isinstance(part, str)],
                    scores=scores,
                    raw_scores=raw_scores,
                )
            )
        return sorted(items, key=lambda item: item.id)

    def _stratified_sample(self, limit: int) -> list[IcleEssaySample]:
        if self.sample_seed is None:
            return self._items[:limit]
        rng = random.Random(self.sample_seed)
        buckets: dict[int, list[IcleEssaySample]] = {}
        for item in self._items:
            bucket = _strength_bucket(float(item.scores[self.score_name]))
            buckets.setdefault(bucket, []).append(item)
        for values in buckets.values():
            rng.shuffle(values)
        bucket_ids = sorted(buckets)
        selected: list[IcleEssaySample] = []
        while len(selected) < limit:
            progressed = False
            for bucket_id in bucket_ids:
                values = buckets.get(bucket_id, [])
                if not values:
                    continue
                selected.append(values.pop(0))
                progressed = True
                if len(selected) >= limit:
                    break
            if not progressed:
                break
        selected.sort(key=lambda item: item.id)
        return selected

    def iter_items(self, limit: int | None = None):
        if limit is None:
            selected = self._items
        else:
            selected = self._stratified_sample(limit)
        self._last_selected_ids = [item.id for item in selected]
        for item in selected:
            yield item

    def get_item(self, item_id: str) -> IcleEssaySample | None:
        return self._index.get(str(item_id))

    @property
    def last_selected_ids(self) -> list[str]:
        return list(self._last_selected_ids)
