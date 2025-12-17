"""Bithumb exchange client implementation."""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Any, Mapping, Optional, cast
from urllib.parse import urlencode

import requests

from exchange_event.exchanges.base import BaseExchange

API_URL = "https://api.bithumb.com"
MAX_REQUEST_ATTEMPTS = 3
MIN_ORDER_KRW = 5500
REQUEST_TIMEOUT_SECONDS = 10


class BithumbExchange(BaseExchange):
    
    def __init__(self, api_credentials: Mapping[str, str]) -> None:
        """Initializes a Bithumb exchange client.

        Args:
            api_credentials: Mapping containing `apiKey` and `secret`.

        Raises:
            ValueError: If required API credentials are missing.
        """
        super().__init__('bithumb', api_credentials)
        self.api_url = API_URL
        api_key = api_credentials.get('apiKey')
        api_secret = api_credentials.get('secret')
        if not api_key or not api_secret:
            raise ValueError("BithumbExchange requires apiKey and secret")
        self.api_key = api_key
        self.api_secret = api_secret
        
    def _generate_signature(self, endpoint: str, params: Mapping[str, str]) -> tuple[str, str]:
        """Generates an API signature for an authenticated request."""
        nonce = str(int(time.time() * 1000))
        data = endpoint + chr(0) + urlencode(params) + chr(0) + nonce
        h = hmac.new(
            self.api_secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha512
        )
        signature = base64.b64encode(h.hexdigest().encode('utf-8')).decode('utf-8')
        
        return signature, nonce
    
    def _request(
        self, endpoint: str, params: Optional[Mapping[str, str]] = None
    ) -> Optional[dict[str, Any]]:
        """Makes an authenticated Bithumb API request with retries."""
        request_params: dict[str, str] = dict(params) if params else {}
        
        for attempt in range(MAX_REQUEST_ATTEMPTS):
            try:
                signature, nonce = self._generate_signature(endpoint, request_params)
                
                headers = {
                    'Api-Key': self.api_key,
                    'Api-Sign': signature,
                    'Api-Nonce': nonce,
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                
                url = f"{self.api_url}{endpoint}"
                
                response = requests.post(
                    url, headers=headers, data=request_params, timeout=REQUEST_TIMEOUT_SECONDS
                )
                result = cast(dict[str, Any], response.json())
                
                # API 에러 체크
                if result.get('status') == '5100':
                    self.logger.error(f"API 키 오류: {result.get('message')}")
                    return None
                
                return result
                
            except Exception as e:
                self.logger.error(
                    "API 요청 실패 (%d/%d): %s", attempt + 1, MAX_REQUEST_ATTEMPTS, e
                )
                if attempt < MAX_REQUEST_ATTEMPTS - 1:
                    time.sleep(2 ** attempt)
                continue
        
        return None
    
    def get_krw_markets(self) -> list[str]:
        """Returns supported KRW markets from the public ticker endpoint."""
        try:
            response = requests.get(
                f"{self.api_url}/public/ticker/ALL_KRW", timeout=REQUEST_TIMEOUT_SECONDS
            )
            data = cast(dict[str, Any], response.json())
            
            if data['status'] == '0000':
                symbols = []
                for coin in data['data']:
                    if coin != 'date':
                        symbols.append(f"{coin}/KRW")
                return symbols
            else:
                self.logger.error(f"마켓 조회 실패: {data}")
                return []
        except Exception as e:
            self.logger.error(f"KRW 마켓 조회 실패: {e}")
            return []
    
    def get_ticker(self, symbol: str) -> Optional[dict[str, float]]:
        """Returns current ticker data for `symbol`."""
        try:
            coin = symbol.split('/')[0]
            
            ticker_response = requests.get(
                f"{self.api_url}/public/ticker/{coin}_KRW",
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            ticker_data = cast(dict[str, Any], ticker_response.json())
            
            if ticker_data['status'] != '0000':
                self.logger.error(f"가격 조회 실패: {ticker_data}")
                return None
            
            ticker_info = cast(dict[str, Any], ticker_data['data'])
            
            orderbook_response = requests.get(
                f"{self.api_url}/public/orderbook/{coin}_KRW",
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            orderbook_data = cast(dict[str, Any], orderbook_response.json())
            
            bid = 0.0
            ask = 0.0
            
            if orderbook_data['status'] == '0000' and 'data' in orderbook_data:
                orderbook_info = cast(dict[str, Any], orderbook_data['data'])
                bids = cast(list[dict[str, Any]], orderbook_info.get('bids', []))
                asks = cast(list[dict[str, Any]], orderbook_info.get('asks', []))
                
                if bids and len(bids) > 0:
                    bid = float(bids[0].get('price', 0.0))
                if asks and len(asks) > 0:
                    ask = float(asks[0].get('price', 0.0))
            
            return {
                'last': float(ticker_info.get('closing_price', 0.0)),
                'bid': bid,
                'ask': ask,
                'volume': float(ticker_info.get('units_traded_24H', 0.0))
            }
            
        except Exception as e:
            self.logger.error(f"가격 정보 조회 실패: {e}")
            return None

    
    def get_balance(self, currency: Optional[str] = None) -> dict[str, dict[str, float]]:
        """Returns balances for all currencies or a single currency."""
        try:
            params: dict[str, str] = {'currency': currency if currency else 'ALL'}
            response = self._request('/info/balance', params)
            
            if response and response['status'] == '0000':
                balances: dict[str, dict[str, float]] = {}
                data = cast(dict[str, Any], response['data'])
                
                if currency:
                    balances[currency] = {
                        'free': float(data[f'available_{currency.lower()}']),
                        'used': float(data[f'in_use_{currency.lower()}']),
                        'total': float(data[f'total_{currency.lower()}'])
                    }
                else:
                    # KRW 잔고
                    if 'total_krw' in data:
                        balances['KRW'] = {
                            'free': float(data.get('available_krw', 0.0)),
                            'used': float(data.get('in_use_krw', 0.0)),
                            'total': float(data.get('total_krw', 0.0))
                        }
                    
                    for key in data:
                        if key.startswith('total_') and not key.endswith('krw'):
                            coin = key.replace('total_', '').upper()
                            if float(data[key]) > 0:
                                balances[coin] = {
                                    'free': float(data.get(f'available_{coin.lower()}', 0.0)),
                                    'used': float(data.get(f'in_use_{coin.lower()}', 0.0)),
                                    'total': float(data[key])
                                }
                
                return balances
            else:
                self.logger.error(f"잔고 조회 실패: {response}")
                return {}
        except Exception as e:
            self.logger.error(f"잔고 조회 실패: {e}")
            return {}
    
    def market_buy_krw(self, symbol: str, krw_amount: float) -> Optional[dict[str, Any]]:
        """Places a market buy order based on a KRW amount."""
        try:
            coin = symbol.split('/')[0]
            
            if krw_amount < MIN_ORDER_KRW:
                self.logger.error(
                    "주문 금액이 최소 주문 금액(%d KRW) 미만: %.0f KRW",
                    MIN_ORDER_KRW,
                    krw_amount,
                )
                return None
            
            # 현재가 조회하여 수량 계산
            ticker = self.get_ticker(symbol)
            if not ticker:
                self.logger.error("가격 정보 조회 실패")
                return None
            
            # 수량 계산 (소수점 8자리까지 - 빗썸 기준)
            units = round(krw_amount / ticker['last'], 8)
            
            params = {
                'order_currency': coin,
                'payment_currency': 'KRW',
                'units': str(units),
                'type': 'bid'
            }
            
            response = self._request('/trade/market_buy', params)
            
            if response and response['status'] == '0000':
                self.logger.info(f"시장가 매수 성공: {symbol} 금액: {krw_amount} KRW, 수량: {units}")
                return {
                    'id': response['order_id'],
                    'symbol': symbol,
                    'side': 'buy',
                    'amount': units,
                    'filled': units,
                    'status': 'closed'
                }
            else:
                self.logger.error(f"시장가 매수 실패: {response}")
                return None
                
        except Exception as e:
            self.logger.error(f"시장가 매수 실패: {e}")
            return None
    
    def create_market_order(
        self, symbol: str, side: str, amount: float
    ) -> Optional[dict[str, Any]]:
        """Creates a market order."""
        try:
            coin = symbol.split('/')[0]
            
            params = {
                'order_currency': coin,
                'payment_currency': 'KRW',
                'units': str(amount)
            }
            
            if side == 'buy':
                params['type'] = 'bid'
                endpoint = '/trade/market_buy'
            else:
                params['type'] = 'ask'
                endpoint = '/trade/market_sell'
            
            response = self._request(endpoint, params)
            
            if response and response['status'] == '0000':
                self.logger.info(f"{side} 주문 생성 성공: {symbol} 수량: {amount}")
                return {
                    'id': response['order_id'],
                    'symbol': symbol,
                    'side': side,
                    'amount': amount,
                    'filled': amount,
                    'status': 'closed'
                }
            else:
                self.logger.error(f"주문 생성 실패: {response}")
                return None
                
        except Exception as e:
            self.logger.error(f"주문 생성 실패: {e}")
            return None
