from __future__ import annotations

import ast
import json
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from enum import StrEnum
from pathlib import Path
from statistics import median
from typing import Any

import networkx as nx

from graph_represent.types.graph import Argument, EdgeType, Graph, Vertex, VertexType
from graph_represent.utils.files import sha256_text


class GraphTextFormat(StrEnum):
    JSON = "json"
    XML = "xml"
    PYTHON_DSL = "python-dsl"
    MERMAID = "mermaid"
    NESTED_JSON = "nested-json"
    EDGE_TABLE = "edge-table"
    FACTS = "facts"
    CLAIM_BUNDLES_INLINE = "claim-bundles-inline"
    RELATION_XML = "relation-xml"
    INLINE_PYTHON_DSL = "inline-python-dsl"
    COMPACT_JSON = "compact-json"
    FORMAL_PROOF = "formal-proof"
    EDGE_SENTENCES = "edge-sentences"


FORMAT_LANGUAGE: dict[GraphTextFormat, str] = {
    GraphTextFormat.JSON: "json",
    GraphTextFormat.XML: "xml",
    GraphTextFormat.PYTHON_DSL: "python",
    GraphTextFormat.MERMAID: "mermaid",
    GraphTextFormat.NESTED_JSON: "json",
    GraphTextFormat.EDGE_TABLE: "markdown",
    GraphTextFormat.FACTS: "text",
    GraphTextFormat.CLAIM_BUNDLES_INLINE: "text",
    GraphTextFormat.RELATION_XML: "xml",
    GraphTextFormat.INLINE_PYTHON_DSL: "python",
    GraphTextFormat.COMPACT_JSON: "json",
    GraphTextFormat.FORMAL_PROOF: "text",
    GraphTextFormat.EDGE_SENTENCES: "text",
}

FORMAT_LABEL: dict[GraphTextFormat, str] = {
    GraphTextFormat.JSON: "Original JSON",
    GraphTextFormat.XML: "XML with attributes (top-down)",
    GraphTextFormat.PYTHON_DSL: "Python DSL (bottom-up)",
    GraphTextFormat.MERMAID: "Mermaid diagram",
    GraphTextFormat.NESTED_JSON: "Nested JSON",
    GraphTextFormat.EDGE_TABLE: "Edge table",
    GraphTextFormat.FACTS: "Facts",
    GraphTextFormat.CLAIM_BUNDLES_INLINE: "Claim bundles inline",
    GraphTextFormat.RELATION_XML: "Relation XML",
    GraphTextFormat.INLINE_PYTHON_DSL: "Inline Python DSL",
    GraphTextFormat.COMPACT_JSON: "Compact JSON",
    GraphTextFormat.FORMAL_PROOF: "Formal proof",
    GraphTextFormat.EDGE_SENTENCES: "Edge sentences",
}


def canonical_graph_payload(graph: Graph) -> dict[str, object]:
    normalized_nodes_by_id = {node.idx: node for node in graph.nodes}
    node_type_by_id = {node_id: node.type for node_id, node in normalized_nodes_by_id.items()}
    node_ids = set(normalized_nodes_by_id)
    merged_premises: dict[tuple[int, str], set[int]] = defaultdict(set)
    for argument in sorted(
        graph.arguments,
        key=lambda item: (item.claim, item.type.value, tuple(sorted(item.premises))),
    ):
        if argument.claim not in node_ids:
            continue
        if node_type_by_id[argument.claim] is not VertexType.CLAIM:
            continue
        premises = {premise for premise in argument.premises if premise in node_ids}
        if not premises:
            continue
        merged_premises[(argument.claim, argument.type.value)].update(premises)
    normalized_arguments: list[dict[str, object]] = [
        {"claim": claim, "premises": sorted(premises), "type": kind}
        for (claim, kind), premises in sorted(
            merged_premises.items(),
            key=lambda item: (item[0][0], item[0][1], tuple(sorted(item[1]))),
        )
    ]
    return {
        "nodes": [
            {"idx": node.idx, "text": node.text, "type": node.type.value}
            for node in sorted(normalized_nodes_by_id.values(), key=lambda item: item.idx)
        ],
        "arguments": normalized_arguments,
    }


def canonical_graph_signature(graph: Graph) -> str:
    return sha256_text(json.dumps(canonical_graph_payload(graph), sort_keys=True))


def graph_text_format_from_value(value: str | GraphTextFormat) -> GraphTextFormat:
    if isinstance(value, GraphTextFormat):
        return value
    return GraphTextFormat(str(value).strip().lower())


def render_graph(graph: Graph, format_name: str | GraphTextFormat) -> str:
    resolved = graph_text_format_from_value(format_name)
    if resolved is GraphTextFormat.JSON:
        return json.dumps(canonical_graph_payload(graph), indent=2)
    if resolved is GraphTextFormat.XML:
        return _render_xml(graph)
    if resolved is GraphTextFormat.PYTHON_DSL:
        return _render_python_dsl(graph)
    if resolved is GraphTextFormat.MERMAID:
        return _render_mermaid(graph)
    if resolved is GraphTextFormat.NESTED_JSON:
        return _render_nested_json(graph)
    if resolved is GraphTextFormat.EDGE_TABLE:
        return _render_edge_table(graph)
    if resolved is GraphTextFormat.FACTS:
        return _render_facts(graph)
    if resolved is GraphTextFormat.CLAIM_BUNDLES_INLINE:
        return _render_claim_bundles_inline(graph)
    if resolved is GraphTextFormat.RELATION_XML:
        return _render_relation_xml(graph)
    if resolved is GraphTextFormat.INLINE_PYTHON_DSL:
        return _render_inline_python_dsl(graph)
    if resolved is GraphTextFormat.COMPACT_JSON:
        return _render_compact_json(graph)
    if resolved is GraphTextFormat.FORMAL_PROOF:
        return _render_formal_proof(graph)
    if resolved is GraphTextFormat.EDGE_SENTENCES:
        return _render_edge_sentences(graph)
    raise ValueError(f"Unsupported graph format '{format_name}'")


