"""Base interfaces for exchange clients."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Mapping, Optional


class BaseExchange(ABC):
    """Abstract base class for exchange clients."""

    def __init__(self, exchange_id: str, api_credentials: Mapping[str, str]) -> None:
        """Initializes an exchange client.

        Args:
            exchange_id: 거래소 ID (upbit, bithumb)
            api_credentials: API 인증 정보
        """
        self.exchange_id = exchange_id
        self.name = exchange_id
        self.logger = logging.getLogger(f'exchange.{exchange_id}')
        
    @abstractmethod
    def get_krw_markets(self) -> list[str]:
        """Returns a list of supported KRW markets.

        Returns:
            list: KRW 마켓 심볼 리스트
        """
        pass
    
    @abstractmethod
    def get_ticker(self, symbol: str) -> Optional[dict[str, float]]:
        """Returns current ticker information for a symbol.

        Args:
            symbol: 거래 심볼 (예: BTC/KRW)
            
        Returns:
            dict: 가격 정보
        """
        pass
    
    @abstractmethod
    def get_balance(self, currency: Optional[str] = None) -> dict[str, dict[str, float]]:
        """Returns account balances.

        Returns:
            dict: 잔고 정보
        """
        pass
    
    @abstractmethod
    def create_market_order(
        self, symbol: str, side: str, amount: float
    ) -> Optional[dict[str, Any]]:
        """Creates a market order.

        Args:
            symbol: 거래 심볼
            side: 'buy' 또는 'sell'
            amount: 주문 수량
            
        Returns:
            dict: 주문 결과
        """
        pass
    
    @abstractmethod
    def market_buy_krw(self, symbol: str, krw_amount: float) -> Optional[dict[str, Any]]:
        """Creates a market buy order for a KRW amount.

        Args:
            symbol: 거래 심볼
            krw_amount: 매수할 KRW 금액
            
        Returns:
            dict: 주문 결과
        """
        pass
    
    def get_balance_summary(self) -> dict[str, Any]:
        """Returns a summarized view of balances.

        Returns:
            dict: 잔액 요약 정보
                - krw: 원화 잔액
                - total_krw: 총 평가금액
                - holdings: 보유 코인 리스트
        """
        try:
            balance = self.get_balance()
            if not balance:
                return {'krw': 0, 'total_krw': 0, 'holdings': []}
            
            krw_balance = 0.0
            total_krw_value = 0.0
            holdings: list[dict[str, Any]] = []
            
            for currency, info in balance.items():
                if currency == 'KRW':
                    krw_balance = float(info.get('total', 0.0))
                    total_krw_value += krw_balance
                else:
                    coin_balance = float(info.get('total', 0.0))
                    if coin_balance > 0:
                        # 현재가 조회
                        symbol = f"{currency}/KRW"
                        ticker = self.get_ticker(symbol)
                        if ticker:
                            current_price = float(ticker.get('last', 0.0))
                            krw_value = coin_balance * current_price
                            total_krw_value += krw_value
                            
                            holdings.append({
                                'currency': currency,
                                'balance': coin_balance,
                                'krw_value': krw_value
                            })
            
            return {
                'krw': krw_balance,
                'total_krw': total_krw_value,
                'holdings': holdings
            }
            
        except Exception as e:
            self.logger.error(f"잔액 요약 조회 실패: {e}")
            return {'krw': 0, 'total_krw': 0, 'holdings': []}
