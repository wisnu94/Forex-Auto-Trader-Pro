from __future__ import annotations

import pytest

from ctrader_cloud import (
    CTraderConfig,
    CTraderConfigError,
    build_order_parameters,
    protocol_volume,
    relative_protection,
    validate_trade_signal,
)


def test_buy_validation_and_relative_protection() -> None:
    assert validate_trade_signal(" buy ", 100.0, 98.0, 104.0) == "BUY"
    assert relative_protection(100.0, 98.0, 104.0) == (200000, 400000)


def test_sell_validation() -> None:
    assert validate_trade_signal("SELL", 100.0, 102.0, 96.0) == "SELL"


def test_invalid_side_and_geometry() -> None:
    with pytest.raises(CTraderConfigError):
        validate_trade_signal("HOLD", 100.0, 98.0, 104.0)
    with pytest.raises(CTraderConfigError):
        validate_trade_signal("BUY", 100.0, 101.0, 104.0)
    with pytest.raises(CTraderConfigError):
        validate_trade_signal("SELL", 100.0, 102.0, 101.0)


def test_zero_and_negative_values_are_rejected() -> None:
    with pytest.raises(CTraderConfigError):
        validate_trade_signal("BUY", 0.0, -1.0, 2.0)
    with pytest.raises(CTraderConfigError):
        relative_protection(100.0, 100.0, 101.0)
    with pytest.raises(CTraderConfigError):
        protocol_volume(0.0)


def test_protocol_volume_and_order_parameters() -> None:
    assert protocol_volume(10.0) == 1000
    result = build_order_parameters("BUY", 100.0, 98.0, 104.0, 10.0)
    assert result == {
        "tradeSide": "BUY",
        "orderType": "MARKET",
        "volume": 1000,
        "relativeStopLoss": 200000,
        "relativeTakeProfit": 400000,
    }


def test_config_requires_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in (
        "CTRADER_CLIENT_ID",
        "CTRADER_CLIENT_SECRET",
        "CTRADER_ACCESS_TOKEN",
    ):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("TRADING_MODE", "DEMO")
    with pytest.raises(CTraderConfigError):
        CTraderConfig.from_env()


def test_live_is_locked_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRADING_MODE", "LIVE")
    monkeypatch.setenv("CTRADER_CLIENT_ID", "id")
    monkeypatch.setenv("CTRADER_CLIENT_SECRET", "secret")
    monkeypatch.setenv("CTRADER_ACCESS_TOKEN", "token")
    monkeypatch.setenv("CTRADER_ACCOUNT_ID", "123")
    monkeypatch.setenv("CTRADER_SYMBOL_ID", "456")
    monkeypatch.setenv("CTRADER_VOLUME_UNITS", "10")
    monkeypatch.setenv("CTRADER_ALLOW_LIVE", "false")
    with pytest.raises(CTraderConfigError):
        CTraderConfig.from_env()


def test_config_demo_accepts_complete_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    values = {
        "TRADING_MODE": "DEMO",
        "CTRADER_CLIENT_ID": "id",
        "CTRADER_CLIENT_SECRET": "secret",
        "CTRADER_ACCESS_TOKEN": "token",
        "CTRADER_ACCOUNT_ID": "123",
        "CTRADER_SYMBOL_ID": "456",
        "CTRADER_VOLUME_UNITS": "10",
        "CTRADER_ALLOW_LIVE": "false",
    }
    for key, value in values.items():
        monkeypatch.setenv(key, value)
    config = CTraderConfig.from_env()
    assert config.mode == "DEMO"
    assert config.account_id == 123
    assert config.symbol_id == 456
    assert config.volume_units == 10.0
