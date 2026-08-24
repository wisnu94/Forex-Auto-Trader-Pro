from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from backtest import backtest_strategy


@dataclass(frozen=True, slots=True)
class WindowResult:
    train_start: int
    train_end: int
    test_start: int
    test_end: int
    total_trades: int
    win_rate: float
    profit_factor: float
    net_r: float
    expectancy_r: float


def _safe_float(value: Any) -> float:
    return float(value) if value is not None else 0.0


def walk_forward(
    df: pd.DataFrame,
    train_bars: int = 1200,
    test_bars: int = 400,
    step_bars: int = 400,
    min_score: int = 70,
) -> list[WindowResult]:
    if train_bars < 200 or test_bars < 100 or step_bars < 1:
        raise ValueError("train_bars>=200, test_bars>=100, step_bars>=1")
    if df is None or len(df) < train_bars + test_bars:
        return []

    results: list[WindowResult] = []
    start = 0
    while start + train_bars + test_bars <= len(df):
        train = df.iloc[start:start + train_bars].copy().reset_index(drop=True)
        test = df.iloc[start + train_bars:start + train_bars + test_bars].copy().reset_index(drop=True)

        # Strategy parameters are fixed by the production strategy; training is
        # deliberately used as a chronology gate, not for fitting arbitrary values.
        _ = backtest_strategy(train, min_score=min_score)
        out = backtest_strategy(test, min_score=min_score)

        results.append(WindowResult(
            train_start=start,
            train_end=start + train_bars,
            test_start=start + train_bars,
            test_end=start + train_bars + test_bars,
            total_trades=int(out["total_trades"]),
            win_rate=_safe_float(out["win_rate"]),
            profit_factor=_safe_float(out["profit_factor"]),
            net_r=_safe_float(out["net_r"]),
            expectancy_r=_safe_float(out["expectancy_r"]),
        ))
        start += step_bars

    return results


def summarize(results: list[WindowResult]) -> dict[str, float | int | bool]:
    if not results:
        return {
            "windows": 0,
            "trades": 0,
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "net_r": 0.0,
            "expectancy_r": 0.0,
            "robust": False,
        }

    trades = sum(x.total_trades for x in results)
    wins = sum(round(x.total_trades * x.win_rate / 100.0) for x in results)
    gross_profit = sum(max(x.net_r, 0.0) for x in results)
    gross_loss = abs(sum(min(x.net_r, 0.0) for x in results))
    pf = gross_profit / gross_loss if gross_loss else (float("inf") if gross_profit else 0.0)
    net_r = sum(x.net_r for x in results)
    expectancy = net_r / trades if trades else 0.0
    positive_windows = sum(x.net_r > 0 for x in results)

    return {
        "windows": len(results),
        "trades": trades,
        "win_rate": round(wins / trades * 100.0, 2) if trades else 0.0,
        "profit_factor": round(pf, 3) if pf != float("inf") else pf,
        "net_r": round(net_r, 4),
        "expectancy_r": round(expectancy, 4),
        "robust": bool(
            trades >= 30
            and positive_windows >= max(2, len(results) // 2)
            and pf >= 1.20
            and expectancy > 0
        ),
    }
