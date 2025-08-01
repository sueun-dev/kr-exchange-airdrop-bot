"""
거래소 기본 클래스
모든 거래소가 상속받는 베이스 클래스입니다.
"""
import ccxt
from abc import ABC, abstractmethod
import logging

class BaseExchange(ABC):
    """거래소 기본 클래스"""
    
    def __init__(self, exchange_id, api_credentials):
        """
        거래소 초기화
        
        Args:
            exchange_id: 거래소 ID (upbit, bithumb, okx, gateio)
            api_credentials: API 인증 정보
        """
        self.exchange_id = exchange_id
        self.name = exchange_id
        self.logger = logging.getLogger(f'exchange.{exchange_id}')
        
        # 빗썸은 CCXT 대신 직접 구현 사용
        if exchange_id != 'bithumb':
            # CCXT 거래소 객체 생성
            exchange_class = getattr(ccxt, exchange_id)
            self.exchange = exchange_class(api_credentials)
            
            # 테스트 모드 설정 (실제 거래 전까지는 True)
            # 한국 거래소는 샌드박스 모드 지원 안함
            if exchange_id not in ['upbit', 'bithumb']:
                self.exchange.setSandboxMode(False)  # 실제 거래 모드
        
    def get_markets(self):
        """
        거래 가능한 마켓 정보 조회
        
        Returns:
            dict: 마켓 정보
        """
        try:
            return self.exchange.load_markets()
        except Exception as e:
            self.logger.error(f"마켓 정보 조회 실패: {e}")
            return {}
    
    def get_ticker(self, symbol):
        """
        현재 가격 정보 조회
        
        Args:
            symbol: 거래 심볼 (예: BTC/USDT)
            
        Returns:
            dict: 가격 정보
        """
        try:
            return self.exchange.fetch_ticker(symbol)
        except Exception as e:
            self.logger.error(f"{symbol} 가격 조회 실패: {e}")
            return None
    
    def get_balance(self):
        """
        계좌 잔고 조회
        
        Returns:
            dict: 잔고 정보
        """
        try:
            return self.exchange.fetch_balance()
        except Exception as e:
            self.logger.error(f"잔고 조회 실패: {e}")
            return None
    
    def create_market_order(self, symbol, side, amount):
        """
        시장가 주문 생성
        
        Args:
            symbol: 거래 심볼
            side: 'buy' 또는 'sell'
            amount: 주문 수량
            
        Returns:
            dict: 주문 결과
        """
        try:
            # Gate.io의 경우 시장가 매수 시 특별 처리
            if self.exchange_id == 'gateio' and side == 'buy' and '/USDT' in symbol:
                ticker = self.exchange.fetch_ticker(symbol)
                if ticker:
                    # Gate.io는 시장가 매수 시 금액으로 주문
                    cost = amount * ticker['last']  # USDT 금액
                    order = self.exchange.create_market_order(
                        symbol, side, cost,  # 금액으로 주문
                        params={'createMarketBuyOrderRequiresPrice': False}
                    )
                else:
                    raise Exception("가격 정보 조회 실패")
            else:
                order = self.exchange.create_market_order(symbol, side, amount)
                
            self.logger.info(f"주문 생성 성공: {symbol} {side} {amount}")
            return order
        except Exception as e:
            self.logger.error(f"주문 생성 실패: {e}")
            return None
    
    @abstractmethod
    def get_usdt_krw_price(self):
        """
        USDT/KRW 가격 조회 (한국 거래소만 구현)
        
        Returns:
            float: USDT 원화 가격
        """
        pass
    
    @abstractmethod
    def get_funding_rate(self, symbol):
        """
        펀딩 수수료율 조회 (해외 거래소만 구현)
        
        Args:
            symbol: 거래 심볼
            
        Returns:
            float: 펀딩 수수료율
        """
        pass