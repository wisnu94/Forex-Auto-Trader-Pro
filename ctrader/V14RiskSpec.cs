using cAlgo.API;

namespace ForexAutoTraderPro;

public sealed class V14RiskSpec
{
    public const double MaxRiskPercent = 0.25;
    public const double MaxDailyLossPercent = 1.0;
    public const int MaxConsecutiveLosses = 3;
    public const int MaxPositions = 1;
    public const int BuyMinimumScore = 78;
    public const int SellMinimumScore = 82;
    public const double AtrStopMultiplier = 1.6;
    public const double RewardRisk = 1.8;

    public static bool IsValidSignal(TradeType direction, int score)
    {
        return direction switch
        {
            TradeType.Buy => score >= BuyMinimumScore,
            TradeType.Sell => score >= SellMinimumScore,
            _ => false
        };
    }

    public static bool IsSafeDailyState(double dailyLossPercent, int consecutiveLosses, int openPositions)
    {
        return dailyLossPercent < MaxDailyLossPercent
            && consecutiveLosses < MaxConsecutiveLosses
            && openPositions < MaxPositions;
    }
}
