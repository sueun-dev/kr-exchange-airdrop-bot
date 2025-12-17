from __future__ import annotations

from exchange_event.airdrop_event import AirdropBot


def test_identify_small_holdings_filters_and_prices() -> None:
    bot = AirdropBot("bithumb")

    balance = {
        "KRW": {"free": 10000.0, "used": 0.0, "total": 10000.0},
        "XRP": {"free": 10.0, "used": 0.0, "total": 10.0},
        "BTC": {"free": 0.01, "used": 0.0, "total": 0.01},
        "NO_PRICE": {"free": 1.0, "used": 0.0, "total": 1.0},
        "ZERO": {"free": 0.0, "used": 0.0, "total": 0.0},
    }
    prices = {
        "XRP": {"closing_price": "400"},
        "BTC": {"closing_price": "600000"},
        "date": "ignored",
    }

    small = bot._identify_small_holdings(balance, prices, account_id="account_1")

    assert [holding["coin"] for holding in small] == ["XRP"]
    assert small[0]["amount"] == 10.0
    assert small[0]["value"] == 4000.0
