from __future__ import annotations

import pandas as pd
import pytest

from walk_forward import summarize, walk_forward


def _data(rows: int) -> pd.DataFrame:
    close = [100.0 + i * 0.01 for i in range(rows)]
    return pd.DataFrame({
        "open": close,
        "high": [x + 0.1 for x in close],
        "low": [x - 0.1 for x in close],
        "close": close,
        "volume": [1000.0] * rows,
    })


def test_empty_and_invalid_inputs() -> None:
    assert walk_forward(_data(100), train_bars=200, test_bars=100) == []
    with pytest.raises(ValueError):
        walk_forward(_data(1000), train_bars=199, test_bars=100)


def test_summary_empty_is_not_robust() -> None:
    result = summarize([])
    assert result["robust"] is False
    assert result["trades"] == 0


def test_walk_forward_returns_chronological_windows() -> None:
    results = walk_forward(_data(1000), train_bars=400, test_bars=200, step_bars=200)
    assert len(results) == 3
    assert results[0].train_start == 0
    assert results[0].test_start == 400
    assert results[1].train_start == 200


def test_summary_requires_positive_expectancy_and_enough_trades() -> None:
    result = summarize([])
    assert result["expectancy_r"] == 0.0
    assert result["profit_factor"] == 0.0
