from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from time import perf_counter


def _format_time() -> str:
    return datetime.now().strftime("[%H:%M:%S]")


def _format_duration(seconds: float) -> str:
    rounded = max(0, round(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def _format_eta_clock(value: datetime) -> str:
    now = datetime.now()
    if value.date() == now.date():
        return value.strftime("Today at %H:%M")
    elif value.date() == (now + timedelta(days=1)).date():
        return value.strftime("Tomorrow at %H:%M")
    return value.strftime("%Y-%m-%d %H:%M")


@dataclass
class ProgressSnapshot:
    completed: int
    total: int
    percent: float
    eta_remaining: str
    eta_completion_str: str


class ProgressReporter:
    def __init__(self, total: int) -> None:
        self._total = max(total, 1)
        self._started_at = perf_counter()
        self._completed = 0

    def item_started(self, item_id: str) -> None:
        print(f"{_format_time()} Started item [{item_id}]", flush=True)

    def stage_started(self, stage_idx: int, stage_name: str) -> None:
        print(f"    {_format_time()} stage {stage_idx}: {stage_name}", flush=True)

    def item_finished(self, item_id: str, output_path: Path) -> None:
        print(f"{_format_time()} Output for item [{item_id}] in {output_path}", flush=True)

    def advance(self) -> ProgressSnapshot:
        self._completed += 1
        elapsed = perf_counter() - self._started_at
        average = elapsed / max(self._completed, 1)
        remaining_count = max(self._total - self._completed, 0)
        eta_remaining_seconds = average * remaining_count
        now = datetime.now()
        eta_completion = now + timedelta(seconds=eta_remaining_seconds)
        percent = min(100.0, (self._completed / self._total) * 100.0)
        return ProgressSnapshot(
            completed=self._completed,
            total=self._total,
            percent=percent,
            eta_remaining=_format_duration(eta_remaining_seconds),
            eta_completion_str=_format_eta_clock(eta_completion),
        )

    def print_update(self) -> None:
        snapshot = self.advance()
        filled = int((snapshot.percent / 100.0) * 24)
        bar = f"{'#' * filled}{'-' * (24 - filled)}"
        message = (
            f"[{bar}] {snapshot.percent:5.1f}% "
            f"({snapshot.completed}/{snapshot.total}) "
            f"ETA {snapshot.eta_completion_str}, {snapshot.eta_remaining} left"
        )
        print(message, flush=True)
