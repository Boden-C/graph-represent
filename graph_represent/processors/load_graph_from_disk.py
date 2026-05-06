from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from graph_represent.processors.base import Processor, ProcessorContext
from graph_represent.types.corpus import IcleEssaySample
from graph_represent.types.graph import Graph


class LoadGraphFromDisk(Processor[IcleEssaySample, Graph, IcleEssaySample]):
    def validate_types(self) -> None:
        if self.input_type is not IcleEssaySample:
            raise ValueError("LoadGraphFromDisk requires input_type IcleEssaySample")
        if self.output_type is not Graph:
            raise ValueError("LoadGraphFromDisk requires output_type Graph")

    def process(self, input_data: BaseModel, context: ProcessorContext[IcleEssaySample]) -> Graph:
        graphs_dir_raw = self.config.get("graphs_dir")
        if graphs_dir_raw is None or not str(graphs_dir_raw).strip():
            raise ValueError("LoadGraphFromDisk requires config['graphs_dir']")
        graphs_dir = Path(str(graphs_dir_raw))
        graph_path = graphs_dir / f"{context.item_id}.json"
        if not graph_path.exists():
            raise FileNotFoundError(f"Missing graph JSON for '{context.item_id}': {graph_path}")
        return Graph.model_validate_json(graph_path.read_text(encoding="utf-8"))
