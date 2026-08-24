"""cTrader Open API cloud execution adapter.

Default mode is DEMO. The module contains pure validation/conversion helpers and a
one-shot Twisted client for scheduled cloud runs. Live trading remains locked unless
CTRADER_ALLOW_LIVE=true and TRADING_MODE=LIVE are both explicitly set.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final


_ALLOWED_MODES: Final[frozenset[str]] = frozenset({"DEMO", "LIVE"})
_ALLOWED_SIDES: Final[frozenset[str]] = frozenset({"BUY", "SELL"})


class CTraderConfigError(ValueError):
    """Raised when cTrader configuration is invalid."""


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


def validate_trade_signal(
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
) -> str:
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
    sl_distance = abs(entry - stop_loss)
    tp_distance = abs(take_profit - entry)
    sl = int(round(sl_distance * 100000))
    tp = int(round(tp_distance * 100000))
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
    """Connect, authenticate, and send one protected market order.

    The official Spotware Python SDK is imported lazily so pure helpers remain
    testable without network credentials.
    """
    from ctrader_open_api import Client, EndPoints, Protobuf, TcpProtocol
    from ctrader_open_api.messages.OpenApiMessages_pb2 import (
        ProtoOAAccountAuthReq,
        ProtoOAApplicationAuthReq,
        ProtoOANewOrderReq,
    )
    from ctrader_open_api.messages.OpenApiModelMessages_pb2 import (
        ProtoOAOrderType,
        ProtoOATradeSide,
    )
    from twisted.internet import reactor

    host = EndPoints.PROTOBUF_LIVE_HOST if config.mode == "LIVE" else EndPoints.PROTOBUF_DEMO_HOST
    client = Client(host, EndPoints.PROTOBUF_PORT, TcpProtocol)
    parameters = build_order_parameters(side, entry, stop_loss, take_profit, config.volume_units)
    completed = {"value": False}

    def fail(message: str) -> None:
        if completed["value"]:
            return
        completed["value"] = True
        print(message)
        try:
            client.stopService()
        finally:
            reactor.stop()

    def connected(current_client: object) -> None:
        request = ProtoOAApplicationAuthReq()
        request.clientId = config.client_id
        request.clientSecret = config.client_secret
        deferred = current_client.send(request)
        deferred.addErrback(lambda failure: fail(f"Application auth failed: {failure}"))

    def on_message(current_client: object, message: object) -> None:
        if completed["value"]:
            return
        payload = Protobuf.extract(message)
        payload_type = getattr(payload, "payloadType", None)

        if payload_type == ProtoOAApplicationAuthReq().payloadType:
            return

        if payload_type == ProtoOAApplicationAuthReq().payloadType + 2:
            auth = ProtoOAAccountAuthReq()
            auth.ctidTraderAccountId = config.account_id
            auth.accessToken = config.access_token
            deferred = current_client.send(auth)
            deferred.addErrback(lambda failure: fail(f"Account auth failed: {failure}"))
            return

        if payload_type == ProtoOAAccountAuthReq().payloadType:
            order = ProtoOANewOrderReq()
            order.ctidTraderAccountId = config.account_id
            order.symbolId = config.symbol_id
            order.orderType = ProtoOAOrderType.Value("MARKET")
            order.tradeSide = ProtoOATradeSide.Value(str(parameters["tradeSide"]))
            order.volume = int(parameters["volume"])
            order.relativeStopLoss = int(parameters["relativeStopLoss"])
            order.relativeTakeProfit = int(parameters["relativeTakeProfit"])
            deferred = current_client.send(order)
            deferred.addErrback(lambda failure: fail(f"Order request failed: {failure}"))
            return

        if payload_type == order_payload_type():
            completed["value"] = True
            print(f"cTrader execution response: {payload}")
            try:
                client.stopService()
            finally:
                reactor.stop()

    def order_payload_type() -> int:
        return 2106

    def disconnected(_current_client: object, reason: object) -> None:
        if not completed["value"]:
            fail(f"cTrader disconnected: {reason}")

    client.setConnectedCallback(connected)
    client.setDisconnectedCallback(disconnected)
    client.setMessageReceivedCallback(on_message)
    client.startService()
    reactor.run()