def parse_graph(text: str, format_name: str | GraphTextFormat) -> Graph:
    resolved = graph_text_format_from_value(format_name)
    if resolved is GraphTextFormat.JSON:
        return Graph.model_validate(json.loads(text))
    if resolved is GraphTextFormat.XML:
        return _parse_xml(text)
    if resolved is GraphTextFormat.PYTHON_DSL:
        return _parse_python_dsl(text)
    if resolved is GraphTextFormat.MERMAID:
        return _parse_mermaid(text)
    if resolved is GraphTextFormat.NESTED_JSON:
        return _parse_nested_json(text)
    if resolved is GraphTextFormat.EDGE_TABLE:
        return _parse_edge_table(text)
    if resolved is GraphTextFormat.FACTS:
        return _parse_facts(text)
    if resolved is GraphTextFormat.CLAIM_BUNDLES_INLINE:
        return _parse_claim_bundles_inline(text)
    if resolved is GraphTextFormat.RELATION_XML:
        return _parse_relation_xml(text)
    if resolved is GraphTextFormat.INLINE_PYTHON_DSL:
        return _parse_inline_python_dsl(text)
    if resolved is GraphTextFormat.COMPACT_JSON:
        return _parse_compact_json(text)
    if resolved is GraphTextFormat.FORMAL_PROOF:
        return _parse_formal_proof(text)
    if resolved is GraphTextFormat.EDGE_SENTENCES:
        return _parse_edge_sentences(text)
    raise ValueError(f"Unsupported graph format '{format_name}'")


def fenced_graph_text(graph_text: str, format_name: str | GraphTextFormat) -> str:
    resolved = graph_text_format_from_value(format_name)
    language = FORMAT_LANGUAGE[resolved]
    label = FORMAT_LABEL[resolved]
    return f"Graph representation format: {label}\n\n```{language}\n{graph_text}\n```"


def graph_file_path(root: Path, format_name: str | GraphTextFormat, file_name: str) -> Path:
    resolved = graph_text_format_from_value(format_name)
    if resolved is GraphTextFormat.JSON:
        return root / file_name
    return root / resolved.value / file_name


def numeric_summary_stats(values: list[float]) -> dict[str, float | int]:
    if not values:
        return {"count": 0, "mean": 0.0, "median": 0.0, "p95": 0.0, "min": 0.0, "max": 0.0}
    ordered = sorted(values)
    p95_index = max(0, min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95))))
    return {
        "count": len(values),
        "mean": round(sum(values) / len(values), 6),
        "median": round(float(median(values)), 6),
        "p95": round(float(ordered[p95_index]), 6),
        "min": round(float(ordered[0]), 6),
        "max": round(float(ordered[-1]), 6),
    }


def _node_lookup(graph: Graph) -> dict[int, Vertex]:
    return {node.idx: node for node in graph.nodes}


def _children_by_claim(graph: Graph) -> dict[int, list[tuple[int, EdgeType]]]:
    node_lookup = _node_lookup(graph)
    children: dict[int, list[tuple[int, EdgeType]]] = defaultdict(list)
    for argument in sorted(
        graph.arguments,
        key=lambda item: (item.claim, item.type.value, tuple(sorted(item.premises))),
    ):
        if argument.claim not in node_lookup:
            continue
        if node_lookup[argument.claim].type is not VertexType.CLAIM:
            continue
        for premise in sorted(argument.premises):
            if premise not in node_lookup:
                continue
            children[argument.claim].append((premise, argument.type))
    return children


def _assert_acyclic(graph: Graph) -> None:
    if not nx.is_directed_acyclic_graph(graph.to_networkx()):
        raise ValueError("Graph format conversion requires an acyclic graph")


def _ordered_roots(graph: Graph) -> list[int]:
    node_lookup = _node_lookup(graph)
    unique_nodes = sorted(node_lookup.values(), key=lambda item: item.idx)
    premise_ids = {premise for argument in graph.arguments for premise in argument.premises}
    root_claim_ids = [
        node.idx
        for node in unique_nodes
        if node.type is VertexType.CLAIM and node.idx not in premise_ids
    ]
    disconnected_ids = [node.idx for node in unique_nodes if node.idx not in premise_ids]
    ordered_roots: list[int] = []
    seen_root_ids: set[int] = set()
    for node_id in [*root_claim_ids, *disconnected_ids]:
        if node_id not in seen_root_ids:
            ordered_roots.append(node_id)
            seen_root_ids.add(node_id)
    return ordered_roots


def _render_xml(graph: Graph) -> str:
    node_lookup = _node_lookup(graph)
    unique_nodes = sorted(node_lookup.values(), key=lambda item: item.idx)
    children_by_claim = _children_by_claim(graph)
    ordered_roots = _ordered_roots(graph)

    root = ET.Element("argument")
    rendered_root_ids: set[int] = set()

    def append_node(
        parent: ET.Element,
        node_id: int,
        edge_type: EdgeType | None,
        path: set[int],
    ) -> None:
        node = node_lookup[node_id]
        attributes = {"id": str(node.idx), "text": node.text}
        if edge_type is not None:
            attributes["type"] = edge_type.value
        if node_id in path:
            attributes["ref"] = "true"
            ET.SubElement(parent, node.type.value, attributes)
            return
        element = ET.SubElement(parent, node.type.value, attributes)
        next_path = set(path)
        next_path.add(node_id)
        for child_id, child_edge_type in children_by_claim.get(node.idx, []):
            append_node(element, child_id, child_edge_type, next_path)

    for node_id in ordered_roots:
        append_node(root, node_id, None, set())
        rendered_root_ids.add(node_id)

    for node in unique_nodes:
        if node.idx not in rendered_root_ids:
            append_node(root, node.idx, None, set())

    return ET.tostring(root, encoding="unicode")


