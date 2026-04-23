from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from graph_represent.providers.openai_compatible import OpenAICompatibleProvider
from graph_represent.types.persuasion import TECHNIQUES_TASK3


@pytest.fixture
def isolated_runner_roots(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    import graph_represent.runner as runner_module

    output_root = tmp_path / "output"
    cache_root = output_root / "cache" / "inference"
    monkeypatch.setattr(runner_module, "OUTPUT_ROOT", output_root)
    monkeypatch.setattr(runner_module, "CACHE_ROOT", cache_root)
    return output_root


@pytest.fixture
def mock_ai_requests(monkeypatch: pytest.MonkeyPatch) -> Callable[[], dict[str, int]]:
    def install() -> dict[str, int]:
        call_counter = {"count": 0}

        def fake_invoke(self, *, model, messages, response_type, create_kwargs):
            del model, messages, create_kwargs
            call_counter["count"] += 1
            if "scores" in response_type.model_fields:
                fields = response_type.model_fields["scores"]
                annotation = str(fields.annotation)
                if "float" in annotation and response_type.__name__ == "PersuasionTechniqueScores":
                    response_model = response_type(
                        scores={
                            label: (0.9 if label in {"loaded language", "smears"} else 0.1)
                            for label in TECHNIQUES_TASK3
                        }
                    )
                else:
                    response_model = response_type(
                        scores={
                            "cogency_mean": 0.7,
                            "rhetoric_strategy_rate": 0.8,
                            "reasonableness_counterargument_mean": 0.6,
                            "reasonableness_rebuttal_mean": 0.5,
                            "overall_quality_mean": 0.65,
                        },
                        rationale="Mock quality scores.",
                    )
            else:
                response_model = response_type()
            self._log("REQUEST_JSON:")
            self._log('{"provider": "mock"}')
            self._log("RESPONSE_JSON:")
            self._log(response_model.model_dump_json())
            return (
                {"provider": self.provider, "model": "mock", "messages": [], "kwargs": {}},
                response_model.model_dump_json(),
            )

        monkeypatch.setattr(OpenAICompatibleProvider, "invoke", fake_invoke)
        return call_counter

    return install
