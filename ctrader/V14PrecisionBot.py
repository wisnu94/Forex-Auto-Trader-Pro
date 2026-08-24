import clr

clr.AddReference("cAlgo.API")

from cAlgo.API import *
from robot_wrapper import *


class V14PrecisionBot:
    def on_start(self):
        self.last_bar_time = None
        self.ema20 = api.Indicators.ExponentialMovingAverage(api.Bars.ClosePrices, 20)
        self.ema50 = api.Indicators.ExponentialMovingAverage(api.Bars.ClosePrices, 50)
        self.rsi = api.Indicators.RelativeStrengthIndex(api.Bars.ClosePrices, 14)
        self.atr = api.Indicators.AverageTrueRange(14, MovingAverageType.WilderSmoothing)
        self.macd = api.Indicators.MacdCrossOver(26, 12, 9)
        self.volume_in_units = api.Symbol.QuantityToVolumeInUnits(api.VolumeInLots)

    def on_bar_closed(self):
        index = api.Bars.Count - 1
        if index < 60:
            return

        current_time = api.Bars.OpenTimes[index]
        if self.last_bar_time == current_time:
            return
        self.last_bar_time = current_time

        if self._has_bot_position():
            return

        close = api.Bars.ClosePrices[index]
        high = api.Bars.HighPrices[index]
        low = api.Bars.LowPrices[index]
        open_price = api.Bars.OpenPrices[index]
        ema20 = self.ema20.Result[index]
        ema50 = self.ema50.Result[index]
        ema20_prev = self.ema20.Result[index - 5]
        ema50_prev = self.ema50.Result[index - 5]
        rsi = self.rsi.Result[index]
        atr = self.atr.Result[index]
        macd = self.macd.MACD[index]
        signal = self.macd.Signal[index]

        if atr <= 0:
            return

        separation = abs(ema20 - ema50) / atr
        candle_range = max(high - low, api.Symbol.PipSize)
        body = abs(close - open_price)
        location = (close - low) / candle_range
        prior_high = max(api.Bars.HighPrices[index - 20:index])
        prior_low = min(api.Bars.LowPrices[index - 20:index])

        trend_buy = ema20 > ema50 and ema20 > ema20_prev and ema50 >= ema50_prev
        trend_sell = ema20 < ema50 and ema20 < ema20_prev and ema50 <= ema50_prev
        buy_break = close > prior_high and location >= 0.67 and body >= 0.40 * candle_range
        sell_break = close < prior_low and location <= 0.33 and body >= 0.40 * candle_range
        buy_pullback = (
            trend_buy
            and low <= ema20 + 0.15 * atr
            and close > ema20
            and close > api.Bars.ClosePrices[index - 1]
        )

        buy_score = 0
        sell_score = 0
        if trend_buy:
            buy_score += 25
        if trend_sell:
            sell_score += 25
        if separation >= 0.35:
            buy_score += 5 if trend_buy else 0
            sell_score += 8 if trend_sell else 0
        if 53 <= rsi <= 67:
            buy_score += 12
        if 33 <= rsi <= 46:
            sell_score += 15
        if macd > signal:
            buy_score += 12
        if macd < signal:
            sell_score += 12
        if buy_break:
            buy_score += 20
        if buy_pullback:
            buy_score += 16
        if sell_break:
            sell_score += 25

        if buy_score >= 78 and trend_buy and (buy_break or buy_pullback):
            self._open_trade(TradeType.Buy, atr)
            return

        if sell_score >= 82 and trend_sell and sell_break:
            self._open_trade(TradeType.Sell, atr)

    def _has_bot_position(self):
        return len(api.Positions.FindAll("V14_PRECISION")) > 0

    def _open_trade(self, trade_type, atr):
        stop_distance = 1.6 * atr
        target_distance = 1.8 * stop_distance
        stop_pips = stop_distance / api.Symbol.PipSize
        target_pips = target_distance / api.Symbol.PipSize

        if stop_pips <= 0 or target_pips <= 0:
            return

        result = api.ExecuteMarketOrder(
            trade_type,
            api.SymbolName,
            self.volume_in_units,
            "V14_PRECISION",
            stop_pips,
            target_pips,
        )
        if not result.IsSuccessful:
            api.Print(f"ORDER_REJECTED: {result.Error}")
