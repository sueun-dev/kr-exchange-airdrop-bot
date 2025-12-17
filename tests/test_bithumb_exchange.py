from __future__ import annotations

import base64
import hashlib
import hmac
import time
from urllib.parse import urlencode

from typing import Any

import pytest
import requests

from exchange_event.exchanges.bithumb import BithumbExchange

from tests.conftest import DummyResponse


def test_generate_signature_is_deterministic(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = BithumbExchange({"apiKey": "k", "secret": "s"})

    monkeypatch.setattr(time, "time", lambda: 1234.567)

    endpoint = "/info/balance"
    params = {"currency": "ALL"}

    signature, nonce = exchange._generate_signature(endpoint, params)

    expected_nonce = str(int(1234.567 * 1000))
    data = endpoint + chr(0) + urlencode(params) + chr(0) + expected_nonce
    expected_h = hmac.new(b"s", data.encode("utf-8"), hashlib.sha512)
    expected_signature = base64.b64encode(expected_h.hexdigest().encode("utf-8")).decode("utf-8")

    assert nonce == expected_nonce
    assert signature == expected_signature


def test_get_krw_markets_parses_all_krw(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = BithumbExchange({"apiKey": "k", "secret": "s"})

    def fake_get(url: str, *args: object, **kwargs: object) -> DummyResponse:
        assert url.endswith("/public/ticker/ALL_KRW")
        return DummyResponse({"status": "0000", "data": {"BTC": {}, "ETH": {}, "date": "ignored"}})

    monkeypatch.setattr(requests, "get", fake_get)

    assert exchange.get_krw_markets() == ["BTC/KRW", "ETH/KRW"]


def test_get_ticker_combines_ticker_and_orderbook(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = BithumbExchange({"apiKey": "k", "secret": "s"})

    def fake_get(url: str, *args: object, **kwargs: object) -> DummyResponse:
        if "/public/ticker/" in url:
            return DummyResponse(
                {"status": "0000", "data": {"closing_price": "1000", "units_traded_24H": "12.5"}}
            )
        if "/public/orderbook/" in url:
            return DummyResponse(
                {
                    "status": "0000",
                    "data": {"bids": [{"price": "995"}], "asks": [{"price": "1005"}]},
                }
            )
        raise AssertionError(f"unexpected url: {url}")

    monkeypatch.setattr(requests, "get", fake_get)

    ticker = exchange.get_ticker("BTC/KRW")
    assert ticker is not None
    assert ticker["last"] == 1000.0
    assert ticker["bid"] == 995.0
    assert ticker["ask"] == 1005.0
    assert ticker["volume"] == 12.5


def test_get_balance_parses_response(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = BithumbExchange({"apiKey": "k", "secret": "s"})

    def fake_request(endpoint: str, params: Any = None) -> dict[str, Any]:
        assert endpoint == "/info/balance"
        return {
            "status": "0000",
            "data": {
                "available_krw": "8000",
                "in_use_krw": "2000",
                "total_krw": "10000",
                "available_btc": "0.3",
                "in_use_btc": "0.2",
                "total_btc": "0.5",
                "available_xrp": "0",
                "in_use_xrp": "0",
                "total_xrp": "0",
            },
        }

    monkeypatch.setattr(exchange, "_request", fake_request)

    balance = exchange.get_balance()
    assert balance["KRW"]["free"] == 8000.0
    assert balance["KRW"]["used"] == 2000.0
    assert balance["KRW"]["total"] == 10000.0
    assert balance["BTC"]["free"] == 0.3
    assert balance["BTC"]["used"] == 0.2
    assert balance["BTC"]["total"] == 0.5
    assert "XRP" not in balance


def test_market_buy_krw_rejects_below_minimum() -> None:
    exchange = BithumbExchange({"apiKey": "k", "secret": "s"})
    assert exchange.market_buy_krw("BTC/KRW", 1000) is None


def test_market_buy_krw_places_order(monkeypatch: pytest.MonkeyPatch) -> None:
    exchange = BithumbExchange({"apiKey": "k", "secret": "s"})

    def fake_get_ticker(_symbol: str) -> dict[str, float]:
        return {"last": 1000.0, "bid": 0.0, "ask": 0.0, "volume": 0.0}

    def fake_request(_endpoint: str, _params: Any = None) -> dict[str, Any]:
        return {"status": "0000", "order_id": "order-123"}

    monkeypatch.setattr(exchange, "get_ticker", fake_get_ticker)
    monkeypatch.setattr(exchange, "_request", fake_request)

    order = exchange.market_buy_krw("BTC/KRW", 5500)
    assert order is not None
    assert order["id"] == "order-123"
    assert order["side"] == "buy"
    assert order["amount"] == 5.5
