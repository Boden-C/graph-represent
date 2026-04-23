from __future__ import annotations

from pydantic import BaseModel

from graph_represent.processors.base import Processor, ProcessorContext


class RemapJsonKeys(Processor):
    def process(self, input_data: BaseModel, context: ProcessorContext) -> BaseModel:
        del context
        payload = input_data.model_dump()
        mapping = {
            str(key): str(value) for key, value in dict(self.config.get("mapping", {})).items()
        }
        remapped = {mapping.get(key, key): value for key, value in payload.items()}
        return self.output_type.model_validate(remapped)
