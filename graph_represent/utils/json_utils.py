from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def fingerprint_data_url(data_url: str) -> dict[str, str | int]:
    header, _, payload = data_url.partition(",")
    decoded = base64.b64decode(payload.encode("utf-8"))
    mime_type = header.split(";", 1)[0].replace("data:", "", 1) or "application/octet-stream"
    return {
        "mime_type": mime_type,
        "byte_length": len(decoded),
        "sha256": __import__("hashlib").sha256(decoded).hexdigest(),
    }


def load_json_file(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
