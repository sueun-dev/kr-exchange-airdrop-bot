"""Type definitions used across the application."""

from __future__ import annotations

from typing import Any, TypedDict

from typing_extensions import NotRequired


class AccountInfo(TypedDict):
    account_id: str
    api_key: str
    api_secret: str


class TradeResult(TypedDict):
    account: str
    symbol: str
    success: bool
    buy_order: NotRequired[dict[str, Any]]
    sell_order: NotRequired[dict[str, Any]]
    error: NotRequired[str]


class SmallHolding(TypedDict):
    coin: str
    amount: float
    value: float


class CleanupResults(TypedDict):
    cleaned_coins: list[str]
    failed_coins: list[str]
    total_cleaned: int
