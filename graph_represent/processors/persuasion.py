from __future__ import annotations

import math
from collections import defaultdict
from itertools import pairwise

from graph_represent.graph_formats import GraphTextFormat, fenced_graph_text, render_graph
from graph_represent.processors.base import Processor, ProcessorContext
from graph_represent.types.chat import (
    ChatMessage,
    ChatMessagesPayload,
    ContentPart,
    ImageContentPart,
    TextContentPart,
)
from graph_represent.types.dataset import (
    ArgumentGraphData,
    ArgumentGraphTextData,
    JsonObject,
    PersuasionSample,
)
from graph_represent.types.persuasion import (
    TECHNIQUES_TASK3,
    TECHNIQUES_TASK3_SET,
    PersuasionAggregateScores,
    PersuasionItemResult,
    PersuasionLabels,
    PersuasionPredictionRecord,
    PersuasionTechniqueScores,
    PersuasionThresholdEvaluationSummary,
    PersuasionThresholdOptimizationInput,
    PersuasionThresholdOptimizationResult,
    PersuasionThresholdPredictions,
    PersuasionThresholdSampleResult,
    PersuasionThresholdSpec,
    PersuasionThresholdVariantResult,
    normalize_technique_name,
)


class BuildPersuasionMessagesFromImage(
    Processor[PersuasionSample, ChatMessagesPayload, PersuasionSample]
):
    def validate_types(self) -> None:
        if (
            not issubclass(self.input_type, PersuasionSample)
            or self.output_type is not ChatMessagesPayload
        ):
            raise ValueError(
                "BuildPersuasionMessagesFromImage requires PersuasionSample -> ChatMessagesPayload"
            )

    def process(
        self,
        input_data: PersuasionSample,
        context: ProcessorContext[PersuasionSample],
    ) -> ChatMessagesPayload:
        del context
        if input_data.image_path is None:
            raise ValueError("Persuasion sample is missing image_path")

        content: list[ContentPart] = [ImageContentPart(image_path=input_data.image_path)]
        prompt_text = str(self.config.get("user_text", "")).strip()
        if prompt_text:
            content.append(TextContentPart(text=prompt_text))
        return ChatMessagesPayload(messages=[ChatMessage(role="user", content=content)])


class BuildPersuasionMessagesFromGraph(
    Processor[ArgumentGraphData | ArgumentGraphTextData, ChatMessagesPayload, PersuasionSample]
):
    def validate_types(self) -> None:
        valid_input_types = {ArgumentGraphData, ArgumentGraphTextData}
        if self.input_type not in valid_input_types or self.output_type is not ChatMessagesPayload:
            raise ValueError(
                "BuildPersuasionMessagesFromGraph requires ArgumentGraphData|ArgumentGraphTextData -> ChatMessagesPayload"
            )

    def process(
        self,
        input_data: ArgumentGraphData | ArgumentGraphTextData,
        context: ProcessorContext[PersuasionSample],
    ) -> ChatMessagesPayload:
        del context
        prompt_text = str(self.config.get("user_text", "")).strip()
        if isinstance(input_data, ArgumentGraphData):
            graph_text = render_graph(input_data.graph, GraphTextFormat.JSON)
            message_text = fenced_graph_text(graph_text, GraphTextFormat.JSON)
        else:
            graph_format = GraphTextFormat(input_data.graph_format)
            message_text = fenced_graph_text(input_data.graph_text, graph_format)
        if prompt_text:
            message_text = f"{prompt_text}\n\n{message_text}"
        return ChatMessagesPayload(
            messages=[ChatMessage(role="user", content=[TextContentPart(text=message_text)])]
        )


class ScorePersuasionLabels(Processor[PersuasionLabels, PersuasionItemResult, PersuasionSample]):
    def validate_types(self) -> None:
        if self.input_type is not PersuasionLabels or self.output_type is not PersuasionItemResult:
            raise ValueError(
                "ScorePersuasionLabels requires PersuasionLabels -> PersuasionItemResult"
            )

    def process(
        self,
        input_data: PersuasionLabels,
        context: ProcessorContext[PersuasionSample],
    ) -> PersuasionItemResult:
        predicted = PersuasionLabels.model_validate(input_data.model_dump())
        sample = context.source_item
        gold = sample.gold_labels
        predicted_set = {normalize_technique_name(label) for label in predicted.labels}
        gold_set = (
            {normalize_technique_name(label) for label in gold.labels}
            if gold is not None
            else set()
        )

        tp_labels: list[str] = []
        fp_labels: list[str] = []
        tn_labels: list[str] = []
        fn_labels: list[str] = []

        for label in TECHNIQUES_TASK3:
            in_pred = label in predicted_set
            in_gold = label in gold_set
            if in_pred and in_gold:
                tp_labels.append(label)
            elif in_pred and not in_gold:
                fp_labels.append(label)
            elif not in_pred and in_gold:
                fn_labels.append(label)
            else:
                tn_labels.append(label)

        return PersuasionItemResult(
            item_id=sample.id,
            predicted=predicted,
            gold=gold,
            tp_labels=tp_labels,
            fp_labels=fp_labels,
            tn_labels=tn_labels,
            fn_labels=fn_labels,
        )


