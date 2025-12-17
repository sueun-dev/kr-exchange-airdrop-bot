from __future__ import annotations

import os

import pytest

from exchange_event.airdrop_event import AirdropBot


def _clear_bithumb_env() -> None:
    for key in list(os.environ.keys()):
        if key.startswith("BITHUMB_API_KEY") or key.startswith("BITHUMB_SECRET_KEY"):
            os.environ.pop(key, None)


def test_load_accounts_prefers_numbered_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_bithumb_env()

    monkeypatch.setenv("BITHUMB_API_KEY", "legacy_key")
    monkeypatch.setenv("BITHUMB_SECRET_KEY", "legacy_secret")
    monkeypatch.setenv("BITHUMB_API_KEY_1", "key_1")
    monkeypatch.setenv("BITHUMB_SECRET_KEY_1", "secret_1")
    monkeypatch.setenv("BITHUMB_API_KEY_2", "key_2")
    monkeypatch.setenv("BITHUMB_SECRET_KEY_2", "secret_2")

    bot = AirdropBot("bithumb")

    assert [account["account_id"] for account in bot.accounts] == ["account_1", "account_2"]
    assert bot.accounts[0]["api_key"] == "key_1"
    assert bot.accounts[1]["api_key"] == "key_2"


def test_load_accounts_falls_back_to_legacy_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_bithumb_env()

    monkeypatch.setenv("BITHUMB_API_KEY", "legacy_key")
    monkeypatch.setenv("BITHUMB_SECRET_KEY", "legacy_secret")

    bot = AirdropBot("bithumb")

    assert [account["account_id"] for account in bot.accounts] == ["account_1"]
    assert bot.accounts[0]["api_key"] == "legacy_key"


def test_load_accounts_returns_empty_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    _clear_bithumb_env()

    bot = AirdropBot("bithumb")

    assert bot.accounts == []