def _dsl_variable_name(node: Vertex, sink_claim_ids: set[int]) -> str:
    if node.type is VertexType.CLAIM and node.idx in sink_claim_ids:
        return f"root_claim_{node.idx}"
    return f"{node.type.value}_{node.idx}"


def _claim_depths(graph: Graph) -> dict[int, int]:
    node_lookup = _node_lookup(graph)
    unique_nodes = list(node_lookup.values())
    claim_nodes = [node for node in unique_nodes if node.type is VertexType.CLAIM]
    claim_ids = {node.idx for node in claim_nodes}
    edges = [
        (premise, argument.claim)
        for argument in graph.arguments
        if argument.claim in claim_ids
        for premise in argument.premises
        if premise in claim_ids
    ]
    claim_graph = nx.DiGraph()
    claim_graph.add_nodes_from(claim_ids)
    claim_graph.add_edges_from(edges)
    condensation = nx.condensation(claim_graph)
    component_depths: dict[int, int] = {}
    memo = {node.idx: 0 for node in unique_nodes if node.type is not VertexType.CLAIM}

    def component_depth(component_id: int) -> int:
        if component_id in component_depths:
            return component_depths[component_id]
        predecessors = list(condensation.predecessors(component_id))
        if not predecessors:
            component_depths[component_id] = 1
            return 1
        component_depths[component_id] = 1 + max(component_depth(item) for item in predecessors)
        return component_depths[component_id]

    members: dict[int, set[int]] = {
        component_id: set(member_ids)
        for component_id, member_ids in condensation.nodes(data="members")
    }
    for component_id in condensation.nodes:
        depth = component_depth(component_id)
        for node_id in members[component_id]:
            memo[node_id] = depth
    return memo


def _render_python_dsl(graph: Graph) -> str:
    node_lookup = _node_lookup(graph)
    unique_nodes = sorted(node_lookup.values(), key=lambda item: item.idx)
    premise_ids = {premise for argument in graph.arguments for premise in argument.premises}
    sink_claim_ids = {
        node.idx
        for node in unique_nodes
        if node.type is VertexType.CLAIM and node.idx not in premise_ids
    }
    depths = _claim_depths(graph)
    layer_zero_nodes = [node for node in unique_nodes if depths[node.idx] == 0]
    lines: list[str] = ["# LAYER 0"]
    ctor_map = {
        VertexType.ELEMENT: "Element",
        VertexType.BACKGROUND: "Background",
        VertexType.CLAIM: "Claim",
        VertexType.NONE: "Element",
    }
    for node in layer_zero_nodes:
        ctor_name = ctor_map.get(node.type, "Element")
        variable_name = _dsl_variable_name(node, sink_claim_ids)
        lines.append(f"{variable_name} = {ctor_name}({node.text!r})")

    claim_nodes_by_depth: dict[int, list[Vertex]] = defaultdict(list)
    for node in unique_nodes:
        if node.type is VertexType.CLAIM and depths[node.idx] > 0:
            claim_nodes_by_depth[depths[node.idx]].append(node)

    for layer_index in sorted(claim_nodes_by_depth):
        lines.append("")
        lines.append(f"# LAYER {layer_index}")
        for node in claim_nodes_by_depth[layer_index]:
            variable_name = _dsl_variable_name(node, sink_claim_ids)
            lines.append(f"{variable_name} = Claim({node.text!r})")
        for node in claim_nodes_by_depth[layer_index]:
            variable_name = _dsl_variable_name(node, sink_claim_ids)
            for argument in sorted(
                [item for item in graph.arguments if item.claim == node.idx],
                key=lambda item: (item.type.value, tuple(sorted(item.premises))),
            ):
                method_name = "supported_by" if argument.type is EdgeType.SUPPORT else "attacked_by"
                valid_premises = [
                    premise for premise in sorted(argument.premises) if premise in node_lookup
                ]
                if not valid_premises:
                    continue
                premise_variables = ", ".join(
                    _dsl_variable_name(node_lookup[premise], sink_claim_ids)
                    for premise in valid_premises
                )
                lines.append(f"{variable_name}.{method_name}({premise_variables})")

    return "\n".join(lines)


def _mermaid_label(text: str) -> str:
    return json.dumps(text)[1:-1]


def _render_mermaid(graph: Graph) -> str:
    node_lookup = _node_lookup(graph)
    unique_nodes = sorted(node_lookup.values(), key=lambda item: item.idx)
    premise_ids = {premise for argument in graph.arguments for premise in argument.premises}
    sink_claim_ids = {
        node.idx
        for node in unique_nodes
        if node.type is VertexType.CLAIM and node.idx not in premise_ids
    }
    lines = ["graph BT"]
    for node in unique_nodes:
        variable_name = _dsl_variable_name(node, sink_claim_ids)
        lines.append(f'  {variable_name}["{_mermaid_label(node.text)}"]')
    lines.append("")
    for argument in sorted(
        graph.arguments,
        key=lambda item: (item.claim, item.type.value, tuple(sorted(item.premises))),
    ):
        if argument.claim not in node_lookup:
            continue
        claim_variable = _dsl_variable_name(node_lookup[argument.claim], sink_claim_ids)
        for premise in sorted(argument.premises):
            if premise not in node_lookup:
                continue
            premise_variable = _dsl_variable_name(node_lookup[premise], sink_claim_ids)
            lines.append(f"  {premise_variable} -- {argument.type.value} --> {claim_variable}")
    return "\n".join(lines)


