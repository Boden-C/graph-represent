from graph_represent.processors.clean_graph import CleanGraph
from graph_represent.processors.model_inference import ModelInference
from graph_represent.processors.persuasion import (
    BuildPersuasionMessagesFromGraph,
    BuildPersuasionMessagesFromImage,
    OptimizePersuasionThresholds,
    ScorePersuasionLabels,
)
from graph_represent.processors.remap_json_keys import RemapJsonKeys
from graph_represent.registry import register_processor

register_processor("ModelInference")(ModelInference)
register_processor("RemapJsonKeys")(RemapJsonKeys)
register_processor("CleanGraph")(CleanGraph)
register_processor("BuildPersuasionMessagesFromGraph")(BuildPersuasionMessagesFromGraph)
register_processor("BuildPersuasionMessagesFromImage")(BuildPersuasionMessagesFromImage)
register_processor("OptimizePersuasionThresholds")(OptimizePersuasionThresholds)
register_processor("ScorePersuasionLabels")(ScorePersuasionLabels)

__all__ = [
    "BuildPersuasionMessagesFromGraph",
    "BuildPersuasionMessagesFromImage",
    "CleanGraph",
    "ModelInference",
    "OptimizePersuasionThresholds",
    "RemapJsonKeys",
    "ScorePersuasionLabels",
]
