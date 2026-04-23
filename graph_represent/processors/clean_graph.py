from __future__ import annotations

from copy import deepcopy

from graph_represent.processors.base import Processor, ProcessorContext
from graph_represent.types.graph import Argument, EdgeType, Graph


class CleanGraph(Processor[Graph, Graph, Graph]):
    def validate_types(self) -> None:
        if self.input_type is not Graph or self.output_type is not Graph:
            raise ValueError("CleanGraph requires Graph input_type and output_type")

    def process(self, input_data: Graph, context: ProcessorContext[Graph]) -> Graph:
        del context
        graph = Graph.model_validate(deepcopy(input_data.model_dump()))
        merge_duplicates = bool(self.config.get("merge_duplicate_nodes", False))
        normalize_indices = bool(self.config.get("normalize_indices", True))

        if merge_duplicates:
            key_to_index: dict[tuple[str, str], int] = {}
            index_map: dict[int, int] = {}
            deduped_nodes = []
            for node in graph.nodes:
                key = (node.text.strip(), node.type.value)
                if key in key_to_index:
                    index_map[node.idx] = key_to_index[key]
                    continue
                key_to_index[key] = node.idx
                index_map[node.idx] = node.idx
                deduped_nodes.append(node)
            graph.nodes = deduped_nodes
            merged_arguments: dict[tuple[int, str], list[int]] = {}
            for argument in graph.arguments:
                claim = index_map.get(argument.claim, argument.claim)
                premises = [index_map.get(premise, premise) for premise in argument.premises]
                filtered_premises: list[int] = []
                seen_premises: set[int] = set()
                for premise in premises:
                    if premise == claim or premise in seen_premises:
                        continue
                    seen_premises.add(premise)
                    filtered_premises.append(premise)
                if not filtered_premises:
                    continue
                merged_arguments.setdefault((claim, argument.type.value), []).extend(
                    filtered_premises
                )
            graph.arguments = [
                Argument.model_validate(
                    {
                        "claim": claim,
                        "premises": list(dict.fromkeys(premises)),
                        "type": EdgeType(argument_type),
                    }
                )
                for (claim, argument_type), premises in merged_arguments.items()
            ]

        valid_indices = {node.idx for node in graph.nodes}
        graph.arguments = [
            argument
            for argument in graph.arguments
            if argument.claim in valid_indices
            and all(premise in valid_indices for premise in argument.premises)
        ]

        if normalize_indices:
            graph.normalize()

        if bool(self.config.get("topological_sort", False)):
            ordered_nodes = graph.to_networkx()
            sorted_indices = list(__import__("networkx").topological_sort(ordered_nodes))
            node_map = {node.idx: node for node in graph.nodes}
            graph.nodes = [node_map[index] for index in sorted_indices]
            graph.normalize()

        return graph