def _render_nested_json(graph: Graph) -> str:
    _assert_acyclic(graph)
    node_lookup = _node_lookup(graph)
    children_by_claim = _children_by_claim(graph)
    ordered_roots = _ordered_roots(graph)

    def build_node(node_id: int, path: set[int]) -> dict[str, object]:
        node = node_lookup[node_id]
        item: dict[str, object] = {
            "id": node.idx,
            "type": node.type.value,
            "text": node.text,
        }
        if node_id in path:
            item["ref"] = True
            return item
        next_path = set(path)
        next_path.add(node_id)
        supports: list[dict[str, object]] = []
        attacks: list[dict[str, object]] = []
        for child_id, edge_type in children_by_claim.get(node_id, []):
            child_item = build_node(child_id, next_path)
            if edge_type is EdgeType.SUPPORT:
                supports.append(child_item)
            else:
                attacks.append(child_item)
        if supports:
            item["supports"] = supports
        if attacks:
            item["attacks"] = attacks
        return item

    payload = {"roots": [build_node(node_id, set()) for node_id in ordered_roots]}
    return json.dumps(payload, indent=2)


def _render_edge_table(graph: Graph) -> str:
    payload = canonical_graph_payload(graph)
    lines = [
        "NODES",
        "| id | type | text |",
        "| --- | --- | --- |",
    ]
    for node in payload["nodes"]:
        lines.append(
            f'| {node["idx"]} | {node["type"]} | {json.dumps(node["text"])} |'
        )
    lines.extend(["", "EDGES", "| from | rel | to |", "| --- | --- | --- |"])
    for argument in payload["arguments"]:
        for premise in argument["premises"]:
            lines.append(f'| {premise} | {argument["type"]} | {argument["claim"]} |')
    return "\n".join(lines)


def _render_facts(graph: Graph) -> str:
    payload = canonical_graph_payload(graph)
    lines: list[str] = []
    for node in payload["nodes"]:
        lines.append(
            f'node({node["idx"]}, {node["type"]}, {json.dumps(node["text"])}).'
        )
    for argument in payload["arguments"]:
        for premise in argument["premises"]:
            lines.append(f'edge({premise}, {argument["type"]}, {argument["claim"]}).')
    return "\n".join(lines)


def _render_claim_bundles_inline(graph: Graph) -> str:
    node_lookup = _node_lookup(graph)
    children_by_claim = _children_by_claim(graph)
    lines = ["NODES"]
    for node in sorted(node_lookup.values(), key=lambda item: item.idx):
        lines.append(f'node|{node.idx}|{node.type.value}|{json.dumps(node.text)}')
    lines.append("")
    lines.append("CLAIMS")
    claim_ids = sorted(node.idx for node in node_lookup.values() if node.type is VertexType.CLAIM)
    for claim_id in claim_ids:
        claim = node_lookup[claim_id]
        lines.append(f'claim|{claim_id}|{json.dumps(claim.text)}')
        for premise_id, edge_type in children_by_claim.get(claim_id, []):
            premise = node_lookup[premise_id]
            lines.append(
                f'{edge_type.value}|{claim_id}|{premise_id}|{premise.type.value}|{json.dumps(premise.text)}'
            )
    lines.append("END")
    return "\n".join(lines)


def _render_relation_xml(graph: Graph) -> str:
    _assert_acyclic(graph)
    node_lookup = _node_lookup(graph)
    unique_nodes = sorted(node_lookup.values(), key=lambda item: item.idx)
    children_by_claim = _children_by_claim(graph)
    ordered_roots = _ordered_roots(graph)
    root = ET.Element("argument")
    rendered_root_ids: set[int] = set()

    def append_node(parent: ET.Element, node_id: int, path: set[int]) -> None:
        node = node_lookup[node_id]
        attrs = {"id": str(node.idx), "node_type": node.type.value, "text": node.text}
        if node_id in path:
            attrs["ref"] = "true"
            ET.SubElement(parent, "node", attrs)
            return
        node_element = ET.SubElement(parent, "node", attrs)
        next_path = set(path)
        next_path.add(node_id)
        for child_id, edge_type in children_by_claim.get(node_id, []):
            rel_element = ET.SubElement(node_element, edge_type.value)
            append_node(rel_element, child_id, next_path)

    for node_id in ordered_roots:
        append_node(root, node_id, set())
        rendered_root_ids.add(node_id)
    for node in unique_nodes:
        if node.idx not in rendered_root_ids:
            append_node(root, node.idx, set())
    return ET.tostring(root, encoding="unicode")


def _render_inline_python_dsl(graph: Graph) -> str:
    payload = canonical_graph_payload(graph)
    node_lookup = {int(node["idx"]): node for node in payload["nodes"]}
    grouped: dict[int, dict[str, list[dict[str, object]]]] = defaultdict(
        lambda: {"support": [], "attack": []}
    )
    for argument in payload["arguments"]:
        claim_id = int(argument["claim"])
        edge_name = str(argument["type"])
        for premise_id in argument["premises"]:
            premise = node_lookup[int(premise_id)]
            grouped[claim_id][edge_name].append(
                {
                    "id": int(premise["idx"]),
                    "type": str(premise["type"]),
                    "text": str(premise["text"]),
                }
            )

    referenced = {int(item["id"]) for claim_edges in grouped.values() for edges in claim_edges.values() for item in edges}
    lines: list[str] = []
    for node in payload["nodes"]:
        node_id = int(node["idx"])
        if str(node["type"]) == VertexType.CLAIM.value:
            supports = grouped[node_id]["support"]
            attacks = grouped[node_id]["attack"]
            lines.append(
                "claim("
                f"id={node_id}, "
                f"text={json.dumps(str(node['text']))}, "
                f"supports={repr([(item['id'], item['type'], item['text']) for item in supports])}, "
                f"attacks={repr([(item['id'], item['type'], item['text']) for item in attacks])}"
                ")"
            )
            continue
        if node_id not in referenced:
            lines.append(
                "node("
                f"id={node_id}, "
                f"type={json.dumps(str(node['type']))}, "
                f"text={json.dumps(str(node['text']))}"
                ")"
            )
    return "\n".join(lines)


