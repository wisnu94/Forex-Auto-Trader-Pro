# cTrader Cloud Setup

## Architecture

The cloud runner uses the existing V14 strategy, evaluates the last closed M15 candle, and can submit a protected market order through cTrader Open API. GitHub Actions is the scheduler; the iPhone does not need to remain connected.

## Required one-time account setup

1. Create a cTrader Open API application and obtain Client ID and Client Secret.
2. Authorize the trading account with trade scope and obtain an Access Token.
3. Record the cTrader account ID and the broker-specific symbol ID for the pair being traded.
4. Use a demo account first.

## GitHub Actions secrets

Create these repository secrets:

- `CTRADER_CLIENT_ID`
- `CTRADER_CLIENT_SECRET`
- `CTRADER_ACCESS_TOKEN`
- `CTRADER_ACCOUNT_ID`
- `CTRADER_SYMBOL_ID`
- `CTRADER_VOLUME_UNITS`

Never commit these values to the repository.

## Safe activation sequence

The workflow currently runs with `CTRADER_EXECUTE=false` and `CTRADER_ALLOW_LIVE=false`. This deliberately performs strategy evaluation without submitting orders.

After the demo integration has been externally authorized and validated, the workflow can be switched to `CTRADER_EXECUTE=true` for demo execution. Live execution is a separate release gate and is not enabled by this document.

## Important data limitation

The first cloud runner uses Yahoo Finance M15 bars for signal generation and cTrader only for execution. This is intentionally not considered broker-grade validation because Yahoo FX quotes and broker quotes can differ. A broker-matched historical data gate must pass before any live release.

## Strategy validation gate

A profitable result or 70-80% win rate is not assumed. Release criteria must use out-of-sample/walk-forward data and include spread, slippage, commission, drawdown, profit factor, expectancy, trade count, and parameter robustness.
