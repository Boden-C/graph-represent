from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from graph_represent.dataloaders.base import DataLoader
from graph_represent.processors.base import Processor, ProcessorContext, RuntimeProtocol
from graph_represent.providers.openai_compatible import OpenAICompatibleProvider
from graph_represent.utils.logging_utils import pretty_json_for_log
from graph_represent.utils.progress import ProgressReporter
from graph_represent.utils.runtime import InferenceCache, OutputStore, RunManifest

import json
import urllib.error
import urllib.request


@dataclass(frozen=True)
class ScriptWorkflow:
    name: str
    loader: DataLoader[BaseModel]
    final_stage_name: str
    final_output_type: type[BaseModel]
    process_item: Callable[[BaseModel, ScriptRuntime, ProcessorContext], BaseModel]
    finalize_run: Callable[[ScriptRuntime], None] | None = None


class ScriptRuntime(RuntimeProtocol):
    def __init__(
        self, *, run_root: Path, cache_root: Path, progress: ProgressReporter | None = None
    ) -> None:
        self.output_store = OutputStore(run_root)
        self.manifest = RunManifest(run_root)
        self._inference_cache = InferenceCache(cache_root)
        self._providers: dict[tuple[str, str | None, str | None], OpenAICompatibleProvider] = {}
        self._model_base_url_cache: dict[tuple[str, tuple[str, ...], str, str | None], str] = {}
        self._active_log_file = None
        self._progress = progress

    @property
    def inference_cache(self) -> InferenceCache:
        return self._inference_cache

    def get_provider(
        self,
        provider: str,
        *,
        base_url: str | None,
        base_urls: list[str] | None,
        api_key: str | None,
        model: str | None,
    ) -> OpenAICompatibleProvider:
        resolved_base_url = self._resolve_model_base_url(
            provider=provider,
            base_url=base_url,
            base_urls=base_urls,
            api_key=api_key,
            model=model,
        )
        cache_key = (provider, resolved_base_url, api_key)
        if cache_key not in self._providers:
            self._providers[cache_key] = OpenAICompatibleProvider(
                provider,
                base_url=resolved_base_url,
                api_key=api_key,
            )
            self._providers[cache_key].log_file = self._active_log_file
        return self._providers[cache_key]

    def _resolve_model_base_url(
        self,
        *,
        provider: str,
        base_url: str | None,
        base_urls: list[str] | None,
        api_key: str | None,
        model: str | None,
    ) -> str | None:
        # Backwards-compat: if a single base_url is set, use it as-is.
        if base_urls is None or not base_urls:
            return base_url

        # If no model specified, we can't probe. Fall back to the first host.
        if model is None:
            return base_urls[0]

        cache_key = (provider, tuple(base_urls), model, api_key)
        cached = self._model_base_url_cache.get(cache_key)
        if cached is not None:
            return cached

        for candidate in base_urls:
            if self._host_serves_model(
                base_url=candidate,
                api_key=api_key,
                model=model,
            ):
                self._model_base_url_cache[cache_key] = candidate
                return candidate

        # Nothing matched (offline, wrong host, etc). Keep deterministic behavior.
        fallback = base_urls[0]
        self._model_base_url_cache[cache_key] = fallback
        return fallback

    @staticmethod
    def _models_url(base_url: str) -> str:
        root = base_url.rstrip("/")
        if root.endswith("/v1"):
            return f"{root}/models"
        return f"{root}/v1/models"

    def _host_serves_model(self, *, base_url: str, api_key: str | None, model: str) -> bool:
        url = self._models_url(base_url)
        req = urllib.request.Request(url, method="GET")
        if api_key and api_key != "-":
            req.add_header("Authorization", f"Bearer {api_key}")
        try:
            # Keep this fast: if the host is down we want to fail over quickly.
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError):
            return False
        data = payload.get("data")
        if not isinstance(data, list):
            return False
        for entry in data:
            if isinstance(entry, dict) and entry.get("id") == model:
                return True
        return False

    def close(self) -> None:
        for provider in self._providers.values():
            provider.close()
        self.manifest.close()

    def run_stage(
        self,
        *,
        stage_index: int,
        stage_name: str,
        processor: Processor,
        input_data: BaseModel,
        context: ProcessorContext,
        save_output: bool = True,
    ) -> BaseModel:
        if self._progress:
            self._progress.stage_started(stage_index + 1, stage_name)
        stage_log_path = self.output_store.stage_log_path(stage_index, stage_name, context.item_id)
        stage_log_path.parent.mkdir(parents=True, exist_ok=True)
        with stage_log_path.open("w", encoding="utf-8") as log_handle:
            self._active_log_file = log_handle
            for provider in self._providers.values():
                provider.log_file = log_handle
            print(f"ITEM: {context.item_id}", file=log_handle, flush=True)
            print(f"STAGE_INDEX: {stage_index}", file=log_handle, flush=True)
            print(f"STAGE_NAME: {stage_name}", file=log_handle, flush=True)
            print(f"PROCESSOR: {type(processor).__name__}", file=log_handle, flush=True)
            print("INPUT_JSON:", file=log_handle, flush=True)
            print(pretty_json_for_log(input_data), file=log_handle, flush=True)
            try:
                output = processor(input_data, context)
                print("STATUS: success", file=log_handle, flush=True)
                print("OUTPUT_JSON:", file=log_handle, flush=True)
                print(pretty_json_for_log(output), file=log_handle, flush=True)
            except Exception as exc:
                print("STATUS: failed", file=log_handle, flush=True)
                print(f"ERROR: {exc}", file=log_handle, flush=True)
                raise
            finally:
                self._active_log_file = None
                for provider in self._providers.values():
                    provider.log_file = None

        if save_output:
            stage_path = self.output_store.stage_output_path(stage_name, context.item_id)
            self.output_store.write_model(stage_path, output)
        return output
