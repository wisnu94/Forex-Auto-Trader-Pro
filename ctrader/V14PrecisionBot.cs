using System;
using System.Linq;
using cAlgo.API;
using cAlgo.API.Indicators;
using cAlgo.API.Internals;

namespace ForexAutoTraderPro;

[Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
public sealed class V14PrecisionBot : Robot
{
    private const string Label = "ForexAutoTraderPro-V14";

    [Parameter("Risk %", DefaultValue = 0.25, MinValue = 0.01, MaxValue = 2.0, Step = 0.01)] public double RiskPercent { get; set; }
    [Parameter("Daily Loss %", DefaultValue = 1.0, MinValue = 0.1, MaxValue = 5.0, Step = 0.1)] public double DailyLossPercent { get; set; }
    [Parameter("Max Consecutive Losses", DefaultValue = 3, MinValue = 1, MaxValue = 10)] public int MaxConsecutiveLosses { get; set; }
    [Parameter("Max Spread Pips", DefaultValue = 2.0, MinValue = 0.1, MaxValue = 20.0, Step = 0.1)] public double MaxSpreadPips { get; set; }
    [Parameter("Buy Min Score", DefaultValue = 78, MinValue = 70, MaxValue = 100)] public int BuyMinimumScore { get; set; }
    [Parameter("Sell Min Score", DefaultValue = 82, MinValue = 70, MaxValue = 100)] public int SellMinimumScore { get; set; }
    [Parameter("ATR Period", DefaultValue = 14, MinValue = 5, MaxValue = 50)] public int AtrPeriod { get; set; }
    [Parameter("ATR SL x", DefaultValue = 1.6, MinValue = 0.5, MaxValue = 5.0, Step = 0.1)] public double AtrStopMultiplier { get; set; }
    [Parameter("Reward/Risk", DefaultValue = 1.8, MinValue = 1.0, MaxValue = 5.0, Step = 0.1)] public double RewardRisk { get; set; }
    [Parameter("EMA Fast", DefaultValue = 20, MinValue = 2, MaxValue = 100)] public int EmaFastPeriod { get; set; }
    [Parameter("EMA Slow", DefaultValue = 50, MinValue = 5, MaxValue = 200)] public int EmaSlowPeriod { get; set; }
    [Parameter("Structure Lookback", DefaultValue = 20, MinValue = 5, MaxValue = 100)] public int StructureLookback { get; set; }
    [Parameter("ADX Period", DefaultValue = 14, MinValue = 5, MaxValue = 50)] public int AdxPeriod { get; set; }
    [Parameter("Volume Multiplier", DefaultValue = 1.10, MinValue = 0.5, MaxValue = 5.0, Step = 0.05)] public double VolumeMultiplier { get; set; }

    private ExponentialMovingAverage _emaFast = null!;
    private ExponentialMovingAverage _emaSlow = null!;
    private RelativeStrengthIndex _rsi = null!;
    private AverageTrueRange _atr = null!;
    private MacdHistogram _macd = null!;
    private DirectionalMovementSystem _dms = null!;
    private Bars _h1Bars = null!;
    private Bars _h4Bars = null!;
    private ExponentialMovingAverage _h1Fast = null!;
    private ExponentialMovingAverage _h1Slow = null!;
    private ExponentialMovingAverage _h4Fast = null!;
    private ExponentialMovingAverage _h4Slow = null!;
    private DateTime _day;
    private double _dayStartBalance;
    private int _consecutiveLosses;
    private bool _locked;

    protected override void OnStart()
    {
        ValidateParameters();
        _emaFast = Indicators.ExponentialMovingAverage(Bars.ClosePrices, EmaFastPeriod);
        _emaSlow = Indicators.ExponentialMovingAverage(Bars.ClosePrices, EmaSlowPeriod);
        _rsi = Indicators.RelativeStrengthIndex(Bars.ClosePrices, 14);
        _atr = Indicators.AverageTrueRange(AtrPeriod, MovingAverageType.Exponential);
        _macd = Indicators.MacdHistogram(26, 12, 9);
        _dms = Indicators.DirectionalMovementSystem(Bars, AdxPeriod);
        _h1Bars = MarketData.GetBars(TimeFrame.Hour, SymbolName);
        _h4Bars = MarketData.GetBars(TimeFrame.Hour4, SymbolName);
        _h1Fast = Indicators.ExponentialMovingAverage(_h1Bars.ClosePrices, EmaFastPeriod);
        _h1Slow = Indicators.ExponentialMovingAverage(_h1Bars.ClosePrices, EmaSlowPeriod);
        _h4Fast = Indicators.ExponentialMovingAverage(_h4Bars.ClosePrices, EmaFastPeriod);
        _h4Slow = Indicators.ExponentialMovingAverage(_h4Bars.ClosePrices, EmaSlowPeriod);
        RebuildRiskState();
        Positions.Closed += OnPositionClosed;
    }

    protected override void OnStop() => Positions.Closed -= OnPositionClosed;

    protected override void OnBarClosed()
    {
        ResetDailyStateIfNeeded();
        if (_locked || !RiskStateIsSafe() || Positions.FindAll(Label, SymbolName).Length > 0) return;
        if (Symbol.Spread / Symbol.PipSize > MaxSpreadPips) return;
        if (Bars.Count < Math.Max(EmaSlowPeriod + 60, StructureLookback + 60)) return;

        var index = Bars.Count - 1;
        var signal = EvaluateSignal(index);
        if (signal.Direction is null) return;
        var direction = signal.Direction.Value;
        var minimum = direction == TradeType.Buy ? BuyMinimumScore : SellMinimumScore;
        if (signal.Score < minimum) return;

        var atr = _atr.Result[index];
        if (!double.IsFinite(atr) || atr <= 0) return;
        var stopPips = atr * AtrStopMultiplier / Symbol.PipSize;
        var takePips = stopPips * RewardRisk;
        if (!double.IsFinite(stopPips) || !double.IsFinite(takePips) || stopPips <= 0 || takePips <= 0) return;

        var volume = Symbol.VolumeForProportionalRisk(ProportionalAmountType.Equity, RiskPercent, stopPips, RoundingMode.Down);
        volume = Symbol.NormalizeVolumeInUnits(volume, RoundingMode.Down);
        if (volume < Symbol.VolumeInUnitsMin) return;

        var result = ExecuteMarketOrder(direction, SymbolName, volume, Label, stopPips, takePips, "V14 precision gate", false, StopTriggerMethod.Trade);
        if (!result.IsSuccessful) Print("Order rejected: {0}", result.Error);
    }

    private (TradeType? Direction, int Score) EvaluateSignal(int index)
    {
        var close = Bars.ClosePrices[index];
        var open = Bars.OpenPrices[index];
        var high = Bars.HighPrices[index];
        var low = Bars.LowPrices[index];
        var h1 = GetTrend(_h1Bars, _h1Fast, _h1Slow);
        var h4 = GetTrend(_h4Bars, _h4Fast, _h4Slow);
        var ema20 = _emaFast.Result[index];
        var ema50 = _emaSlow.Result[index];
        var prevEma20 = _emaFast.Result[index - 5];
        var prevEma50 = _emaSlow.Result[index - 5];
        var atr = _atr.Result[index];
        var rsi = _rsi.Result[index];
        var adx = _dms.ADX[index];
        var diPlus = _dms.DIPlus[index];
        var diMinus = _dms.DIMinus[index];
        var hist = _macd.Histogram[index];
        var histPrev = _macd.Histogram[index - 1];
        if (!double.IsFinite(atr) || atr <= 0 || !double.IsFinite(adx)) return (null, 0);

        var atrMedian = AtrMedian(index, 50);
        var atrOk = atrMedian > 0 && atr / atrMedian >= 0.75 && atr / atrMedian <= 1.70 && atr / close >= 0.00025 && atr / close <= 0.02;
        var sep = Math.Abs(ema20 - ema50) / atr;
        var trendBuy = ema20 > ema50 && ema20 > prevEma20 && ema50 >= prevEma50;
        var trendSell = ema20 < ema50 && ema20 < prevEma20 && ema50 <= prevEma50;
        var priorHigh = double.MinValue;
        var priorLow = double.MaxValue;
        for (var i = index - StructureLookback; i < index; i++) { priorHigh = Math.Max(priorHigh, Bars.HighPrices[i]); priorLow = Math.Min(priorLow, Bars.LowPrices[i]); }
        var range = Math.Max(high - low, Symbol.TickSize);
        var body = Math.Abs(close - open);
        var location = (close - low) / range;
        var buyBreak = close > priorHigh && location >= 0.67 && body >= 0.40 * range;
        var sellBreak = close < priorLow && location <= 0.33 && body >= 0.40 * range;
        var buyPullback = trendBuy && low <= ema20 + 0.15 * atr && close > ema20 && close > Bars.ClosePrices[index - 1];
        var buyScore = 0;
        var sellScore = 0;
        if (trendBuy) buyScore += 25;
        if (trendSell) sellScore += 25;
        if (sep >= 0.35) { if (trendBuy) buyScore += 5; if (trendSell) sellScore += 8; }
        if (rsi >= 53 && rsi <= 67) buyScore += 12;
        if (rsi >= 33 && rsi <= 46) sellScore += 15;
        if (hist > 0 && hist >= histPrev) buyScore += 12;
        if (hist < 0 && hist <= histPrev) sellScore += 15;
        if (adx >= 20 && diPlus - diMinus >= 3) buyScore += 16;
        if (adx >= 25 && diMinus - diPlus >= 5) sellScore += 20;
        if (atrOk) { if (trendBuy) buyScore += 5; if (trendSell) sellScore += 5; }
        if (buyPullback || buyBreak) buyScore += 15;
        if (sellBreak) sellScore += 18;
        if (Bars.TickVolumes.Count > 20)
        {
            double average = 0;
            for (var i = index - 19; i < index; i++) average += Bars.TickVolumes[i];
            average /= 19.0;
            if (average > 0 && Bars.TickVolumes[index] >= average * VolumeMultiplier)
            {
                if (buyScore > sellScore && (buyPullback || buyBreak)) buyScore += 5;
                else if (sellScore > buyScore && sellBreak) sellScore += 5;
            }
        }
        var side = buyScore > sellScore ? TradeType.Buy : sellScore > buyScore ? TradeType.Sell : (TradeType?)null;
        var score = Math.Max(buyScore, sellScore);
        if (side == TradeType.Buy && (h4 != "BUY" || h1 != "BUY" || !trendBuy || !atrOk || (!buyPullback && !buyBreak) || rsi < 53)) side = null;
        if (side == TradeType.Sell && (h4 != "SELL" || h1 != "SELL" || !trendSell || !atrOk || !sellBreak || rsi > 46 || adx < 25 || diMinus - diPlus < 5)) side = null;
        return (side, score);
    }

    private static string GetTrend(Bars bars, ExponentialMovingAverage fast, ExponentialMovingAverage slow)
    {
        if (bars.Count < 60) return "HOLD";
        return fast.Result.LastValue > slow.Result.LastValue ? "BUY" : fast.Result.LastValue < slow.Result.LastValue ? "SELL" : "HOLD";
    }

    private double AtrMedian(int index, int lookback)
    {
        var start = Math.Max(0, index - lookback);
        var values = Enumerable.Range(start, index - start).Select(i => _atr.Result[i]).Where(x => double.IsFinite(x) && x > 0).OrderBy(x => x).ToArray();
        if (values.Length == 0) return 0;
        var middle = values.Length / 2;
        return values.Length % 2 == 0 ? (values[middle - 1] + values[middle]) / 2.0 : values[middle];
    }

    private bool RiskStateIsSafe()
    {
        var dailyLoss = _dayStartBalance <= 0 ? 0 : Math.Max(0, (_dayStartBalance - Account.Equity) / _dayStartBalance * 100.0);
        return dailyLoss < DailyLossPercent && _consecutiveLosses < MaxConsecutiveLosses && Positions.FindAll(Label, SymbolName).Length < 1;
    }

    private void ResetDailyStateIfNeeded()
    {
        if (Server.Time.Date == _day) return;
        _day = Server.Time.Date;
        _dayStartBalance = Account.Balance;
        _consecutiveLosses = 0;
        _locked = false;
    }

    private void RebuildRiskState()
    {
        _day = Server.Time.Date;
        _dayStartBalance = Account.Balance;
        _consecutiveLosses = 0;
        _locked = false;
        var history = History.FindAll(Label, SymbolName).OrderByDescending(x => x.ClosingTime).ToArray();
        foreach (var position in history)
        {
            if (position.ClosingTime.Date != _day) break;
            if (position.NetProfit < 0) _consecutiveLosses++;
            else if (position.NetProfit > 0) break;
        }
        if (_consecutiveLosses >= MaxConsecutiveLosses) _locked = true;
    }

    private void OnPositionClosed(PositionClosedEventArgs args)
    {
        var position = args.Position;
        if (!string.Equals(position.Label, Label, StringComparison.Ordinal) || !string.Equals(position.SymbolName, SymbolName, StringComparison.Ordinal)) return;
        if (position.NetProfit < 0) { _consecutiveLosses++; if (_consecutiveLosses >= MaxConsecutiveLosses) _locked = true; }
        else if (position.NetProfit > 0) _consecutiveLosses = 0;
    }

    private void ValidateParameters()
    {
        if (RiskPercent <= 0 || RiskPercent > 2) throw new ArgumentOutOfRangeException(nameof(RiskPercent));
        if (DailyLossPercent <= 0 || DailyLossPercent > 5) throw new ArgumentOutOfRangeException(nameof(DailyLossPercent));
        if (MaxConsecutiveLosses < 1) throw new ArgumentOutOfRangeException(nameof(MaxConsecutiveLosses));
        if (MaxSpreadPips <= 0) throw new ArgumentOutOfRangeException(nameof(MaxSpreadPips));
        if (BuyMinimumScore < 70 || SellMinimumScore < 70) throw new ArgumentOutOfRangeException(nameof(BuyMinimumScore));
        if (AtrPeriod < 5 || AtrStopMultiplier <= 0 || RewardRisk < 1) throw new ArgumentOutOfRangeException(nameof(AtrPeriod));
        if (EmaFastPeriod >= EmaSlowPeriod) throw new ArgumentException("EMA Fast must be below EMA Slow.");
        if (StructureLookback < 5 || AdxPeriod < 5 || VolumeMultiplier <= 0) throw new ArgumentOutOfRangeException(nameof(StructureLookback));
    }
}
