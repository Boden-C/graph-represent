from __future__ import annotations

import argparse
import json
import os
import time
import sys
from pathlib import Path
from typing import Any

from openai import OpenAI


REPO_ROOT = Path(__file__).resolve().parents[1]
CORPUS_ROOT = REPO_ROOT / "data" / "icle"
ESSAYS_PATH = CORPUS_ROOT / "essays" / "icle_essays_normalized.json"
GRAPH_PROMPT_PATH = REPO_ROOT / "graph_represent" / "prompts" / "IcleArgumentGraphByModel__EssayByModel.md"


def _load_icle_item(essays_path: Path, item_id: str) -> dict[str, Any]:
    payload = json.loads(essays_path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        # Try common layouts.
        for key in ("items", "data", "samples"):
            if isinstance(payload.get(key), list):
                payload = payload[key]
                break

    if not isinstance(payload, list):
        raise ValueError(f"Unexpected ICLE essays JSON structure in {essays_path}")

    for entry in payload:
        if not isinstance(entry, dict):
            continue
        entry_id = entry.get("item_id", entry.get("id"))
        if entry_id is not None and str(entry_id) == str(item_id):
            return entry
    raise KeyError(f"Item id '{item_id}' not found in {essays_path}")


def _build_user_message(*, prompt: str | None, essay: str) -> str:
    return f"Essay prompt:\n{prompt or '(none)'}\n\nEssay text:\n{essay}\n"


def _load_graph_json_schema() -> dict[str, Any]:
    # Hard-coded schema matching the one logged in your stage output.
    # (The prompt says only support/attack and claim/element/background,
    # but the schema itself allows extra enum values; keep it identical.)
    return {
        "title": "Graph",
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "arguments": {
                "title": "Arguments",
                "type": "array",
                "items": {
                    "title": "Argument",
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "claim": {"title": "Claim", "type": "integer"},
                        "premises": {
                            "title": "Premises",
                            "type": "array",
                            "items": {"type": "integer"},
                        },
                        "schema_version": {
                            "title": "Schema Version",
                            "type": "integer",
                            "default": 1,
                        },
                        "type": {
                            "title": "EdgeType",
                            "type": "string",
                            "enum": [
                                "support",
                                "support",
                                "attack",
                                "attack",
                                "trigger",
                                "paraphrase",
                            ],
                        },
                    },
                    "required": ["claim", "type"],
                },
            },
            "edges": {
                "title": "Edges",
                "default": None,
                "anyOf": [
                    {
                        "type": "array",
                        "items": {
                            "title": "Edge",
                            "type": "object",
                            "additionalProperties": False,
                            "properties": {
                                "from_idx": {"title": "From Idx", "type": "integer"},
                                "to_idx": {"title": "To Idx", "type": "integer"},
                                "schema_version": {
                                    "title": "Schema Version",
                                    "type": "integer",
                                    "default": 1,
                                },
                                "type": {
                                    "title": "EdgeType",
                                    "type": "string",
                                    "enum": [
                                        "support",
                                        "support",
                                        "attack",
                                        "attack",
                                        "trigger",
                                        "paraphrase",
                                    ],
                                },
                            },
                            "required": ["from_idx", "to_idx", "type"],
                        },
                    },
                    {"type": "null"},
                ],
            },
            "nodes": {
                "title": "Nodes",
                "type": "array",
                "items": {
                    "title": "Vertex",
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "idx": {"title": "Idx", "type": "integer"},
                        "text": {"title": "Text", "type": "string"},
                        "schema_version": {
                            "title": "Schema Version",
                            "type": "integer",
                            "default": 1,
                        },
                        "type": {
                            "title": "VertexType",
                            "type": "string",
                            "enum": [
                                "element",
                                "element",
                                "background",
                                "background",
                                "claim",
                                "none",
                            ],
                        },
                    },
                    "required": ["idx", "text", "type"],
                },
            },
            "schema_version": {
                "title": "Schema Version",
                "type": "integer",
                "default": 1,
            },
        },
        "required": ["nodes"],
    }


def _extract_first_json_after_marker(text: str, marker: str) -> dict[str, Any]:
    marker_index = text.find(marker)
    if marker_index < 0:
        raise ValueError(f"Marker not found: {marker!r}")

    brace_start = text.find("{", marker_index)
    if brace_start < 0:
        raise ValueError(f"No JSON object found after marker: {marker!r}")

    depth = 0
    in_string = False
    escape = False
    for i in range(brace_start, len(text)):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                obj_text = text[brace_start : i + 1]
                return json.loads(obj_text)

    raise ValueError("Unterminated JSON object while scanning stage log")


