"""Timeout-safe robustness harness for Gold V15.

This module provides bounded Monte Carlo/Bootstrap execution helpers so an audit
can fail closed instead of consuming the GitHub Actions job budget. It does not
change strategy parameters or manufacture pass results.
"""
from __future__ import annotations

import os
import time
from typing import Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")

DEFAULT_BUDGET_SECONDS = float(os.getenv("AUDIT_BUDGET_SECONDS", "180"))
DEFAULT_MAX_RUNS = int(os.getenv("AUDIT_MAX_RUNS", "2000"))


def bounded_bootstrap(
    values: Sequence[float],
    evaluator: Callable[[Sequence[float]], T],
    *,
    runs: int = DEFAULT_MAX_RUNS,
    budget_seconds: float = DEFAULT_BUDGET_SECONDS,
    seed: int = 1403,
) -> tuple[list[T], bool]:
    """Run bootstrap evaluations with deterministic seed and hard time budget.

    Returns (completed_results, complete). A partial result set is explicitly
    marked incomplete and must never be interpreted as a robustness PASS.
    """
    import random

    if not values:
        return [], True
    rng = random.Random(seed)
    started = time.monotonic()
    out: list[T] = []
    target = max(1, min(int(runs), DEFAULT_MAX_RUNS))

    for _ in range(target):
        if time.monotonic() - started >= budget_seconds:
            return out, False
        sample = [values[rng.randrange(len(values))] for _ in values]
        out.append(evaluator(sample))

    return out, True


def require_complete(results: Iterable[T], complete: bool) -> list[T]:
    """Fail closed if the robustness budget was exhausted."""
    materialized = list(results)
    if not complete:
        raise TimeoutError(
            f"robustness audit incomplete: completed={len(materialized)}; "
            "do not classify partial bootstrap output as PASS"
        )
    return materialized


if __name__ == "__main__":
    print("Gold V15 robustness timeout guard: READY")
    print(f"Budget seconds : {DEFAULT_BUDGET_SECONDS:g}")
    print(f"Max bootstrap : {DEFAULT_MAX_RUNS}")
    print("Fail-closed   : YES")
