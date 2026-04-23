from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from graph_represent.types.pipeline import InferenceCacheEntry
from graph_represent.utils.files import atomic_write_text, sha256_file, sha256_text
from graph_represent.utils.json_utils import canonical_json


def sanitize_item_id(item_id: str) -> str:
    sanitized = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in item_id)
    return sanitized or "item"


class InferenceCache:
    def __init__(self, root: Path) -> None:
        self._root = root
        self._root.mkdir(parents=True, exist_ok=True)

    def build_cache_key(self, normalized_request: dict[str, Any]) -> str:
        return sha256_text(canonical_json(normalized_request))

    def load(self, cache_key: str) -> str | None:
        path = self._root / f"{cache_key}.json"
        if not path.exists():
            return None
        entry = InferenceCacheEntry.model_validate_json(path.read_text(encoding="utf-8"))
        return entry.response_text

    def store(
        self,
        *,
        cache_key: str,
        provider: str,
        model: str,
        request_payload: dict[str, Any],
        response_text: str,
    ) -> None:
        path = self._root / f"{cache_key}.json"
        entry = InferenceCacheEntry(
            cache_key=cache_key,
            provider=provider,
            model=model,
            request_payload=request_payload,
            response_text=response_text,
        )
        atomic_write_text(path, entry.model_dump_json(indent=2))


class OutputStore:
    def __init__(self, run_root: Path) -> None:
        self._run_root = run_root
        self._output_root = run_root / "output"
        self._logs_root = run_root / "logs"
        self._output_root.mkdir(parents=True, exist_ok=True)
        self._logs_root.mkdir(parents=True, exist_ok=True)

    @property
    def run_root(self) -> Path:
        return self._run_root

    @property
    def output_root(self) -> Path:
        return self._output_root

    @property
    def logs_root(self) -> Path:
        return self._logs_root

    def stage_output_path(self, stage_name: str, item_id: str) -> Path:
        safe_id = sanitize_item_id(item_id)
        return self._output_root / stage_name / f"{safe_id}.json"

    def final_output_path(self, final_stage_name: str, item_id: str) -> Path:
        safe_id = sanitize_item_id(item_id)
        return self._output_root / final_stage_name / f"{safe_id}.json"

    def stage_log_path(self, stage_index: int, stage_name: str, item_id: str) -> Path:
        safe_id = sanitize_item_id(item_id)
        return self._logs_root / safe_id / f"{stage_index:02d}_{stage_name}.log"

    def write_model(self, path: Path, model: BaseModel) -> str:
        atomic_write_text(path, model.model_dump_json(indent=2))
        return sha256_file(path)

    def has_output(self, path: Path) -> bool:
        return path.exists()


class RunManifest:
    def __init__(self, run_root: Path) -> None:
        self._path = run_root / "run_manifest.json"
        if self._path.exists():
            self._state = json.loads(self._path.read_text(encoding="utf-8"))
        else:
            self._state = {
                "schema_version": 1,
                "items": {},
            }
            self._flush()

    def _timestamp(self) -> str:
        return datetime.now(UTC).isoformat()

    def _flush(self) -> None:
        atomic_write_text(
            self._path,
            json.dumps(self._state, indent=2, ensure_ascii=False),
        )

    def set_run_metadata(
        self,
        *,
        run_name: str,
        pipeline_name: str,
        mode: str,
        final_stage_name: str,
    ) -> None:
        self._state["run_name"] = run_name
        self._state["pipeline_name"] = pipeline_name
        self._state["mode"] = mode
        self._state["final_stage_name"] = final_stage_name
        self._state.setdefault("created_at", self._timestamp())
        self._state["updated_at"] = self._timestamp()
        self._flush()

    def mark_running(self, item_id: str) -> None:
        self._state.setdefault("items", {})[item_id] = {
            "status": "running",
            "error": None,
            "updated_at": self._timestamp(),
        }
        self._state["updated_at"] = self._timestamp()
        self._flush()

    def mark_success(self, item_id: str, output_path: Path, output_sha: str) -> None:
        self._state.setdefault("items", {})[item_id] = {
            "status": "success",
            "output_path": str(output_path),
            "output_sha": output_sha,
            "error": None,
            "updated_at": self._timestamp(),
        }
        self._state["updated_at"] = self._timestamp()
        self._flush()

    def mark_failed(self, item_id: str, error: str) -> None:
        self._state.setdefault("items", {})[item_id] = {
            "status": "failed",
            "error": error,
            "updated_at": self._timestamp(),
        }
        self._state["updated_at"] = self._timestamp()
        self._flush()

    def is_complete(
        self,
        item_id: str,
        output_path: Path,
        output_store: OutputStore,
        output_type: type[BaseModel],
    ) -> bool:
        item_record = self._state.get("items", {}).get(item_id)
        if item_record is None:
            return False
        if item_record.get("status") != "success":
            return False
        if item_record.get("output_path") != str(output_path):
            return False
        if not output_store.has_output(output_path):
            return False
        if sha256_file(output_path) != item_record.get("output_sha"):
            return False
        try:
            output_type.model_validate_json(output_path.read_text(encoding="utf-8"))
        except Exception:
            return False
        return True

    def close(self) -> None:
        self._flush()
