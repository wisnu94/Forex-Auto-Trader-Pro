# Native cTrader V14 cBot

## Artifact

`V14PrecisionBot.cs` is the native cTrader implementation of the V14 precision strategy.

It uses only built-in cTrader Algo APIs so the resulting `.algo` is suitable for Cloud execution without external DLL dependencies.

## Strategy gates

- M15 execution chart.
- H1 and H4 EMA20/EMA50 trend confirmation.
- EMA slope and separation.
- RSI(14).
- MACD histogram.
- ADX/+DI/-DI.
- ATR(14) volatility regime.
- 20-bar breakout or BUY pullback structure.
- Tick-volume confirmation.
- BUY minimum score: 78.
- SELL minimum score: 82 and mandatory breakdown + stronger ADX/DI dominance.

## Risk controls

- Risk per trade: 0.25% of equity.
- Maximum daily equity loss: 1%.
- Maximum consecutive losses: 3.
- Maximum open positions for this bot/symbol: 1.
- Maximum spread: 2 pips by default.
- Stop loss: 1.6 x ATR.
- Take profit: 1.8R.
- No trailing or averaging-down logic.

## Cloud compatibility

The bot uses `AccessRights.None` and only built-in indicators and market/trading APIs. cTrader documents that cloud-compatible cBots should avoid Windows-specific dependencies and external DLL loading. See the official cloud requirements documentation.

## Build constraint

The repository contains the complete source, but cTrader's official documentation states that `.algo` creation/compilation takes place in cTrader Windows or Mac. Once a compiled `.algo` exists, cTrader Mobile can open/import it and start a Cloud instance.

This means an iOS-only user can operate the finished bot from Mobile, but the initial source-to-`.algo` build cannot be completed from this repository alone.

## Safety

The source is intended for DEMO/backtesting first. Do not enable real-money execution based on a single backtest result. Validate using broker-native historical data, walk-forward testing, spread/commission assumptions, and demo forward results before considering live trading.
