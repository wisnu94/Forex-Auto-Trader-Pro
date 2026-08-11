import os
import pandas as pd
from backtest import backtest_strategy
from config import EMA_FAST, EMA_SLOW, ATR_PERIOD, ATR_SL_MULTIPLIER, REWARD_RISK, MIN_SCORE
from data import get_bars

# FAST CI audit: use 1500 bars by default to reduce Yahoo download time.
# For deeper validation, run with ROBUSTNESS_BARS=3000 or more.
BARS = int(os.getenv("ROBUSTNESS_BARS", "1500"))
SYMBOL = os.getenv("ROBUSTNESS_SYMBOL", "XAUUSD")
TIMEFRAME = "M15"

COST_LEVELS_R = (0.00, 0.05, 0.10, 0.15, 0.20)
MIN_TRADES_WARNING = 20
MIN_TRADES_READY = 30

# Small fixed RR stress test. No parameter fitting / optimization.
SCENARIOS = (
    ("BASE", EMA_FAST, EMA_SLOW, ATR_SL_MULTIPLIER, REWARD_RISK, MIN_SCORE),
    ("RR_MINUS10", EMA_FAST, EMA_SLOW, ATR_SL_MULTIPLIER, REWARD_RISK * 0.90, MIN_SCORE),
    ("RR_PLUS10", EMA_FAST, EMA_SLOW, ATR_SL_MULTIPLIER, REWARD_RISK * 1.10, MIN_SCORE),
)


def validate_ohlc(df):
    required = {"open", "high", "low", "close", "time"}
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Missing OHLC columns: {sorted(missing)}")

    invalid = (
        (df.high < df.low)
        | (df.high < df.open)
        | (df.high < df.close)
        | (df.low > df.open)
        | (df.low > df.close)
    )
    if bool(invalid.any()):
        raise RuntimeError(f"Invalid OHLC rows: {int(invalid.sum())}")


def run(
    df,
    ema_fast=EMA_FAST,
    ema_slow=EMA_SLOW,
    atr_sl=ATR_SL_MULTIPLIER,
    rr=REWARD_RISK,
    score=MIN_SCORE,
):
    return backtest_strategy(
        df=df,
        ema_fast=ema_fast,
        ema_slow=ema_slow,
        atr_period=ATR_PERIOD,
        atr_sl_multiplier=atr_sl,
        reward_risk=rr,
        min_score=score,
    )


def summarize(name, r):
    print("-" * 70)
    print(name)
    print("-" * 70)
    print(f"Trades       : {r['total_trades']}")
    print(f"Win Rate     : {r['win_rate']}%")
    print(f"Profit Factor: {r['profit_factor']}")
    print(f"Net R        : {r['net_r']}")
    print(f"Expectancy R : {r['expectancy_r']}")


def max_drawdown_r(trades):
    equity = peak = max_dd = 0.0
    for t in trades:
        equity += float(t["r_multiple"])
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
    return round(max_dd, 4)


def direction_stats(trades):
    out = {}
    for signal in ("BUY", "SELL"):
        x = [t for t in trades if t.get("signal") == signal]
        out[signal] = (
            len(x),
            sum(t.get("outcome") == "WIN" for t in x),
            round(sum(float(t.get("r_multiple", 0)) for t in x), 4),
        )
    return out


def cost_stress(trades):
    print("\nCOST STRESS TEST")
    print("Cost is modeled as R deducted per completed trade.")
    print("-" * 70)

    if not trades:
        print("No trades available.")
        return

    base = sum(float(t["r_multiple"]) for t in trades)
    n = len(trades)

    for cost in COST_LEVELS_R:
        net = base - cost * n
        print(
            f"cost={cost:>4.2f}R | net_R={net:>8.3f} | "
            f"expectancy_R={net/n:>8.4f} | "
            f"status={'PASS' if net > 0 else 'FAIL'}"
        )


def segment_result(df, start, end):
    seg = df.iloc[start:end].reset_index(drop=True)
    if len(seg) < max(EMA_SLOW + 120, 300):
        return None
    return run(seg)


def scenario_audit(df):
    print("\nFAST PARAMETER STABILITY TEST")
    print("Fixed RR perturbations only; no parameter fitting.")
    print("-" * 70)

    rows = []

    for name, ef, es, sl, rr, score in SCENARIOS:
        r = run(df, ef, es, sl, rr, score)

        cost_pass = (
            sum(float(t["r_multiple"]) for t in r["trades"])
            - 0.10 * r["total_trades"]
        ) > 0

        status = (
            "PASS"
            if r["expectancy_r"] > 0
            and r["profit_factor"] > 1
            and cost_pass
            else "FAIL"
        )

        print(
            f"{name:<14} trades={r['total_trades']:>3} "
            f"WR={r['win_rate']:>6.2f}% PF={r['profit_factor']:>7} "
            f"ExpR={r['expectancy_r']:>7.4f} "
            f"cost0.10R={'PASS' if cost_pass else 'FAIL'} "
            f"status={status}"
        )

        rows.append(
            {
                "scenario": name,
                "trades": r["total_trades"],
                "win_rate": r["win_rate"],
                "profit_factor": r["profit_factor"],
                "net_r": r["net_r"],
                "expectancy_r": r["expectancy_r"],
                "cost_010_positive": cost_pass,
                "status": status,
            }
        )

    return rows


