from __future__ import annotations

import argparse
import importlib.util
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Sequence, cast

from pydantic import BaseModel

import graph_represent.dataloaders
import graph_represent.processors
import graph_represent.types  # noqa: F401
from graph_represent.dataloaders.base import DataLoader
from graph_represent.processors.base import Processor, ProcessorContext
from graph_represent.registry import dataloader_registry, processor_registry, type_registry
from graph_represent.types.pipeline import JsonPipelineSpec, ProcessorStageSpec
from graph_represent.utils.progress import ProgressReporter
from graph_represent.workflow import ScriptRuntime, ScriptWorkflow

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = REPO_ROOT / "output"
CACHE_ROOT = OUTPUT_ROOT / "cache" / "inference"
RUNS_ROOT = REPO_ROOT / "runs"


def _default_runname() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _load_script_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(f"graph_represent_script_{path.stem}", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load script '{path}'")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _resolve_task_path(task: str) -> Path:
    raw = Path(task)
    if raw.exists():
        return raw.resolve()
    for suffix in (".json", ".py"):
        candidate = (RUNS_ROOT / f"{task}{suffix}").resolve()
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"Task '{task}' not found")


def _build_dataloader(spec) -> object:
    loader_cls = cast(type[DataLoader], dataloader_registry.get(spec.name))
    loader = loader_cls(**spec.config)
    expected_type = type_registry.get(spec.item_type)
    first_item = next(iter(loader.iter_items(limit=1)), None)
    if first_item is not None:
        expected_type.model_validate(first_item.model_dump())
    return loader


def _build_processor(stage_spec: ProcessorStageSpec):
    processor_cls = cast(type[Processor], processor_registry.get(stage_spec.processor))
    input_type = type_registry.get(stage_spec.input_type)
    output_type = type_registry.get(stage_spec.output_type)
    return processor_cls(
        name=stage_spec.name,
        config=stage_spec.config,
        input_type=input_type,
        output_type=output_type,
        retry=stage_spec.retry,
    )


def _validate_output(output: BaseModel, output_type: type[BaseModel]) -> BaseModel:
    return output_type.model_validate(output.model_dump())


def _materialize_items(dataloader: DataLoader, limit: int | None) -> list[BaseModel]:
    return list(dataloader.iter_items(limit=limit))


def _item_id_for(item: BaseModel) -> str:
    item_id = getattr(item, "item_id", None)
    if item_id is not None:
        return str(item_id)

    legacy_id = getattr(item, "id", None)
    if legacy_id is not None:
        return str(legacy_id)

    raise ValueError(f"Item model '{type(item).__name__}' has no item identifier field")


def run_json_pipeline(
    spec: JsonPipelineSpec,
    *,
    runname: str,
    limit: int | None,
) -> Path:
    run_root = OUTPUT_ROOT / runname / spec.pipeline_name
    progress = None
    runtime: ScriptRuntime | None = None
    try:
        dataloader = _build_dataloader(spec.dataloader)
        processors = [_build_processor(stage_spec) for stage_spec in spec.stages]
        items = _materialize_items(cast(DataLoader, dataloader), limit)
        progress = ProgressReporter(total=len(items))
        runtime = ScriptRuntime(run_root=run_root, cache_root=CACHE_ROOT, progress=progress)
        final_stage_name = spec.stages[-1].name
        final_output_type = type_registry.get(spec.stages[-1].output_type)
        runtime.manifest.set_run_metadata(
            run_name=runname,
            pipeline_name=spec.pipeline_name,
            mode="json",
            final_stage_name=final_stage_name,
        )

        print(
            f"Running JSON pipeline '{spec.pipeline_name}' into {run_root}",
            flush=True,
        )
        for item in items:
            item_id = _item_id_for(item)
            final_output_path = runtime.output_store.final_output_path(final_stage_name, item_id)
            if runtime.manifest.is_complete(
                item_id,
                final_output_path,
                runtime.output_store,
                final_output_type,
            ):
                progress.item_started(item_id)
                progress.item_finished(item_id, final_output_path)
                progress.print_update()
                continue
            progress.item_started(item_id)
            runtime.manifest.mark_running(item_id)
            context = ProcessorContext(item_id=item_id, source_item=item, runtime=runtime)
            current = item
            try:
                for index, (stage_spec, processor) in enumerate(
                    zip(spec.stages, processors, strict=True)
                ):
                    current = runtime.run_stage(
                        stage_index=index,
                        stage_name=stage_spec.name,
                        processor=processor,
                        input_data=current,
                        context=context,
                        save_output=stage_spec.save_output,
                    )
                final_output = _validate_output(current, final_output_type)
                output_sha = runtime.output_store.write_model(final_output_path, final_output)
                runtime.manifest.mark_success(item_id, final_output_path, output_sha)
                progress.item_finished(item_id, final_output_path)
                progress.print_update()
            except Exception as exc:
                runtime.manifest.mark_failed(item_id, str(exc))
                print(f"[item {item_id}] failed: {exc}", flush=True)
                raise
        print(f"Completed JSON pipeline '{spec.pipeline_name}'", flush=True)
        return run_root
    finally:
        if runtime is not None:
            runtime.close()


