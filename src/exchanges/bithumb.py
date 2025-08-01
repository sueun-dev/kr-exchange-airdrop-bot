"""
빗썸 거래소 클래스
"""
import hmac
import hashlib
import base64
import time
import requests
import json
from urllib.parse import urlencode
from .base import BaseExchange

class BithumbExchange(BaseExchange):
    """빗썸 거래소 구현"""
    
    def __init__(self, api_credentials):
        super().__init__('bithumb', api_credentials)
        self.api_url = 'https://api.bithumb.com'
        self.api_key = api_credentials.get('apiKey')
        self.api_secret = api_credentials.get('secret')
        
    def _generate_signature(self, endpoint, params):
        """
        빗썸 API 서명 생성
        """
        nonce = str(int(time.time() * 1000))
        data = endpoint + chr(0) + urlencode(params) + chr(0) + nonce
        h = hmac.new(self.api_secret.encode('utf-8'), data.encode('utf-8'), hashlib.sha512)
        signature = base64.b64encode(h.hexdigest().encode('utf-8')).decode('utf-8')
        
        return signature, nonce
    
    def _request(self, endpoint, params=None, retry_count=3):
        """
        빗썸 API 요청 (재시도 로직 포함)
        """
        if params is None:
            params = {}
        
        for attempt in range(retry_count):
            try:
                signature, nonce = self._generate_signature(endpoint, params)
                
                headers = {
                    'Api-Key': self.api_key,
                    'Api-Sign': signature,
                    'Api-Nonce': nonce,
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                
                url = f"{self.api_url}{endpoint}"
                
                response = requests.post(url, headers=headers, data=params, timeout=10)
                result = response.json()
                
                # API 에러 체크
                if result.get('status') == '5100':
                    self.logger.error(f"API 키 오류: {result.get('message')}")
                    return None
                
                return result
                
            except requests.exceptions.Timeout:
                self.logger.warning(f"요청 타임아웃 ({attempt + 1}/{retry_count})")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)  # 지수 백오프
                continue
                
            except Exception as e:
                self.logger.error(f"API 요청 실패 ({attempt + 1}/{retry_count}): {e}")
                if attempt < retry_count - 1:
                    time.sleep(2 ** attempt)
                continue
        
        return None
    
    def get_krw_markets(self):
        """
        KRW 마켓 코인 목록 조회
        
        Returns:
            list: KRW 마켓 심볼 리스트
        """
        try:
            # 빗썸은 기본적으로 모든 마켓이 KRW
            response = requests.get(f"{self.api_url}/public/ticker/ALL_KRW")
            data = response.json()
            
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
    
    def get_ticker(self, symbol):
        """
        현재가 정보 조회
        
        Args:
            symbol: 거래 심볼
            
        Returns:
            dict: 가격 정보
        """
        try:
            coin = symbol.split('/')[0]
            
            # Ticker 정보 조회
            ticker_response = requests.get(f"{self.api_url}/public/ticker/{coin}_KRW")
            ticker_data = ticker_response.json()
            
            if ticker_data['status'] != '0000':
                self.logger.error(f"가격 조회 실패: {ticker_data}")
                return None
            
            ticker_info = ticker_data['data']
            
            # Orderbook 정보 조회하여 매수/매도 호가 가져오기
            orderbook_response = requests.get(f"{self.api_url}/public/orderbook/{coin}_KRW")
            orderbook_data = orderbook_response.json()
            
            bid = 0
            ask = 0
            
            if orderbook_data['status'] == '0000' and 'data' in orderbook_data:
                bids = orderbook_data['data'].get('bids', [])
                asks = orderbook_data['data'].get('asks', [])
                
                if bids and len(bids) > 0:
                    bid = float(bids[0]['price'])
                if asks and len(asks) > 0:
                    ask = float(asks[0]['price'])
            
            return {
                'last': float(ticker_info.get('closing_price', 0)),
                'bid': bid,
                'ask': ask,
                'volume': float(ticker_info.get('units_traded_24H', 0))
            }
            
        except Exception as e:
            self.logger.error(f"가격 정보 조회 실패: {e}")
            return None
    
    def get_usdt_krw_price(self):
        """
        USDT/KRW 가격 조회 (빗썸은 USDT 거래 미지원)
        
        Returns:
            float: None
        """
        return None
    
    def get_funding_rate(self, symbol):
        """
        펀딩 수수료율 조회 (빗썸은 현물 거래소라 해당 없음)
        
        Returns:
            float: 0
        """
        return 0
    
    def get_balance(self, currency=None):
        """
        잔고 조회
        
        Args:
            currency: 특정 통화 (None이면 전체 조회)
            
        Returns:
            dict: 잔고 정보
        """
        try:
            params = {'currency': currency if currency else 'ALL'}
            response = self._request('/info/balance', params)
            
            if response and response['status'] == '0000':
                balances = {}
                data = response['data']
                
                if currency:
                    balances[currency] = {
                        'free': float(data[f'available_{currency.lower()}']),
                        'used': float(data[f'in_use_{currency.lower()}']),
                        'total': float(data[f'total_{currency.lower()}'])
                    }
                else:
                    # 전체 잔고 파싱
                    # KRW 잔고
                    if 'total_krw' in data:
                        balances['KRW'] = {
                            'free': float(data.get('available_krw', 0)),
                            'used': float(data.get('in_use_krw', 0)),
                            'total': float(data.get('total_krw', 0))
                        }
                    
                    # 코인 잔고
                    for key in data:
                        if key.startswith('total_') and not key.endswith('krw'):
                            coin = key.replace('total_', '').upper()
                            if float(data[key]) > 0:
                                balances[coin] = {
                                    'free': float(data.get(f'available_{coin.lower()}', 0)),
                                    'used': float(data.get(f'in_use_{coin.lower()}', 0)),
                                    'total': float(data[key])
                                }
                
                return balances
            else:
                self.logger.error(f"잔고 조회 실패: {response}")
                return {}
        except Exception as e:
            self.logger.error(f"잔고 조회 실패: {e}")
            return {}
    
    def market_buy_krw(self, symbol, krw_amount):
        """
        KRW 금액 기반 시장가 매수
        
        Args:
            symbol: 거래 심볼
            krw_amount: 매수할 KRW 금액
            
        Returns:
            dict: 주문 결과
        """
        try:
            coin = symbol.split('/')[0]
            
            # 최소 주문 금액 확인 (1000 KRW)
            if krw_amount < 1000:
                self.logger.error(f"주문 금액이 최소 주문 금액(1000 KRW) 미만: {krw_amount:.0f} KRW")
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
                'type': 'bid'  # 매수
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
    
    def create_market_order(self, symbol, side, amount):
        """
        시장가 주문 생성
        
        Args:
            symbol: 거래 심볼
            side: buy/sell
            amount: 주문 수량 (코인 수량)
            
        Returns:
            dict: 주문 결과
        """
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