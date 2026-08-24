using cAlgo.API;
using NUnit.Framework;

namespace ForexAutoTraderPro.Tests;

[TestFixture]
public sealed class V14RiskSpecTests
{
    [TestCase(TradeType.Buy, 78, true)]
    [TestCase(TradeType.Buy, 77, false)]
    [TestCase(TradeType.Sell, 82, true)]
    [TestCase(TradeType.Sell, 81, false)]
    public void SignalThresholdsAreAsymmetric(TradeType direction, int score, bool expected)
    {
        Assert.That(V14RiskSpec.IsValidSignal(direction, score), Is.EqualTo(expected));
    }

    [TestCase(0.99, 2, 0, true)]
    [TestCase(1.00, 0, 0, false)]
    [TestCase(0.50, 3, 0, false)]
    [TestCase(0.50, 0, 1, false)]
    public void RiskStateStopsUnsafeTrading(double dailyLoss, int losses, int positions, bool expected)
    {
        Assert.That(V14RiskSpec.IsSafeDailyState(dailyLoss, losses, positions), Is.EqualTo(expected));
    }
}
