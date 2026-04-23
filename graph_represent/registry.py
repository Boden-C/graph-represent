from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

from pydantic import BaseModel

ModelClassT = TypeVar("ModelClassT", bound=type[BaseModel])
FactoryT = TypeVar("FactoryT")


class TypeRegistry:
    def __init__(self) -> None:
        self._types: dict[str, type[BaseModel]] = {}

    def register(self, name: str, model_type: type[BaseModel]) -> None:
        self._types[name] = model_type

    def get(self, name: str) -> type[BaseModel]:
        if name not in self._types:
            raise KeyError(f"Unknown type '{name}'")
        return self._types[name]

    def names(self) -> list[str]:
        return sorted(self._types)


class NamedFactoryRegistry:
    def __init__(self) -> None:
        self._entries: dict[str, object] = {}

    def register(self, name: str, entry: object) -> None:
        self._entries[name] = entry

    def get(self, name: str) -> object:
        if name not in self._entries:
            raise KeyError(f"Unknown registry entry '{name}'")
        return self._entries[name]

    def names(self) -> list[str]:
        return sorted(self._entries)


type_registry = TypeRegistry()
processor_registry = NamedFactoryRegistry()
dataloader_registry = NamedFactoryRegistry()


def register_type(name: str) -> Callable[[ModelClassT], ModelClassT]:
    def decorator(model_type: ModelClassT) -> ModelClassT:
        type_registry.register(name, model_type)
        return model_type

    return decorator


def register_processor(name: str) -> Callable[[FactoryT], FactoryT]:
    def decorator(factory: FactoryT) -> FactoryT:
        processor_registry.register(name, factory)
        return factory

    return decorator


def register_dataloader(name: str) -> Callable[[FactoryT], FactoryT]:
    def decorator(factory: FactoryT) -> FactoryT:
        dataloader_registry.register(name, factory)
        return factory

    return decorator
