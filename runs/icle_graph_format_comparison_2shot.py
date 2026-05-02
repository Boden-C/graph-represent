from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import networkx as nx

from graph_represent.dataloaders.icle_essays import IcleEssayDataLoader
from graph_represent.format_suite import COMPARISON_FORMATS
from graph_represent.graph_formats import GraphTextFormat, fenced_graph_text, render_graph
from graph_represent.models import GEMMA3_27B
from graph_represent.processors.clean_graph import CleanGraph
from graph_represent.processors.model_inference import ModelInference
from graph_represent.types.chat import ChatMessage, ChatMessagesPayload, TextContentPart
from graph_represent.types.corpus import IcleEssaySample
from graph_represent.types.graph import Graph
from graph_represent.types.pipeline import RetryPolicyConfig
from graph_represent.types.quality import (
    ArgumentQualitySampleResult,
    ArgumentQualityScores,
    ArgumentQualityVariantResult,
)
from graph_represent.utils.files import atomic_write_text
from graph_represent.workflow import ScriptWorkflow

REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "icle"
ESSAYS_PATH = CORPUS_ROOT / "essays" / "icle_essays_normalized.json"
ANSWERS_PATH = CORPUS_ROOT / "answers" / "quality_scores.json"
EXEMPLARS_PATH = CORPUS_ROOT / "datasets" / "few_shot_exemplars.json"
GRAPH_PROMPT_PATH = REPO_ROOT / "graph_represent" / "prompts" / "IcleArgumentGraphByModel__EssayByModel.md"
SCORE_PROMPT_PATH = REPO_ROOT / "graph_represent" / "prompts" / "IcleStrengthOfArgumentByModel__GraphByModel.md"
FEW_SHOT_PREFIX_PATH = REPO_ROOT / "graph_represent" / "prompts" / "IcleFewShotPrefix__StrengthOfArgument.md"
MODEL = GEMMA3_27B