def main() -> int:
    parser = argparse.ArgumentParser(description="Stream ICLE graph generation from vLLM")
    parser.add_argument("--item-id", default="BGSU1001")
    parser.add_argument("--base-url", default=os.getenv("LOCAL_VLM_URL", "http://localhost:8000/v1"))
    parser.add_argument("--api-key", default=os.getenv("LOCAL_VLM_API_KEY", "-"))
    parser.add_argument("--model", default="Qwen/Qwen3-VL-8B-Instruct")
    parser.add_argument("--max-tokens", type=int, default=8192)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument(
        "--max-seconds",
        type=float,
        default=60.0,
        help="Stop reading the stream after this many seconds (best-effort).",
    )
    parser.add_argument(
        "--print-max-chars",
        type=int,
        default=8000,
        help="Print at most this many streamed chars to stdout; full output goes to a file.",
    )
    parser.add_argument(
        "--no-schema",
        action="store_true",
        help="Disable response_format=json_schema (debug A/B).",
    )
    parser.add_argument(
        "--system-prompt-file",
        default=str(GRAPH_PROMPT_PATH),
        help="Path to the system prompt Markdown file",
    )
    parser.add_argument(
        "--replay-stage-log",
        default=None,
        help=(
            "Path to a stage log containing REQUEST_JSON. If set, the script will replay that "
            "exact normalized request payload (messages/kwargs/schema) with stream=True."
        ),
    )
    args = parser.parse_args()

    if args.replay_stage_log:
        stage_text = Path(args.replay_stage_log).read_text(encoding="utf-8")
        normalized_request = _extract_first_json_after_marker(stage_text, "REQUEST_JSON:")
        replay_base_url = str(normalized_request.get("base_url") or args.base_url)
        replay_messages = normalized_request.get("messages")
        replay_kwargs = normalized_request.get("kwargs")
        if not isinstance(replay_messages, list) or not isinstance(replay_kwargs, dict):
            raise ValueError("Stage log REQUEST_JSON missing 'messages' or 'kwargs'")

        request = dict(replay_kwargs)
        request["messages"] = replay_messages
        request["stream"] = True
        request["stream_options"] = {"include_usage": True}
        if args.no_schema:
            request.pop("response_format", None)

        client = OpenAI(base_url=replay_base_url, api_key=str(args.api_key))
    else:
        item = _load_icle_item(ESSAYS_PATH, str(args.item_id))
        prompt = item.get("prompt")
        essay = item.get("essay")
        if not isinstance(essay, str) or not essay.strip():
            raise ValueError(f"Item '{args.item_id}' has no essay text")

        system_prompt = Path(args.system_prompt_file).read_text(encoding="utf-8")
        user_message = _build_user_message(
            prompt=str(prompt) if prompt is not None else None,
            essay=essay,
        )

        client = OpenAI(base_url=str(args.base_url), api_key=str(args.api_key))

        openai_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        request = {
            "model": str(args.model),
            "messages": openai_messages,
            "temperature": float(args.temperature),
            "max_tokens": int(args.max_tokens),
            "stream": True,
            "stream_options": {"include_usage": True},
        }
        if not args.no_schema:
            request["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "Graph", "schema": _load_graph_json_schema()},
            }

    print("REQUEST (normalized):")
    print(json.dumps({"base_url": args.base_url, **request}, indent=2)[:4000])
    print("\n--- STREAM START ---\n")

    started = time.time()
    out_dir = REPO_ROOT / "output" / "stream_debug"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"icle_{args.item_id}_{int(started)}.txt"

    printed = 0
    total = 0
    with out_path.open("w", encoding="utf-8") as out_handle:
        stream = client.chat.completions.create(**request)
        try:
            for chunk in stream:
                if (time.time() - started) > float(args.max_seconds):
                    print("\n\n--- STOP (max-seconds reached) ---\n")
                    break

                choices = getattr(chunk, "choices", None)
                if not choices:
                    usage = getattr(chunk, "usage", None)
                    if usage is not None:
                        print(f"[stream usage] {usage}", file=sys.stderr)
                    continue

                choice = choices[0]
                delta = choice.delta
                content = getattr(delta, "content", None)
                if not content:
                    continue

                out_handle.write(content)
                out_handle.flush()
                total += len(content)

                if printed < int(args.print_max_chars):
                    remaining = int(args.print_max_chars) - printed
                    to_print = content[:remaining]
                    sys.stdout.write(to_print)
                    sys.stdout.flush()
                    printed += len(to_print)
        finally:
            close = getattr(stream, "close", None)
            if callable(close):
                close()

    print("\n\n--- STREAM END ---\n")
    print(f"Streamed chars (total): {total}", file=sys.stderr)
    print(f"Wrote full stream to: {out_path}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
