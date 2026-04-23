from __future__ import annotations

from enum import StrEnum
from itertools import groupby

import networkx as nx
from pydantic import Field, field_validator, model_validator

from graph_represent.registry import register_type
from graph_represent.types.base import SchemaModel


class VertexType(StrEnum):
    ELEMENT = "element"
    PREMISE = "element"
    BACKGROUND = "background"
    EVIDENCE = "background"
    CLAIM = "claim"
    NONE = "none"


class EdgeType(StrEnum):
    SUPPORT = "support"
    SUPPORTS = "support"
    ATTACK = "attack"
    ATTACKS = "attack"
    TRIGGER = "trigger"
    PARAPHRASE = "paraphrase"


class Vertex(SchemaModel):
    idx: int
    text: str
    type: VertexType

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        alias_map = {
            "claim": VertexType.CLAIM.value,
            "majorclaim": VertexType.CLAIM.value,
            "major_claim": VertexType.CLAIM.value,
            "major claim": VertexType.CLAIM.value,
            "premise": VertexType.ELEMENT.value,
            "premises": VertexType.ELEMENT.value,
            "element": VertexType.ELEMENT.value,
            "background": VertexType.BACKGROUND.value,
            "evidence": VertexType.BACKGROUND.value,
        }
        return alias_map.get(normalized, normalized)


class Edge(SchemaModel):
    from_idx: int
    to_idx: int
    type: EdgeType

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        normalized = value.strip().lower()
        alias_map = {
            "supports": EdgeType.SUPPORT.value,
            "attacks": EdgeType.ATTACK.value,
        }
        return alias_map.get(normalized, normalized)


class Argument(SchemaModel):
    claim: int
    premises: list[int] = Field(default_factory=list)
    type: EdgeType

    @field_validator("type", mode="before")
    @classmethod
    def normalize_type(cls, value: object) -> object:
        return Edge.normalize_type(value)


@register_type("Graph")
class Graph(SchemaModel):
    nodes: list[Vertex]
    arguments: list[Argument] = Field(default_factory=list)
    edges: list[Edge] | None = Field(default=None, exclude=True)

    @model_validator(mode="after")
    def convert_edges_to_arguments(self) -> Graph:
        if self.edges and not self.arguments:

            def group_key(edge: Edge) -> tuple[int, str]:
                return (edge.to_idx, edge.type.value)

            sorted_edges = sorted(self.edges, key=group_key)
            self.arguments = [
                Argument(
                    claim=claim,
                    premises=[edge.from_idx for edge in group],
                    type=EdgeType(edge_type),
                )
                for (claim, edge_type), group in groupby(sorted_edges, key=group_key)
            ]
        self.edges = None
        return self

    def flat_edges(self) -> list[Edge]:
        return [
            Edge(from_idx=premise, to_idx=argument.claim, type=argument.type)
            for argument in self.arguments
            for premise in argument.premises
        ]

    def normalize(self) -> Graph:
        index_map: dict[int, int] = {}
        for new_index, node in enumerate(self.nodes):
            index_map[node.idx] = new_index
            node.idx = new_index
        cleaned_arguments: list[Argument] = []
        for argument in self.arguments:
            if argument.claim not in index_map:
                continue
            normalized_premises = [
                index_map[premise] for premise in argument.premises if premise in index_map
            ]
            if not normalized_premises:
                continue
            argument.claim = index_map[argument.claim]
            argument.premises = normalized_premises
            cleaned_arguments.append(argument)
        self.arguments = cleaned_arguments
        return self

    def to_networkx(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        graph.add_nodes_from(node.idx for node in self.nodes)
        graph.add_edges_from((edge.from_idx, edge.to_idx) for edge in self.flat_edges())
        return graph