def _load_score_module():
    path = CORPUS_ROOT / "score_outputs.py"
    spec = importlib.util.spec_from_file_location("icle_score_outputs", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _parse_target_formats() -> list[GraphTextFormat]:
    raw = os.getenv("GRAPH_REPRESENT_FORMATS")
    if raw is None or not raw.strip():
        return list(COMPARISON_FORMATS)
    lowered = raw.strip().lower()
    if lowered == "all":
        return list(COMPARISON_FORMATS)
    values = [item.strip() for item in raw.split(",") if item.strip()]
    formats = [GraphTextFormat(value) for value in values]
    if not formats:
        raise ValueError("GRAPH_REPRESENT_FORMATS did not resolve to any formats")
    return formats


def _sample_seed() -> int | None:
    raw = os.getenv("GRAPH_REPRESENT_SAMPLE_SEED")
    if raw is None or not raw.strip():
        return None
    return int(raw)


def _few_shot_mode() -> str:
    return (os.getenv("GRAPH_REPRESENT_FEW_SHOT_MODE") or "on").strip().lower()


def _exclude_few_shot_ids() -> bool:
    raw = (os.getenv("GRAPH_REPRESENT_EXCLUDE_FEW_SHOT_IDS") or "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _load_exemplar_ids(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    ids = payload.get("item_ids", [])
    if not isinstance(ids, list):
        raise ValueError(f"Invalid exemplar manifest: {path}")
    return [str(item) for item in ids]


def _exemplar_manifest_path() -> Path:
    raw = os.getenv("GRAPH_REPRESENT_EXEMPLARS_PATH")
    if raw is None or not raw.strip():
        return EXEMPLARS_PATH
    return Path(raw)


def _format_few_shot_example(sample: IcleEssaySample) -> str:
    raw_score = sample.raw_scores["strength_of_argument"]
    return (
        f"ID: {sample.id}\n"
        f"Prompt:\n{sample.prompt or ''}\n\n"
        f"Essay:\n{sample.essay}\n\n"
        f"Gold strength_of_argument (raw 1.0-4.0): {raw_score:.1f}\n"
    )


def _build_few_shot_prefix(loader: IcleEssayDataLoader, exemplar_ids: list[str]) -> str:
    template = FEW_SHOT_PREFIX_PATH.read_text(encoding="utf-8")
    examples: list[str] = []
    for item_id in exemplar_ids:
        sample = loader.get_item(item_id)
        if sample is None:
            raise ValueError(f"Few-shot exemplar id '{item_id}' not found in ICLE loader")
        examples.append(_format_few_shot_example(sample))
    return template.replace("{few_shot_examples}", "\n\n---\n\n".join(examples))


def _graph_messages(sample: IcleEssaySample) -> ChatMessagesPayload:
    text = (
        f"Essay prompt:\n{sample.prompt or '(none)'}\n\n"
        f"Essay text:\n{sample.essay}\n"
    )
    return ChatMessagesPayload(
        messages=[ChatMessage(role="user", content=[TextContentPart(text=text)])]
    )


def _score_messages(
    sample: IcleEssaySample,
    format_name: GraphTextFormat,
    graph: Graph,
    few_shot_prefix: str | None,
) -> tuple[ChatMessagesPayload, int, int]:
    graph_text = render_graph(graph, format_name)
    text = fenced_graph_text(graph_text, format_name)
    if few_shot_prefix is not None:
        text = f"{few_shot_prefix}\n\nNow score this graph:\n\n{text}"
    return (
        ChatMessagesPayload(messages=[ChatMessage(role="user", content=[TextContentPart(text=text)])]),
        len(graph_text),
        max(1, len(graph_text.splitlines())),
    )


def _is_acyclic(graph: Graph) -> bool:
    return nx.is_directed_acyclic_graph(graph.to_networkx())


def build_workflow() -> ScriptWorkflow:
    target_formats = _parse_target_formats()
    seed = _sample_seed()
    few_shot_mode = _few_shot_mode()
    exemplar_manifest_path = _exemplar_manifest_path()
    exemplar_ids = _load_exemplar_ids(exemplar_manifest_path)
    excluded_ids = set(exemplar_ids) if _exclude_few_shot_ids() else set()

    loader = IcleEssayDataLoader(
        essays_path=ESSAYS_PATH,
        answers_path=ANSWERS_PATH,
        score_name="strength_of_argument",
        sample_seed=seed,
        excluded_ids=excluded_ids,
    )
    few_shot_prefix = None
    if few_shot_mode != "off":
        few_shot_prefix = _build_few_shot_prefix(loader, exemplar_ids)

    build_graph = ModelInference(
        name="infer_graph__icle",
        config={
            "provider": MODEL.provider,
            "base_urls": MODEL.base_urls,
            "model": MODEL.name,
            "system_prompt_file": str(GRAPH_PROMPT_PATH),
            "temperature": 0.0,
            "max_tokens": 8192,
        },
        input_type=ChatMessagesPayload,
        output_type=Graph,
        retry=RetryPolicyConfig(),
    )
    clean_graph = CleanGraph(
        name="clean_graph__icle",
        config={
            "normalize_indices": True,
            "merge_duplicate_nodes": True,
        },
        input_type=Graph,
        output_type=Graph,
        retry=RetryPolicyConfig(),
    )
    infer_by_format = {
        format_name: ModelInference(
            name=f"infer_quality__{format_name.value}",
            config={
                "provider": MODEL.provider,
                "base_urls": MODEL.base_urls,
                "model": MODEL.name,
                "system_prompt_file": str(SCORE_PROMPT_PATH),
                "temperature": 0.0,
                "max_tokens": 512,
            },
            input_type=ChatMessagesPayload,
            output_type=ArgumentQualityScores,
            retry=RetryPolicyConfig(),
        )
        for format_name in target_formats
    }

    def process_item(item, runtime, context):
        sample = IcleEssaySample.model_validate(item.model_dump())
        graph_messages = _graph_messages(sample)
        graph = runtime.run_stage(
            stage_index=0,
            stage_name="infer_graph__icle",
            processor=build_graph,
            input_data=graph_messages,
            context=context,
        )
        graph = runtime.run_stage(
            stage_index=1,
            stage_name="clean_graph__icle",
            processor=clean_graph,
            input_data=Graph.model_validate(graph.model_dump()),
            context=context,
        )
        cleaned_graph = Graph.model_validate(graph.model_dump())
        if not _is_acyclic(cleaned_graph):
            raise ValueError(f"Graph for '{sample.id}' is cyclic after cleaning")

        variants: list[ArgumentQualityVariantResult] = []
        for index, format_name in enumerate(target_formats):
            messages, char_count, line_count = _score_messages(
                sample,
                format_name,
                cleaned_graph,
                few_shot_prefix,
            )
            scores = runtime.run_stage(
                stage_index=index + 2,
                stage_name=f"infer_quality__{format_name.value}",
                processor=infer_by_format[format_name],
                input_data=messages,
                context=context,
                save_output=False,
            )
            variants.append(
                ArgumentQualityVariantResult(
                    item_id=sample.id,
                    version_name="icle_generated",
                    input_mode=format_name.value,
                    model_name=MODEL.name,
                    scores=ArgumentQualityScores.model_validate(scores.model_dump()),
                    gold_scores={"strength_of_argument": sample.scores["strength_of_argument"]},
                    gold_raw_scores={"strength_of_argument": sample.raw_scores["strength_of_argument"]},
                    input_char_count=char_count,
                    input_line_count=line_count,
                )
            )

        return ArgumentQualitySampleResult(
            item_id=sample.id,
            gold_scores={"strength_of_argument": sample.scores["strength_of_argument"]},
            gold_raw_scores={"strength_of_argument": sample.raw_scores["strength_of_argument"]},
            variants=variants,
        )

    def finalize_run(runtime) -> None:
        eval_ids = loader.last_selected_ids
        overlap = sorted(set(eval_ids).intersection(exemplar_ids))
        if overlap:
            raise ValueError(f"Few-shot leak detected. Overlapping ids: {', '.join(overlap)}")
        run_config = {
            "corpus": "icle",
            "graph_path_mode": "per_run_generated",
            "primary_metric": "qwk",
            "score_name": "strength_of_argument",
            "sample_seed": seed,
            "eval_item_ids": eval_ids,
            "few_shot_item_ids": exemplar_ids,
            "few_shot_mode": few_shot_mode,
            "target_formats": [item.value for item in target_formats],
            "graph_model": MODEL.name,
            "score_model": MODEL.name,
            "graph_prompt_file": str(GRAPH_PROMPT_PATH),
            "score_prompt_file": str(SCORE_PROMPT_PATH),
            "few_shot_prefix_file": str(FEW_SHOT_PREFIX_PATH),
            "exemplar_manifest": str(exemplar_manifest_path),
        }
        atomic_write_text(
            runtime.output_store.output_root / "run_config.json",
            json.dumps(run_config, indent=2),
        )
        _load_score_module().score_run(runtime.output_store.run_root)

    return ScriptWorkflow(
        name="icle_graph_format_comparison_2shot",
        loader=loader,
        final_stage_name="quality_outputs",
        final_output_type=ArgumentQualitySampleResult,
        process_item=process_item,
        finalize_run=finalize_run,
    )
