"""
업비트 거래소 클래스
"""
from .base import BaseExchange

class UpbitExchange(BaseExchange):
    """업비트 거래소 구현"""
    
    def __init__(self, api_credentials):
        super().__init__('upbit', api_credentials)
        
    def get_usdt_krw_price(self):
        """
        USDT/KRW 가격 조회
        
        Returns:
            float: USDT 원화 가격
        """
        try:
            ticker = self.exchange.fetch_ticker('USDT/KRW')
            return ticker['last']
        except Exception as e:
            self.logger.error(f"USDT/KRW 가격 조회 실패: {e}")
            return None
    
    def get_funding_rate(self, symbol):
        """
        펀딩 수수료율 조회 (업비트는 현물 거래소라 해당 없음)
        
        Returns:
            float: 0
        """
        return 0
    
    def get_krw_markets(self):
        """
        KRW 마켓 코인 목록 조회
        
        Returns:
            list: KRW 마켓 심볼 리스트
        """
        try:
            markets = self.get_markets()
            krw_symbols = []
            
            for symbol, market in markets.items():
                if market['quote'] == 'KRW' and market['active']:
                    krw_symbols.append(symbol)
                    
            return krw_symbols
        except Exception as e:
            self.logger.error(f"KRW 마켓 조회 실패: {e}")
            return []
    
    def create_market_order(self, symbol, side, amount):
        """
        시장가 주문 생성
        업비트는 매수 시 금액 기반 주문
        
        Args:
            symbol: 거래 심볼
            side: buy/sell
            amount: 주문 수량 (매수 시 KRW 금액, 매도 시 코인 수량)
            
        Returns:
            dict: 주문 결과
        """
        try:
            if side == 'buy':
                # 업비트 매수는 금액 기반이므로 수량에서 금액으로 변환
                ticker = self.get_ticker(symbol)
                if not ticker:
                    self.logger.error("가격 정보 조회 실패")
                    return None
                
                krw_amount = amount * ticker['last']
                
                # 최소 주문 금액 확인 (5000 KRW)
                if krw_amount < 5000:
                    self.logger.error(f"주문 금액이 최소 주문 금액(5000 KRW) 미만: {krw_amount:.0f} KRW")
                    return None
                
                # 업비트 시장가 매수
                order = self.exchange.create_order(
                    symbol=symbol,
                    type='market',
                    side='buy',
                    amount=None,
                    params={'cost': krw_amount}  # 업비트는 cost 파라미터로 금액 지정
                )
                
                # 주문 성공 시 요청한 수량을 반환
                if order:
                    order['filled'] = amount
                    order['amount'] = amount
            else:
                # 매도는 일반적인 방식
                order = self.exchange.create_market_order(symbol, side, amount)
            
            self.logger.info(f"{side} 주문 생성 성공: {symbol} 요청수량: {amount}, 체결수량: {order.get('filled', 0)}")
            self.logger.debug(f"주문 응답 전체: {order}")
            return order
        except Exception as e:
            self.logger.error(f"주문 생성 실패: {e}")
            return None
    
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
            # 최소 주문 금액 확인 (5000 KRW)
            if krw_amount < 5000:
                self.logger.error(f"주문 금액이 최소 주문 금액(5000 KRW) 미만: {krw_amount:.0f} KRW")
                return None
            
            # 업비트 시장가 매수
            order = self.exchange.create_order(
                symbol=symbol,
                type='market',
                side='buy',
                amount=None,
                params={'cost': krw_amount}  # 업비트는 cost 파라미터로 금액 지정
            )
            
            self.logger.info(f"시장가 매수 성공: {symbol} 금액: {krw_amount} KRW")
            return order
        except Exception as e:
            self.logger.error(f"시장가 매수 실패: {e}")
            return None