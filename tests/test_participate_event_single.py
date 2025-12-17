from __future__ import annotations

import time
from typing import Any, Optional

import pytest

from exchange_event.airdrop_event import AirdropBot
from exchange_event.types import AccountInfo


class _FakeExchange:
    def __init__(self, buy_ok: bool = True) -> None:
        self._buy_ok = buy_ok

    def market_buy_krw(self, symbol: str, krw_amount: float) -> Optional[dict[str, Any]]:
        if not self._buy_ok:
            return None
        return {"id": "buy-1"}

    def get_balance(self) -> dict[str, dict[str, float]]:
        return {
            "KRW": {"free": 10000.0},
            "BTC": {"free": 0.5},
        }

    def create_market_order(self, symbol: str, side: str, amount: float) -> dict[str, Any]:
        assert symbol == "BTC/KRW"
        assert side == "sell"
        assert amount == 0.5
        return {"id": "sell-1"}


def test_participate_event_single_success(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = AirdropBot("bithumb")
    bot.wait_time = 0

    account: AccountInfo = {"account_id": "account_1", "api_key": "k", "api_secret": "s"}
    fake_exchange = _FakeExchange(buy_ok=True)

    monkeypatch.setattr(bot, "create_exchange", lambda account_info: fake_exchange)
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)

    assert bot.participate_event_single(account, "BTC") is True

    result = bot.results.get_nowait()
    assert result["success"] is True
    assert result["account"] == "account_1"
    assert result["symbol"] == "BTC/KRW"


def test_participate_event_single_buy_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    bot = AirdropBot("bithumb")

    account: AccountInfo = {"account_id": "account_1", "api_key": "k", "api_secret": "s"}
    fake_exchange = _FakeExchange(buy_ok=False)

    monkeypatch.setattr(bot, "create_exchange", lambda account_info: fake_exchange)
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)

    assert bot.participate_event_single(account, "BTC") is False

    result = bot.results.get_nowait()
    assert result["success"] is False
    assert result["error"] == "매수 실패"