def main():
    print("=" * 70)
    print("FOREX AUTO TRADER PRO - GOLD ROBUSTNESS AUDIT V3 FAST")
    print("=" * 70)
    print(f"Live symbol       : {SYMBOL} (MT5)")
    print("CI proxy          : GC=F (Yahoo gold futures)")
    print(f"Timeframe         : {TIMEFRAME}")
    print(f"Bars requested    : {BARS}")
    print(
        f"Parameters        : EMA {EMA_FAST}/{EMA_SLOW}, ATR {ATR_PERIOD}, "
        f"SL {ATR_SL_MULTIPLIER}x, RR {REWARD_RISK}, score {MIN_SCORE}"
    )
    print("Parameter fitting : NONE")
    print("Live trading      : NOT ENABLED")
    print("Audit mode        : FAST CI")
    print()

    df = get_bars(SYMBOL, TIMEFRAME, count=BARS, source="YAHOO")
    validate_ohlc(df)

    print("OHLC validation    : PASS")
    print(f"Loaded bars        : {len(df)}")
    print(f"First candle       : {df.iloc[0]['time']}")
    print(f"Last candle        : {df.iloc[-1]['time']}")
    print()

    full = run(df)
    summarize("FULL SAMPLE", full)

    print(f"Max Drawdown R     : {max_drawdown_r(full['trades'])}")

    d = direction_stats(full["trades"])
    print(
        f"BUY                : trades={d['BUY'][0]} "
        f"wins={d['BUY'][1]} netR={d['BUY'][2]}"
    )
    print(
        f"SELL               : trades={d['SELL'][0]} "
        f"wins={d['SELL'][1]} netR={d['SELL'][2]}"
    )

    cost_stress(full["trades"])

    split = int(len(df) * 0.60)
    train = segment_result(df, 0, split)
    hold = segment_result(df, split, len(df))

    if train is None or hold is None:
        print("HOLDOUT CHECK : INSUFFICIENT DATA")
        raise SystemExit(2)

    summarize("CHRONOLOGICAL 60% SAMPLE", train)
    summarize("CHRONOLOGICAL 40% HOLDOUT", hold)

    scenarios = scenario_audit(df)
    stable = sum(x["status"] == "PASS" for x in scenarios)
    stability = stable / len(scenarios) * 100

    print("\nROBUSTNESS DECISION")
    print("-" * 70)

    checks = {
        "full_positive_expectancy": full["expectancy_r"] > 0,
        "holdout_positive_expectancy": hold["expectancy_r"] > 0,
        "full_pf_above_1": full["profit_factor"] > 1,
        "holdout_pf_above_1": hold["profit_factor"] > 1,
        "holdout_has_trades": hold["total_trades"] > 0,
        "cost_010_positive": full["net_r"] - 0.10 * full["total_trades"] > 0,
        "parameter_stability_80pct": stability >= 80,
        "full_sample_trade_count_ready": full["total_trades"] >= MIN_TRADES_READY,
        "holdout_trade_count_ready": hold["total_trades"] >= MIN_TRADES_READY,
    }

    for name, passed in checks.items():
        print(f"{'PASS' if passed else 'FAIL'} | {name}")

    if full["total_trades"] < MIN_TRADES_WARNING:
        print(
            f"WARNING | full sample has only {full['total_trades']} trades; "
            "statistical confidence is low."
        )

    if hold["total_trades"] < MIN_TRADES_WARNING:
        print(
            f"WARNING | holdout has only {hold['total_trades']} trades; "
            "statistical confidence is low."
        )

    print(f"Parameter stability : {stable}/{len(scenarios)} = {stability:.1f}%")
    print(
        "\nROBUSTNESS STATUS : "
        f"{'PASS' if all(checks.values()) else 'NOT_READY'}"
    )
    print("No live-trading setting is changed by this audit.")

    rows = []

    for label, result in (
        ("FULL", full),
        ("TRAIN_60", train),
        ("HOLDOUT_40", hold),
    ):
        for t in result["trades"]:
            row = dict(t)
            row["sample"] = label
            rows.append(row)

    if rows:
        pd.DataFrame(rows).to_csv("gold_robustness_trades.csv", index=False)
        print("Saved: gold_robustness_trades.csv")

    pd.DataFrame(scenarios).to_csv(
        "gold_parameter_stability.csv", index=False
    )
    print("Saved: gold_parameter_stability.csv")


if __name__ == "__main__":
    main()