def _render_compact_json(graph: Graph) -> str:
    payload = canonical_graph_payload(graph)
    compact = {
        "n": [{"i": node["idx"], "y": node["type"], "t": node["text"]} for node in payload["nodes"]],
        "a": [
            {"c": arg["claim"], "r": arg["type"], "p": arg["premises"]}
            for arg in payload["arguments"]
        ],
    }
    return json.dumps(compact, sort_keys=True, separators=(",", ":"))


def _render_edge_sentences(graph: Graph) -> str:
    payload = canonical_graph_payload(graph)
    lines: list[str] = []
    for node in payload["nodes"]:
        lines.append(f'Node {node["idx"]} ({node["type"]}): {json.dumps(node["text"])}.')
    lines.append("")
    for argument in payload["arguments"]:
        verb = "SUPPORTS" if argument["type"] == EdgeType.SUPPORT.value else "ATTACKS"
        for premise in argument["premises"]:
            lines.append(f"Node {premise} {verb} Node {argument['claim']}.")
    return "\n".join(lines)


def _render_formal_proof(graph: Graph) -> str:
    payload = canonical_graph_payload(graph)
    nodes = {int(node["idx"]): node for node in payload["nodes"]}
    blocks: list[str] = []
    for argument in payload["arguments"]:
        claim_id = int(argument["claim"])
        premises = [int(p) for p in argument["premises"]]
        lines: list[str] = ["We have:"]
        for i, pid in enumerate(premises):
            text = str(nodes[pid]["text"])
            if i == 0:
                lines.append(f"{text} ({pid}) ")
            else:
                lines.append(f"and {text} ({pid}) ")
        lines.append("")
        premises_ref = " and ".join(f"({p})" for p in premises)
        claim_text = str(nodes.get(claim_id, {"text": ""})["text"])
        lines.append(f"From {premises_ref} => {claim_text} ({claim_id}.")
        # close the sentence properly if missing )
        if not lines[-1].endswith(")"):
            lines[-1] = lines[-1].rstrip(".") + ")."
        lines.append("")
        lines.append("The argument ends here.")
        blocks.append("\n".join(lines))

    return "\n\n".join(blocks)


def _parse_formal_proof(text: str) -> Graph:
    nodes_by_id: dict[int, Vertex] = {}
    arguments_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)
    lines = [ln.rstrip() for ln in text.splitlines()]
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i].strip()
        if not line:
            i += 1
            continue
        if line.lower().startswith("we have:"):
            i += 1
            premises: list[int] = []
            # collect premise lines until a 'From' line
            while i < n:
                cur = lines[i].strip()
                if not cur:
                    i += 1
                    continue
                if cur.startswith("From "):
                    # parse From line
                    from_line = cur
                    # extract premise ids from left side
                    left_right = re.match(r"^From\s+(.+?)\s*=>\s*(.+)\.?$", from_line)
                    if not left_right:
                        raise ValueError(f"Unsupported formal-proof From line '{from_line}'")
                    left, right = left_right.groups()
                    prem_ids = [int(m) for m in re.findall(r"\((\d+)\)", left)]
                    premises = prem_ids
                    # parse claim id and claim text from right
                    claim_match = re.match(r"^(.*)\s*\((\d+)\)\s*$", right)
                    if not claim_match:
                        raise ValueError(f"Unsupported formal-proof claim part '{right}'")
                    claim_text = claim_match.group(1).strip()
                    claim_id = int(claim_match.group(2))
                    # add claim node
                    existing = nodes_by_id.get(claim_id)
                    claim_node = Vertex(idx=claim_id, text=claim_text, type=VertexType.CLAIM)
                    if existing is None:
                        nodes_by_id[claim_id] = claim_node
                    elif existing != claim_node:
                        raise ValueError(f"Conflicting formal-proof claim id {claim_id}")
                    # add premise nodes if missing (type as ELEMENT)
                    for pid in premises:
                        if pid not in nodes_by_id:
                            # try to find textual description above
                            # search backwards for a line that ends with '(pid)'
                            found_text: str | None = None
                            for j in range(i - 1, max(-1, i - 6), -1):
                                m = re.match(rf"^(?:and\s+)?(.+?)\s*\({pid}\)\s*$", lines[j].strip())
                                if m:
                                    found_text = m.group(1).strip()
                                    break
                            nodes_by_id[pid] = Vertex(idx=pid, text=found_text or "", type=VertexType.ELEMENT)
                    arguments_by_key[(claim_id, EdgeType.SUPPORT.value)].extend(premises)
                    i += 1
                    break
                else:
                    # premise line; just move on, parsing of actual ids happens in From
                    i += 1
            continue
        i += 1

    return _graph_from_components(nodes_by_id, arguments_by_key)


def _graph_from_components(
    nodes_by_id: dict[int, Vertex],
    arguments_by_key: dict[tuple[int, str], list[int]],
) -> Graph:
    arguments = [
        Argument(claim=claim_id, premises=premises, type=EdgeType(edge_type))
        for (claim_id, edge_type), premises in sorted(arguments_by_key.items())
    ]
    return Graph(nodes=sorted(nodes_by_id.values(), key=lambda item: item.idx), arguments=arguments)