def run_script_workflow(
    workflow: ScriptWorkflow,
    *,
    runname: str,
    limit: int | None,
) -> Path:
    run_root = OUTPUT_ROOT / runname / workflow.name
    progress = None
    runtime: ScriptRuntime | None = None
    try:
        final_stage_name = workflow.final_stage_name
        items = _materialize_items(cast(DataLoader, workflow.loader), limit)
        progress = ProgressReporter(total=len(items))
        runtime = ScriptRuntime(run_root=run_root, cache_root=CACHE_ROOT, progress=progress)
        runtime.manifest.set_run_metadata(
            run_name=runname,
            pipeline_name=workflow.name,
            mode="script",
            final_stage_name=final_stage_name,
        )
        print(
            f"Running script workflow '{workflow.name}' into {run_root}",
            flush=True,
        )
        for item in items:
            item_id = _item_id_for(item)
            final_output_path = runtime.output_store.final_output_path(final_stage_name, item_id)
            if runtime.manifest.is_complete(
                item_id,
                final_output_path,
                runtime.output_store,
                workflow.final_output_type,
            ):
                progress.item_started(item_id)
                progress.item_finished(item_id, final_output_path)
                progress.print_update()
                continue
            progress.item_started(item_id)
            runtime.manifest.mark_running(item_id)
            context = ProcessorContext(item_id=item_id, source_item=item, runtime=runtime)
            try:
                output = workflow.process_item(item, runtime, context)
                final_output = _validate_output(output, workflow.final_output_type)
                output_sha = runtime.output_store.write_model(final_output_path, final_output)
                runtime.manifest.mark_success(item_id, final_output_path, output_sha)
                progress.item_finished(item_id, final_output_path)
                progress.print_update()
            except Exception as exc:
                runtime.manifest.mark_failed(item_id, str(exc))
                print(f"[item {item_id}] failed: {exc}", flush=True)
                raise
        if workflow.finalize_run is not None:
            workflow.finalize_run(runtime)
        print(f"Completed script workflow '{workflow.name}'", flush=True)
        return run_root
    finally:
        if runtime is not None:
            runtime.close()


def load_task(task: str) -> JsonPipelineSpec | ScriptWorkflow:
    path = _resolve_task_path(task)
    if path.suffix == ".json":
        return JsonPipelineSpec.model_validate_json(path.read_text(encoding="utf-8"))
    if path.suffix != ".py":
        raise ValueError(f"Unsupported task file '{path}'")

    module = _load_script_module(path)
    builder = getattr(module, "build_workflow", None)
    if callable(builder):
        workflow = builder()
    else:
        workflow = getattr(module, "WORKFLOW", None)
    if not isinstance(workflow, ScriptWorkflow):
        raise TypeError(
            "Script task must expose build_workflow() or WORKFLOW returning ScriptWorkflow"
        )
    return workflow


def run_task(task: str, *, runname: str | None = None, limit: int | None = None) -> Path:
    loaded = load_task(task)
    resolved_runname = runname or _default_runname()
    if isinstance(loaded, JsonPipelineSpec):
        return run_json_pipeline(loaded, runname=resolved_runname, limit=limit)
    return run_script_workflow(loaded, runname=resolved_runname, limit=limit)


def run_tasks(
    tasks: Sequence[str],
    *,
    runname: str | None = None,
    limit: int | None = None,
) -> list[Path]:
    resolved_runname = runname or _default_runname()
    return [run_task(task, runname=resolved_runname, limit=limit) for task in tasks]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run graph_represent pipelines")
    parser.add_argument(
        "tasks",
        nargs="+",
        type=str,
        help="One or more JSON configs or Python workflow paths/names",
    )
    parser.add_argument("--runname", type=str, default=None, help="Output run name")
    parser.add_argument("--limit", "--count", type=int, default=None, help="Item limit")
    return parser
