from __future__ import annotations

import importlib.util
from pathlib import Path

from graph_represent.dataloaders.corpus_graphs import CorpusGraphDataLoader
from graph_represent.format_suite import COMPARISON_FORMATS
from graph_represent.graph_formats import GraphTextFormat, fenced_graph_text, render_graph
from graph_represent.models import GEMMA3_27B
from graph_represent.processors.model_inference import ModelInference
from graph_represent.types.chat import ChatMessage, ChatMessagesPayload, TextContentPart
from graph_represent.types.corpus import CorpusGraphSample
from graph_represent.types.persuasion import (
    PersuasionLabels,
    PersuasionTechniqueScores,
    PersuasionThresholdSampleResult,
    PersuasionThresholdVariantResult,
)
from graph_represent.types.pipeline import RetryPolicyConfig
from graph_represent.workflow import ScriptWorkflow

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "memeargs"
GRAPH_PATH = CORPUS_ROOT / "graphs" / "memeargs_normalized.json"
ANSWERS_PATH = CORPUS_ROOT / "answers" / "labels.json"
DATASET_PATH = CORPUS_ROOT / "datasets" / "dev_set.json"
PROMPT_PATH = REPO_ROOT / "graph_represent" / "prompts" / "PersuasionScoresByModel__GraphByModel.md"
MODEL = GEMMA3_27B
TARGET_FORMATS = list(COMPARISON_FORMATS)


def _load_score_module():
    path = CORPUS_ROOT / "score_outputs.py"
    spec = importlib.util.spec_from_file_location("memeargs_score_outputs", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _messages_for_graph(sample: CorpusGraphSample, format_name: GraphTextFormat) -> tuple[ChatMessagesPayload, int, int]:
    graph_text = render_graph(sample.graph, format_name)
    text = fenced_graph_text(graph_text, format_name)
    return (
        ChatMessagesPayload(messages=[ChatMessage(role="user", content=[TextContentPart(text=text)])]),
        len(graph_text),
        max(1, len(graph_text.splitlines())),
    )


def build_workflow() -> ScriptWorkflow:
    loader = CorpusGraphDataLoader(
        corpus="memeargs",
        graph_path=GRAPH_PATH,
        graph_version="memeargs_normalized",
        answers_path=ANSWERS_PATH,
        dataset_path=DATASET_PATH,
    )
    infer_by_format = {
        format_name: ModelInference(
            name=f"infer_scores__{format_name.value}",
            config={
                "provider": MODEL.provider,
                "base_urls": MODEL.base_urls,
                "model": MODEL.name,
                "system_prompt_file": str(PROMPT_PATH),
                "temperature": 0.0,
                "max_tokens": 512,
            },
            input_type=ChatMessagesPayload,
            output_type=PersuasionTechniqueScores,
            retry=RetryPolicyConfig(),
        )
        for format_name in TARGET_FORMATS
    }

    def process_item(item, runtime, context):
        sample = CorpusGraphSample.model_validate(item.model_dump())
        labels = sample.gold.get("labels", []) if sample.gold else []
        gold = PersuasionLabels(reasons={str(label): "gold" for label in labels})
        gold_split = str(sample.gold.get("split")) if isinstance(sample.gold, dict) and sample.gold.get("split") else None
        variants: list[PersuasionThresholdVariantResult] = []
        for index, format_name in enumerate(TARGET_FORMATS):
            messages, char_count, line_count = _messages_for_graph(sample, format_name)
            scores = runtime.run_stage(
                stage_index=index,
                stage_name=f"infer_scores__{format_name.value}",
                processor=infer_by_format[format_name],
                input_data=messages,
                context=context,
                save_output=False,
            )
            variants.append(
                PersuasionThresholdVariantResult(
                    item_id=sample.id,
                    version_name=sample.graph_version,
                    input_mode=format_name.value,
                    model_name=MODEL.name,
                    scores=PersuasionTechniqueScores.model_validate(scores.model_dump()),
                    gold=gold,
                    gold_split=gold_split,
                    input_char_count=char_count,
                    input_line_count=line_count,
                )
            )
        return PersuasionThresholdSampleResult(item_id=sample.id, gold=gold, variants=variants)

    def finalize_run(runtime) -> None:
        _load_score_module().score_run(runtime.output_store.run_root)

    return ScriptWorkflow(
        name="memeargs_graph_format_comparison",
        loader=loader,
        final_stage_name="threshold_outputs",
        final_output_type=PersuasionThresholdSampleResult,
        process_item=process_item,
        finalize_run=finalize_run,
    )