def compute_persuasion_aggregate(results: list[PersuasionItemResult]) -> PersuasionAggregateScores:
    invalid_labels: set[str] = set()
    per_label_tp: dict[str, int] = {label: 0 for label in TECHNIQUES_TASK3}
    per_label_fp: dict[str, int] = {label: 0 for label in TECHNIQUES_TASK3}
    per_label_tn: dict[str, int] = {label: 0 for label in TECHNIQUES_TASK3}
    per_label_fn: dict[str, int] = {label: 0 for label in TECHNIQUES_TASK3}

    for result in results:
        if result.gold is None:
            continue
        predicted_set = {normalize_technique_name(label) for label in result.predicted.labels}
        gold_set = {normalize_technique_name(label) for label in result.gold.labels}
        for label in predicted_set:
            if label not in TECHNIQUES_TASK3_SET:
                invalid_labels.add(label)
        for label in TECHNIQUES_TASK3:
            in_pred = label in predicted_set
            in_gold = label in gold_set
            if in_pred and in_gold:
                per_label_tp[label] += 1
            elif in_pred and not in_gold:
                per_label_fp[label] += 1
            elif not in_pred and in_gold:
                per_label_fn[label] += 1
            else:
                per_label_tn[label] += 1

    def safe_div(num: float, den: float) -> float:
        return num / den if den > 0 else 1.0

    def f1(precision: float, recall: float) -> float:
        return 2 * precision * recall / (precision + recall) if precision + recall > 0 else 1.0

    total_tp = sum(per_label_tp.values())
    total_fp = sum(per_label_fp.values())
    total_tn = sum(per_label_tn.values())
    total_fn = sum(per_label_fn.values())
    micro_precision = safe_div(total_tp, total_tp + total_fp)
    micro_recall = safe_div(total_tp, total_tp + total_fn)
    micro_f1 = f1(micro_precision, micro_recall)

    macro_precision = 0.0
    macro_recall = 0.0
    macro_f1 = 0.0
    for label in TECHNIQUES_TASK3:
        precision = safe_div(per_label_tp[label], per_label_tp[label] + per_label_fp[label])
        recall = safe_div(per_label_tp[label], per_label_tp[label] + per_label_fn[label])
        macro_precision += precision
        macro_recall += recall
        macro_f1 += f1(precision, recall)

    label_count = len(TECHNIQUES_TASK3)
    return PersuasionAggregateScores(
        micro_precision=round(micro_precision, 5),
        micro_recall=round(micro_recall, 5),
        micro_f1=round(micro_f1, 5),
        macro_precision=round(macro_precision / label_count, 5),
        macro_recall=round(macro_recall / label_count, 5),
        macro_f1=round(macro_f1 / label_count, 5),
        tp=total_tp,
        fp=total_fp,
        tn=total_tn,
        fn=total_fn,
        invalid_labels=sorted(invalid_labels),
    )


def compute_semeval_f1(
    predicted_label_sets: list[list[str]],
    gold_label_sets: list[list[str]],
) -> tuple[float, float]:
    if len(predicted_label_sets) != len(gold_label_sets):
        raise ValueError("Predicted and gold label sets must have the same length")

    per_label_f1: list[float] = []
    total_tp = 0
    total_fp = 0
    total_fn = 0
    for label in TECHNIQUES_TASK3:
        tp = fp = fn = 0
        for predicted_labels, gold_labels in zip(
            predicted_label_sets, gold_label_sets, strict=True
        ):
            in_predicted = label in {normalize_technique_name(item) for item in predicted_labels}
            in_gold = label in {normalize_technique_name(item) for item in gold_labels}
            if in_predicted and in_gold:
                tp += 1
            elif in_predicted and not in_gold:
                fp += 1
            elif not in_predicted and in_gold:
                fn += 1
        total_tp += tp
        total_fp += fp
        total_fn += fn
        per_label_f1.append(_binary_f1(tp, fp, fn))

    macro_f1 = sum(per_label_f1) / len(per_label_f1)
    micro_f1 = _binary_f1(total_tp, total_fp, total_fn)
    return float(macro_f1), float(micro_f1)