def _parse_xml(text: str) -> Graph:
    root = ET.fromstring(text)
    if root.tag != "argument":
        raise ValueError("XML graph must have <argument> as the root element")

    nodes_by_id: dict[int, Vertex] = {}
    arguments_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)

    def visit(element: ET.Element, parent_id: int | None = None) -> None:
        if element.tag not in {item.value for item in VertexType if item is not VertexType.NONE}:
            raise ValueError(f"Unsupported XML node tag '{element.tag}'")
        node_id = int(element.attrib["id"])
        node_text = element.attrib["text"]
        node_type = VertexType(element.tag)
        existing = nodes_by_id.get(node_id)
        candidate = Vertex(idx=node_id, text=node_text, type=node_type)
        if existing is None:
            nodes_by_id[node_id] = candidate
        elif existing != candidate:
            raise ValueError(f"Conflicting XML node definition for id {node_id}")

        if parent_id is not None:
            edge_type = EdgeType(element.attrib["type"])
            arguments_by_key[(parent_id, edge_type.value)].append(node_id)

        if element.attrib.get("ref") == "true":
            return
        for child in list(element):
            visit(child, node_id)

    for child in list(root):
        visit(child)

    return _graph_from_components(nodes_by_id, arguments_by_key)


def _parse_python_dsl(text: str) -> Graph:
    tree = ast.parse(text)
    nodes_by_id: dict[int, Vertex] = {}
    variable_to_id: dict[str, int] = {}
    arguments_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)
    type_map = {"Element": VertexType.ELEMENT, "Background": VertexType.BACKGROUND, "Claim": VertexType.CLAIM}

    for statement in tree.body:
        if isinstance(statement, ast.Assign):
            if len(statement.targets) != 1 or not isinstance(statement.targets[0], ast.Name):
                raise ValueError("Unsupported assignment in Python DSL")
            target = statement.targets[0].id
            if not isinstance(statement.value, ast.Call) or not isinstance(statement.value.func, ast.Name):
                raise ValueError("Unsupported constructor call in Python DSL")
            ctor_name = statement.value.func.id
            if ctor_name not in type_map:
                raise ValueError(f"Unsupported constructor '{ctor_name}' in Python DSL")
            if len(statement.value.args) != 1:
                raise ValueError("Python DSL constructors require exactly one text argument")
            text_value = ast.literal_eval(statement.value.args[0])
            if not isinstance(text_value, str):
                raise ValueError("Python DSL constructor argument must be a string")
            match = re.match(r"^(?:root_)?[a-z_]+_(\d+)$", target)
            if match is None:
                raise ValueError(f"Unsupported DSL variable name '{target}'")
            node_id = int(match.group(1))
            variable_to_id[target] = node_id
            nodes_by_id[node_id] = Vertex(idx=node_id, text=text_value, type=type_map[ctor_name])
            continue

        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call):
            call = statement.value
            if not isinstance(call.func, ast.Attribute) or not isinstance(call.func.value, ast.Name):
                raise ValueError("Unsupported DSL method call")
            claim_name = call.func.value.id
            if claim_name not in variable_to_id:
                raise ValueError(f"Unknown claim variable '{claim_name}' in Python DSL")
            method_name = call.func.attr
            if method_name not in {"supported_by", "attacked_by"}:
                raise ValueError(f"Unsupported DSL method '{method_name}'")
            edge_type = EdgeType.SUPPORT if method_name == "supported_by" else EdgeType.ATTACK
            claim_id = variable_to_id[claim_name]
            for arg in call.args:
                if not isinstance(arg, ast.Name) or arg.id not in variable_to_id:
                    raise ValueError("DSL edge arguments must be existing variables")
                arguments_by_key[(claim_id, edge_type.value)].append(variable_to_id[arg.id])

    return _graph_from_components(nodes_by_id, arguments_by_key)


def _parse_mermaid(text: str) -> Graph:
    nodes_by_id: dict[int, Vertex] = {}
    arguments_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)
    node_pattern = re.compile(r'^\s*((?:root_)?[a-z_]+)_(\d+)\["((?:[^"\\]|\\.)*)"\]\s*$')
    edge_pattern = re.compile(
        r"^\s*((?:root_)?[a-z_]+)_(\d+)\s*--\s*(support|attack)\s*-->\s*((?:root_)?[a-z_]+)_(\d+)\s*$"
    )
    type_map = {
        "element": VertexType.ELEMENT,
        "background": VertexType.BACKGROUND,
        "claim": VertexType.CLAIM,
        "root_claim": VertexType.CLAIM,
    }

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line or line == "graph BT":
            continue
        node_match = node_pattern.match(line)
        if node_match is not None:
            prefix, node_id_text, label = node_match.groups()
            node_type = type_map.get(prefix)
            if node_type is None:
                raise ValueError(f"Unsupported Mermaid node prefix '{prefix}'")
            node_id = int(node_id_text)
            nodes_by_id[node_id] = Vertex(idx=node_id, text=json.loads(f'"{label}"'), type=node_type)
            continue

        edge_match = edge_pattern.match(line)
        if edge_match is not None:
            _, premise_id_text, edge_type, _, claim_id_text = edge_match.groups()
            arguments_by_key[(int(claim_id_text), edge_type)].append(int(premise_id_text))
            continue

        raise ValueError(f"Unsupported Mermaid line '{line}'")

    return _graph_from_components(nodes_by_id, arguments_by_key)


