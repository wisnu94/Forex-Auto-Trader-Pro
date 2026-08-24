"""cTrader Open API cloud execution adapter.

Default mode is DEMO. Pure helpers are network-free and directly testable.
Live trading remains locked unless both live switches are explicitly enabled.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"DEMO", "LIVE"})
_ALLOWED_SIDES: Final[frozenset[str]] = frozenset({"BUY", "SELL"})


class CTraderConfigError(ValueError):
    """Raised when cTrader configuration or trade parameters are invalid."""


@dataclass(frozen=True, slots=True)
class CTraderConfig:
    mode: str
    client_id: str
    client_secret: str
    access_token: str
    account_id: int
    symbol_id: int
    volume_units: float
    allow_live: bool

    @classmethod
    def from_env(cls) -> "CTraderConfig":
        mode = os.getenv("TRADING_MODE", "DEMO").strip().upper()
        if mode not in _ALLOWED_MODES:
            raise CTraderConfigError("TRADING_MODE harus DEMO atau LIVE")

        client_id = os.getenv("CTRADER_CLIENT_ID", "").strip()
        client_secret = os.getenv("CTRADER_CLIENT_SECRET", "").strip()
        access_token = os.getenv("CTRADER_ACCESS_TOKEN", "").strip()
        if not client_id or not client_secret or not access_token:
            raise CTraderConfigError(
                "CTRADER_CLIENT_ID, CTRADER_CLIENT_SECRET, dan CTRADER_ACCESS_TOKEN wajib diisi"
            )

        try:
            account_id = int(os.getenv("CTRADER_ACCOUNT_ID", "0"))
            symbol_id = int(os.getenv("CTRADER_SYMBOL_ID", "0"))
            volume_units = float(os.getenv("CTRADER_VOLUME_UNITS", "1000"))
        except ValueError as exc:
            raise CTraderConfigError("Account ID, symbol ID, dan volume harus numerik") from exc

        if account_id <= 0 or symbol_id <= 0:
            raise CTraderConfigError("CTRADER_ACCOUNT_ID dan CTRADER_SYMBOL_ID harus > 0")
        if volume_units <= 0:
            raise CTraderConfigError("CTRADER_VOLUME_UNITS harus > 0")

        allow_live = os.getenv("CTRADER_ALLOW_LIVE", "false").strip().lower() == "true"
        if mode == "LIVE" and not allow_live:
            raise CTraderConfigError("LIVE terkunci: CTRADER_ALLOW_LIVE harus true")

        return cls(
            mode=mode,
            client_id=client_id,
            client_secret=client_secret,
            access_token=access_token,
            account_id=account_id,
            symbol_id=symbol_id,
            volume_units=volume_units,
            allow_live=allow_live,
        )


def validate_trade_signal(side: str, entry: float, stop_loss: float, take_profit: float) -> str:
    normalized = side.strip().upper()
    if normalized not in _ALLOWED_SIDES:
        raise CTraderConfigError("Signal harus BUY atau SELL")
    if not all(value > 0 for value in (entry, stop_loss, take_profit)):
        raise CTraderConfigError("Entry, SL, dan TP harus > 0")
    if normalized == "BUY" and not (stop_loss < entry < take_profit):
        raise CTraderConfigError("BUY membutuhkan SL < entry < TP")
    if normalized == "SELL" and not (take_profit < entry < stop_loss):
        raise CTraderConfigError("SELL membutuhkan TP < entry < SL")
    return normalized


def relative_protection(entry: float, stop_loss: float, take_profit: float) -> tuple[int, int]:
    sl = int(round(abs(entry - stop_loss) * 100000))
    tp = int(round(abs(take_profit - entry) * 100000))
    if sl <= 0 or tp <= 0:
        raise CTraderConfigError("Jarak SL/TP terlalu kecil")
    return sl, tp


def protocol_volume(volume_units: float) -> int:
    if volume_units <= 0:
        raise CTraderConfigError("Volume harus > 0")
    protocol = int(round(volume_units * 100))
    if protocol <= 0:
        raise CTraderConfigError("Volume menghasilkan protocol volume 0")
    return protocol


def build_order_parameters(
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    volume_units: float,
) -> dict[str, int | float | str]:
    normalized = validate_trade_signal(side, entry, stop_loss, take_profit)
    sl, tp = relative_protection(entry, stop_loss, take_profit)
    return {
        "tradeSide": normalized,
        "orderType": "MARKET",
        "volume": protocol_volume(volume_units),
        "relativeStopLoss": sl,
        "relativeTakeProfit": tp,
    }


def run_one_shot_order(
    config: CTraderConfig,
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
) -> None:
    """Connect, authenticate, send one protected market order, then exit."""
    from ctrader_open_api import Client, EndPoints, TcpProtocol
    from ctrader_open_api.messages.OpenApiMessages_pb2 import (
        ProtoOAAccountAuthReq,
        ProtoOAAccountAuthRes,
        ProtoOAApplicationAuthReq,
        ProtoOAApplicationAuthRes,
        ProtoOANewOrderReq,
        ProtoOAExecutionEvent,
    )
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
        ProtoOAOrderType,
        ProtoOATradeSide,
    )
    from twisted.internet import reactor

    host = EndPoints.PROTOBUF_LIVE_HOST if config.mode == "LIVE" else EndPoints.PROTOBUF_DEMO_HOST
    client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
    parameters = build_order_parameters(side, entry, stop_loss, take_profit, config.volume_units)
    finished = {"value": False}

    def finish(message: str, failed: bool = False) -> None:
        if finished["value"]:
            return
        finished["value"] = True
        print(message)
        try:
            client.stopService()
        finally:
            reactor.stop()
        if failed:
            raise RuntimeError(message)

    def on_error(failure: object) -> None:
        finish(f"cTrader API error: {failure}", failed=True)

    def send_account_auth(current_client: object) -> None:
        request = ProtoOAAccountAuthReq()
        request.ctidTraderAccountId = config.account_id
        request.accessToken = config.access_token
        deferred = current_client.send(request)
        deferred.addCallback(on_account_auth)
        deferred.addErrback(on_error)

    def on_application_auth(_message: object) -> None:
        send_account_auth(client)

    def on_account_auth(message: object) -> None:
        if not isinstance(message, ProtoOAAccountAuthRes):
            finish(f"Unexpected account auth response: {message}", failed=True)
            return

        request = ProtoOANewOrderReq()
        request.ctidTraderAccountId = config.account_id
        request.symbolId = config.symbol_id
        request.orderType = ProtoOAOrderType.Value("MARKET")
        request.tradeSide = ProtoOATradeSide.Value(str(parameters["tradeSide"]))
        request.volume = int(parameters["volume"])
        request.relativeStopLoss = int(parameters["relativeStopLoss"])
        request.relativeTakeProfit = int(parameters["relativeTakeProfit"])
        deferred = client.send(request)
        deferred.addCallback(on_order_response)
        deferred.addErrback(on_error)

    def on_order_response(message: object) -> None:
        if isinstance(message, ProtoOAExecutionEvent):
            finish(f"cTrader execution response: {message}")
            return
        finish(f"Unexpected order response: {message}", failed=True)

    def connected(current_client: object) -> None:
        request = ProtoOAApplicationAuthReq()
        request.clientId = config.client_id
        request.clientSecret = config.client_secret
        deferred = current_client.send(request)
        deferred.addCallback(on_application_auth)
        deferred.addErrback(on_error)

    def disconnected(_current_client: object, reason: object) -> None:
        if not finished["value"]:
            finish(f"cTrader disconnected before completion: {reason}", failed=True)

    client.setConnectedCallback(connected)
    client.setDisconnectedCallback(disconnected)
    client.startService()
    reactor.run()
