from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel

LOG_TRUNCATE_CHARS = int(os.getenv("GRAPH_REPRESENT_LOG_TRUNCATE_CHARS", "1000"))


def truncate_string(value: str, limit: int | None = None) -> str:
    max_length = LOG_TRUNCATE_CHARS if limit is None else limit
    if len(value) <= max_length:
        return value
    return f"{value[:max_length]}..."


def sanitize_for_log(value: object, limit: int | None = None) -> object:
    if isinstance(value, BaseModel):
        return sanitize_for_log(value.model_dump(mode="json"), limit=limit)
    if isinstance(value, Path):
        return truncate_string(str(value), limit=limit)
    if isinstance(value, str):
        return truncate_string(value, limit=limit)
    if isinstance(value, list):
        return [sanitize_for_log(item, limit=limit) for item in value]
    if isinstance(value, tuple):
        return [sanitize_for_log(item, limit=limit) for item in value]
    if isinstance(value, dict):
        return {str(key): sanitize_for_log(item, limit=limit) for key, item in value.items()}
    return value


def pretty_json_for_log(value: object, limit: int | None = None) -> str:
    sanitized = sanitize_for_log(value, limit=limit)
    return json.dumps(sanitized, indent=2, ensure_ascii=False, sort_keys=True)


def maybe_json_value(value: str, limit: int | None = None) -> str:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return pretty_json_for_log({"text": value}, limit=limit)
    return pretty_json_for_log(parsed, limit=limit)