def _parse_nested_json(text: str) -> Graph:
    payload = json.loads(text)
    roots = payload.get("roots", [])
    if not isinstance(roots, list):
        raise ValueError("Nested JSON requires roots list")
    nodes_by_id: dict[int, Vertex] = {}
    arguments_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)

    def visit(node_payload: dict[str, Any], parent_id: int | None = None, edge_type: str | None = None) -> None:
        node_id = int(node_payload["id"])
        node_type = VertexType(str(node_payload["type"]))
        node_text = str(node_payload["text"])
        candidate = Vertex(idx=node_id, type=node_type, text=node_text)
        existing = nodes_by_id.get(node_id)
        if existing is None:
            nodes_by_id[node_id] = candidate
        elif existing != candidate:
            raise ValueError(f"Conflicting nested-json node definition for id {node_id}")

        if parent_id is not None and edge_type is not None:
            arguments_by_key[(parent_id, edge_type)].append(node_id)
        if bool(node_payload.get("ref")):
            return
        for key in ("supports", "attacks"):
            children = node_payload.get(key, [])
            if not isinstance(children, list):
                continue
            rel = EdgeType.SUPPORT.value if key == "supports" else EdgeType.ATTACK.value
            for child in children:
                if isinstance(child, dict):
                    visit(child, parent_id=node_id, edge_type=rel)

    for root in roots:
        if isinstance(root, dict):
            visit(root)

    return _graph_from_components(nodes_by_id, arguments_by_key)


def _parse_edge_table(text: str) -> Graph:
    nodes_by_id: dict[int, Vertex] = {}
    arguments_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)
    section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "NODES":
            section = "nodes"
            continue
        if line == "EDGES":
            section = "edges"
            continue
        if not line.startswith("|"):
            continue
        if line.lower().startswith("| id |") or line.lower().startswith("| from |"):
            continue
        if line.startswith("| ---"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if section == "nodes" and len(cells) == 3:
            node_id = int(cells[0])
            node_type = VertexType(cells[1])
            node_text = json.loads(cells[2])
            nodes_by_id[node_id] = Vertex(idx=node_id, type=node_type, text=node_text)
            continue
        if section == "edges" and len(cells) == 3:
            premise_id = int(cells[0])
            edge_type = EdgeType(cells[1]).value
            claim_id = int(cells[2])
            arguments_by_key[(claim_id, edge_type)].append(premise_id)
    return _graph_from_components(nodes_by_id, arguments_by_key)


def _parse_facts(text: str) -> Graph:
    node_pattern = re.compile(r'^node\((\d+),\s*([a-z_]+),\s*(".*")\)\.$')
    edge_pattern = re.compile(r"^edge\((\d+),\s*([a-z_]+),\s*(\d+)\)\.$")
    nodes_by_id: dict[int, Vertex] = {}
    arguments_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        node_match = node_pattern.match(line)
        if node_match:
            node_id, node_type, node_text = node_match.groups()
            nodes_by_id[int(node_id)] = Vertex(
                idx=int(node_id),
                type=VertexType(node_type),
                text=json.loads(node_text),
            )
            continue
        edge_match = edge_pattern.match(line)
        if edge_match:
            premise_id, edge_type, claim_id = edge_match.groups()
            arguments_by_key[(int(claim_id), EdgeType(edge_type).value)].append(int(premise_id))
            continue
        raise ValueError(f"Unsupported facts line '{line}'")
    return _graph_from_components(nodes_by_id, arguments_by_key)


def _parse_claim_bundles_inline(text: str) -> Graph:
    nodes_by_id: dict[int, Vertex] = {}
    arguments_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)
    section: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "NODES":
            section = "nodes"
            continue
        if line == "CLAIMS":
            section = "claims"
            continue
        if line == "END":
            break
        if section == "nodes":
            parts = line.split("|", 3)
            if len(parts) != 4 or parts[0] != "node":
                raise ValueError(f"Unsupported claim-bundles node line '{line}'")
            node_id = int(parts[1])
            nodes_by_id[node_id] = Vertex(
                idx=node_id, type=VertexType(parts[2]), text=json.loads(parts[3])
            )
            continue
        if section == "claims":
            parts = line.split("|", 4)
            if parts[0] == "claim":
                if len(parts) != 3:
                    raise ValueError(f"Unsupported claim-bundles claim line '{line}'")
                claim_id = int(parts[1])
                claim_text = json.loads(parts[2])
                claim_node = Vertex(idx=claim_id, type=VertexType.CLAIM, text=claim_text)
                existing = nodes_by_id.get(claim_id)
                if existing is None:
                    nodes_by_id[claim_id] = claim_node
                elif existing != claim_node:
                    raise ValueError(f"Conflicting claim-bundles claim definition id {claim_id}")
                continue
            if parts[0] in {EdgeType.SUPPORT.value, EdgeType.ATTACK.value}:
                if len(parts) != 5:
                    raise ValueError(f"Unsupported claim-bundles edge line '{line}'")
                edge_type = parts[0]
                claim_id = int(parts[1])
                premise_id = int(parts[2])
                premise_type = VertexType(parts[3])
                premise_text = json.loads(parts[4])
                premise_node = Vertex(idx=premise_id, type=premise_type, text=premise_text)
                existing = nodes_by_id.get(premise_id)
                if existing is None:
                    nodes_by_id[premise_id] = premise_node
                elif existing != premise_node:
                    raise ValueError(f"Conflicting claim-bundles premise definition id {premise_id}")
                arguments_by_key[(claim_id, edge_type)].append(premise_id)
                continue
            raise ValueError(f"Unsupported claim-bundles line '{line}'")
    return _graph_from_components(nodes_by_id, arguments_by_key)