def _binary_f1(tp: int, fp: int, fn: int) -> float:
    if tp + fp == 0 and tp + fn == 0:
        return 1.0
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def optimize_label_threshold(scores: list[float], gold_binary: list[int]) -> tuple[float, float]:
    if len(scores) != len(gold_binary):
        raise ValueError("Scores and gold labels must have the same length")
    normalized_scores = [max(0.0, min(1.0, float(score))) for score in scores]
    unique_scores = sorted(set(normalized_scores))
    candidates: set[float] = {0.0, math.nextafter(1.0, 2.0)}
    candidates.update(unique_scores)
    candidates.update((left + right) / 2.0 for left, right in pairwise(unique_scores))

    best_threshold = 0.0
    best_f1 = -1.0
    for threshold in sorted(candidates):
        predicted = [1 if score >= threshold else 0 for score in normalized_scores]
        tp = sum(1 for gold, pred in zip(gold_binary, predicted, strict=True) if gold and pred)
        fp = sum(1 for gold, pred in zip(gold_binary, predicted, strict=True) if not gold and pred)
        fn = sum(1 for gold, pred in zip(gold_binary, predicted, strict=True) if gold and not pred)
        current_f1 = _binary_f1(tp, fp, fn)
        if current_f1 > best_f1:
            best_threshold = threshold
            best_f1 = current_f1
    return best_threshold, best_f1


def threshold_scores_to_labels(
    scores: PersuasionTechniqueScores,
    thresholds: dict[str, float],
) -> PersuasionLabels:
    reasons: dict[str, str | None] = {}
    for label in TECHNIQUES_TASK3:
        score = scores.scores.get(label, 0.0)
        threshold = thresholds.get(label, 0.0)
        reasons[label] = (
            f"score={score:.6f}; threshold={threshold:.6f}" if score >= threshold else None
        )
    return PersuasionLabels(reasons=reasons)


class OptimizePersuasionThresholds(
    Processor[
        PersuasionThresholdOptimizationInput,
        PersuasionThresholdOptimizationResult,
        JsonObject,
    ]
):
    def validate_types(self) -> None:
        if (
            self.input_type is not PersuasionThresholdOptimizationInput
            or self.output_type is not PersuasionThresholdOptimizationResult
        ):
            raise ValueError(
                "OptimizePersuasionThresholds requires "
                "PersuasionThresholdOptimizationInput -> PersuasionThresholdOptimizationResult"
            )

    def process(
        self,
        input_data: PersuasionThresholdOptimizationInput,
        context: ProcessorContext[JsonObject],
    ) -> PersuasionThresholdOptimizationResult:
        del context
        grouped_results: dict[tuple[str, str], list[PersuasionThresholdVariantResult]] = (
            defaultdict(list)
        )
        for sample in input_data.samples:
            sample_result = PersuasionThresholdSampleResult.model_validate(sample.model_dump())
            for variant in sample_result.variants:
                grouped_results[(variant.version_name, variant.input_mode)].append(variant)

        threshold_specs: list[PersuasionThresholdSpec] = []
        summaries: list[PersuasionThresholdEvaluationSummary] = []
        predictions: list[PersuasionThresholdPredictions] = []

        for version_name, input_mode in sorted(grouped_results):
            variants = sorted(
                grouped_results[(version_name, input_mode)], key=lambda item: item.item_id
            )
            thresholds: dict[str, float] = {}
            label_f1: dict[str, float] = {}

            for label in TECHNIQUES_TASK3:
                label_scores = [variant.scores.scores[label] for variant in variants]
                gold_binary = [
                    1
                    if variant.gold is not None
                    and label in {normalize_technique_name(value) for value in variant.gold.labels}
                    else 0
                    for variant in variants
                ]
                threshold, label_score_f1 = optimize_label_threshold(label_scores, gold_binary)
                thresholds[label] = threshold
                label_f1[label] = round(label_score_f1, 5)

            predicted_records: list[PersuasionPredictionRecord] = []
            predicted_sets: list[list[str]] = []
            gold_sets: list[list[str]] = []
            for variant in variants:
                predicted_labels = threshold_scores_to_labels(variant.scores, thresholds)
                predicted_records.append(
                    PersuasionPredictionRecord(
                        item_id=variant.item_id, labels=predicted_labels.labels
                    )
                )
                predicted_sets.append(predicted_labels.labels)
                gold_sets.append(variant.gold.labels if variant.gold is not None else [])

            macro_f1, micro_f1 = compute_semeval_f1(predicted_sets, gold_sets)
            threshold_specs.append(
                PersuasionThresholdSpec(
                    version_name=version_name,
                    input_mode=input_mode,
                    thresholds=thresholds,
                    label_f1=label_f1,
                )
            )
            summaries.append(
                PersuasionThresholdEvaluationSummary(
                    version_name=version_name,
                    input_mode=input_mode,
                    micro_f1=round(micro_f1, 5),
                    macro_f1=round(macro_f1, 5),
                    item_count=len(variants),
                )
            )
            predictions.append(
                PersuasionThresholdPredictions(
                    version_name=version_name,
                    input_mode=input_mode,
                    predictions=predicted_records,
                )
            )

        return PersuasionThresholdOptimizationResult(
            thresholds=threshold_specs,
            summaries=summaries,
            predictions=predictions,
        )
