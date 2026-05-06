from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Message:
    role: str
    text: str


@dataclass(frozen=True)
class CallTranscript:
    stage_log: Path
    stage_name: str
    messages: list[Message]
    assistant_text: str | None
    request_kwargs: dict[str, object] | None


def _extract_block(text: str, start_marker: str, end_marker: str | None) -> str | None:
    start_idx = text.find(start_marker)
    if start_idx == -1:
        return None
    start_idx += len(start_marker)
    if end_marker is None:
        return text[start_idx:].strip()
    end_idx = text.find(end_marker, start_idx)
    if end_idx == -1:
        return None
    return text[start_idx:end_idx].strip()


def _parse_pretty_json(block: str) -> object | None:
    try:
        return json.loads(block)
    except json.JSONDecodeError:
        return None


def _cache_ref_from_stage_log(text: str) -> dict[str, object] | None:
    block = _extract_block(text, "REQUEST_CACHE:\n", "REQUEST_JSON:\n")
    if block is None:
        return None
    payload = _parse_pretty_json(block)
    return payload if isinstance(payload, dict) else None


def _stage_name_from_log(text: str, fallback: str) -> str:
    match = re.search(r"^STAGE_NAME:\s*(.+?)\s*$", text, flags=re.MULTILINE)
    if match is None:
        return fallback
    return match.group(1).strip() or fallback


def _messages_from_request_json(payload: object) -> list[Message]:
    if not isinstance(payload, dict):
        return []
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return []

    parsed: list[Message] = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = str(msg.get("role") or "")
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") == "text":
                parts.append(str(part.get("text") or ""))
        parsed.append(Message(role=role, text="".join(parts)))
    return parsed


def _assistant_text_from_response_json(block: str) -> str | None:
    payload = _parse_pretty_json(block)
    if payload is not None:
        return json.dumps(payload, indent=2, ensure_ascii=False)
    return block.strip() or None


def _load_from_cache(cache_path: Path) -> tuple[list[Message], str | None, dict[str, object] | None] | None:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    if not isinstance(payload, dict):
        return None
    request_payload = payload.get("request_payload")
    messages = _messages_from_request_json(request_payload)
    response_text = payload.get("response_text")
    assistant_text = str(response_text) if response_text is not None else None

    kwargs_raw = None
    if isinstance(request_payload, dict):
        kwargs_obj = request_payload.get("kwargs")
        if isinstance(kwargs_obj, dict):
            kwargs_raw = {str(k): v for k, v in kwargs_obj.items()}

    if assistant_text is not None:
        assistant_text = _assistant_text_from_response_json(assistant_text)
    return messages, assistant_text, kwargs_raw


def parse_stage_log(path: Path) -> CallTranscript | None:
    raw = path.read_text(encoding="utf-8")
    stage_name = _stage_name_from_log(raw, fallback=path.stem)

    cache_ref = _cache_ref_from_stage_log(raw)
    if cache_ref is not None:
        cache_path_raw = cache_ref.get("cache_path")
        if cache_path_raw is not None:
            cache_path = Path(str(cache_path_raw))
            loaded = _load_from_cache(cache_path)
            if loaded is not None:
                messages, assistant_text, request_kwargs = loaded
                return CallTranscript(
                    stage_log=path,
                    stage_name=stage_name,
                    messages=messages,
                    assistant_text=assistant_text,
                    request_kwargs=request_kwargs,
                )

    request_block = _extract_block(raw, "REQUEST_JSON:\n", "RESPONSE_JSON:\n")
    if request_block is None:
        return None

    request_payload = _parse_pretty_json(request_block)
    messages = _messages_from_request_json(request_payload)

    response_block = _extract_block(raw, "RESPONSE_JSON:\n", "STATUS:")
    assistant_text = None
    if response_block is not None:
        assistant_text = _assistant_text_from_response_json(response_block)

    return CallTranscript(
        stage_log=path,
        stage_name=stage_name,
        messages=messages,
        assistant_text=assistant_text,
        request_kwargs=None,
    )


def _render_md(transcripts: list[CallTranscript], *, root: Path) -> str:
    lines: list[str] = []
    lines.append(f"# Run Message Transcript\n")
    lines.append(f"Source: {root}\n")

    for transcript in transcripts:
        rel = transcript.stage_log.relative_to(root)
        lines.append(f"## {transcript.stage_name}\n")
        lines.append(f"Log: {rel}\n")

        if transcript.request_kwargs is not None:
            lines.append("### Request kwargs\n")
            lines.append("```\n" + json.dumps(transcript.request_kwargs, indent=2, ensure_ascii=False) + "\n```\n")

        for message in transcript.messages:
            role = message.role or "(unknown)"
            lines.append(f"### {role.capitalize()}\n")
            lines.append("```\n" + message.text.rstrip() + "\n```\n")

        if transcript.assistant_text is not None:
            lines.append("### Assistant\n")
            lines.append("```\n" + transcript.assistant_text.rstrip() + "\n```\n")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract model call transcripts from a run folder.")
    parser.add_argument("run_root", type=Path, help="Path like output/<timestamp>/<workflow>")
    parser.add_argument(
        "--item-id",
        type=str,
        default=None,
        help="Optional item id. If omitted, uses the first logs/<item>/ folder.",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output markdown file path. Default: <run_root>/messages_transcript.md",
    )

    args = parser.parse_args()
    run_root: Path = args.run_root
    logs_root = run_root / "logs"
    if not logs_root.exists():
        raise SystemExit(f"No logs folder: {logs_root}")

    item_id = args.item_id
    if item_id is None:
        item_dirs = sorted([p for p in logs_root.iterdir() if p.is_dir()])
        if not item_dirs:
            raise SystemExit(f"No item log folders under: {logs_root}")
        item_dir = item_dirs[0]
        item_id = item_dir.name
    else:
        item_dir = logs_root / item_id

    if not item_dir.exists():
        raise SystemExit(f"No such item log folder: {item_dir}")

    stage_logs = sorted(item_dir.glob("*.log"))
    transcripts: list[CallTranscript] = []
    for log_path in stage_logs:
        transcript = parse_stage_log(log_path)
        if transcript is None:
            continue
        transcripts.append(transcript)

    out_path = args.out or (run_root / "messages_transcript.md")
    out_path.write_text(_render_md(transcripts, root=run_root), encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