def _parse_relation_xml(text: str) -> Graph:
    root = ET.fromstring(text)
    if root.tag != "argument":
        raise ValueError("Relation XML graph must have <argument> as the root element")
    nodes_by_id: dict[int, Vertex] = {}
    arguments_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)

    def visit_node(node_element: ET.Element, parent_id: int | None = None, edge_type: str | None = None) -> None:
        if node_element.tag != "node":
            raise ValueError(f"Unsupported relation-xml tag '{node_element.tag}'")
        node_id = int(node_element.attrib["id"])
        node_type = VertexType(node_element.attrib["node_type"])
        node_text = node_element.attrib["text"]
        candidate = Vertex(idx=node_id, text=node_text, type=node_type)
        existing = nodes_by_id.get(node_id)
        if existing is None:
            nodes_by_id[node_id] = candidate
        elif existing != candidate:
            raise ValueError(f"Conflicting relation-xml node definition for id {node_id}")
        if parent_id is not None and edge_type is not None:
            arguments_by_key[(parent_id, edge_type)].append(node_id)
        if node_element.attrib.get("ref") == "true":
            return
        for relation_wrapper in list(node_element):
            if relation_wrapper.tag not in {EdgeType.SUPPORT.value, EdgeType.ATTACK.value}:
                continue
            for child_node in list(relation_wrapper):
                visit_node(child_node, parent_id=node_id, edge_type=relation_wrapper.tag)

    for child in list(root):
        visit_node(child)
    return _graph_from_components(nodes_by_id, arguments_by_key)


def _parse_inline_python_dsl(text: str) -> Graph:
    tree = ast.parse(text)
    nodes_by_id: dict[int, Vertex] = {}
    arguments_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)

    def keyword_map(call: ast.Call) -> dict[str, object]:
        result: dict[str, object] = {}
        for item in call.keywords:
            if item.arg is None:
                continue
            result[item.arg] = ast.literal_eval(item.value)
        return result

    for statement in tree.body:
        if not isinstance(statement, ast.Expr) or not isinstance(statement.value, ast.Call):
            raise ValueError("Inline Python DSL accepts only call expressions")
        call = statement.value
        if not isinstance(call.func, ast.Name):
            raise ValueError("Inline Python DSL call target must be a function name")
        kwargs = keyword_map(call)
        if call.func.id == "node":
            node = Vertex(
                idx=int(kwargs["id"]),
                type=VertexType(str(kwargs["type"])),
                text=str(kwargs["text"]),
            )
            existing = nodes_by_id.get(node.idx)
            if existing is None:
                nodes_by_id[node.idx] = node
            elif existing != node:
                raise ValueError(f"Conflicting node definition for id {node.idx}")
            continue
        if call.func.id != "claim":
            raise ValueError(f"Unsupported inline Python DSL function '{call.func.id}'")
        claim_id = int(kwargs["id"])
        claim_node = Vertex(idx=claim_id, type=VertexType.CLAIM, text=str(kwargs["text"]))
        existing = nodes_by_id.get(claim_id)
        if existing is None:
            nodes_by_id[claim_id] = claim_node
        elif existing != claim_node:
            raise ValueError(f"Conflicting claim definition for id {claim_id}")

        for edge_name in (EdgeType.SUPPORT.value, EdgeType.ATTACK.value):
            raw_items = kwargs.get(f"{edge_name}s", [])
            if not isinstance(raw_items, list):
                continue
            for raw_item in raw_items:
                if not isinstance(raw_item, (list, tuple)) or len(raw_item) != 3:
                    raise ValueError("Inline Python DSL supports/attacks entries must be 3-tuples")
                premise_id = int(raw_item[0])
                premise_type = VertexType(str(raw_item[1]))
                premise_text = str(raw_item[2])
                premise_node = Vertex(idx=premise_id, type=premise_type, text=premise_text)
                premise_existing = nodes_by_id.get(premise_id)
                if premise_existing is None:
                    nodes_by_id[premise_id] = premise_node
                elif premise_existing != premise_node:
                    raise ValueError(f"Conflicting premise definition for id {premise_id}")
                arguments_by_key[(claim_id, edge_name)].append(premise_id)
        continue

    return _graph_from_components(nodes_by_id, arguments_by_key)


def _parse_compact_json(text: str) -> Graph:
    payload = json.loads(text)
    raw_nodes = payload.get("n", [])
    raw_arguments = payload.get("a", [])
    if not isinstance(raw_nodes, list) or not isinstance(raw_arguments, list):
        raise ValueError("Compact JSON payload is invalid")
    nodes = [
        Vertex(idx=int(node["i"]), type=VertexType(str(node["y"])), text=str(node["t"]))
        for node in raw_nodes
    ]
    arguments = [
        Argument(
            claim=int(argument["c"]),
            premises=[int(item) for item in argument.get("p", [])],
            type=EdgeType(str(argument["r"])),
        )
        for argument in raw_arguments
    ]
    return Graph(nodes=nodes, arguments=arguments)


def _parse_edge_sentences(text: str) -> Graph:
    node_pattern = re.compile(r'^Node (\d+) \(([a-z_]+)\): ("(?:[^"\\]|\\.)*")\.$')
    edge_pattern = re.compile(r"^Node (\d+) (SUPPORTS|ATTACKS) Node (\d+)\.$")
    nodes_by_id: dict[int, Vertex] = {}
    arguments_by_key: dict[tuple[int, str], list[int]] = defaultdict(list)
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        node_match = node_pattern.match(line)
        if node_match:
            node_id, node_type, node_text = node_match.groups()
            nodes_by_id[int(node_id)] = Vertex(
                idx=int(node_id),
                type=VertexType(node_type),
                text=json.loads(node_text),
            )
            continue
        edge_match = edge_pattern.match(line)
        if edge_match:
            premise_id, rel, claim_id = edge_match.groups()
            edge_type = EdgeType.SUPPORT.value if rel == "SUPPORTS" else EdgeType.ATTACK.value
            arguments_by_key[(int(claim_id), edge_type)].append(int(premise_id))
            continue
        raise ValueError(f"Unsupported edge-sentences line '{line}'")
    return _graph_from_components(nodes_by_id, arguments_by_key)
