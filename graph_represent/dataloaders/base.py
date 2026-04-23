from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from typing import Generic, TypeVar

from pydantic import BaseModel

ItemT = TypeVar("ItemT", bound=BaseModel, covariant=True)


class DataLoader(ABC, Generic[ItemT]):
    @abstractmethod
    def iter_items(self, limit: int | None = None) -> Iterable[ItemT]:
        """Yield typed items in a deterministic order."""

    @abstractmethod
    def get_item(self, item_id: str) -> ItemT | None:
        """Load one item by item_id."""
