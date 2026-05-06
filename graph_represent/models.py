"""Model configuration for graph_represent."""

from __future__ import annotations

# Default model serving provider
DEFAULT_PROVIDER = "vllm"

# Base URLs to probe for any model name. The workflow will check these in order.
MODEL_BASE_URLS = [
    "http://localhost:8000/v1",
    "http://10.176.142.89:8000/v1",
]
