"""Canonical model registry for graph_represent run scripts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelConfig:
    name: str
    provider: str
    base_urls: list[str]


GEMMA3_27B = ModelConfig(
    name="google/gemma-3-27b-it",
    provider="vllm",
    base_urls=[
        "http://localhost:8000/v1",
        "http://10.176.142.89:8000/v1",
    ],
)

QWEN32B = ModelConfig(
    name="Qwen/Qwen2.5-VL-32B-Instruct-AWQ",
    provider="vllm",
    base_urls=[
        "http://localhost:8000/v1",
        "http://10.176.142.89:8000/v1",
    ],
)

QWEN8B = ModelConfig(
    name="Qwen/Qwen3-VL-8b-Instruct",
    provider="vllm",
    base_urls=[
        "http://localhost:8000/v1",
        "http://10.176.142.89:8000/v1",
    ],
)

INTERNVL2_8B = ModelConfig(
    name="OpenGVLab/InternVL2-8B",
    provider="vllm",
    base_urls=[
        "http://localhost:8000/v1",
        "http://10.176.142.89:8000/v1",
    ],
)
