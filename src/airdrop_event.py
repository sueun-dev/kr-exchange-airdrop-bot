"""에어드랍 이벤트 자동 참여 시스템 모듈.

빗썸 거래소에서 에어드랍 이벤트에 자동으로 참여하는 봇을 제공합니다.
단일 계정과 다중 계정 모두 지원합니다.
"""

import logging
import os
import queue
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

from exchanges.bithumb import BithumbExchange

# 환경 변수 로드
load_dotenv()

# 로깅 설정
log_dir = Path(__file__).parent.parent / 'logs'
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_dir / 'airdrop_event.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('AirdropEvent')

class AirdropBot:
    """에어드랍 이벤트 자동 참여 봇.
    
    빗썸 거래소에서 에어드랍 이벤트에 자동으로 참여합니다.
    단일 계정과 다중 계정 모두 지원합니다.
    
    Attributes:
        exchange_name: 거래소 이름 (현재는 'bithumb'만 지원)
        accounts: 로드된 계정 정보 리스트
        trade_amount: 거래 금액 (KRW)
        wait_time: 매수 후 대기 시간 (초)
        results: 거래 결과를 저장하는 큐
    """
    
    def __init__(self, exchange_name: str = 'bithumb') -> None:
        """AirdropBot을 초기화합니다.
        
        Args:
            exchange_name: 거래소 이름 (기본값: 'bithumb')
        """
        self.exchange_name = exchange_name
        self.accounts = self._load_accounts()
        self.trade_amount = float(os.getenv('DEFAULT_TRADE_AMOUNT', 5500))
        self.wait_time = int(os.getenv('WAIT_TIME_SECONDS', 2))
        self.results: queue.Queue = queue.Queue()
        
    def _load_accounts(self) -> List[Dict[str, str]]:
        """환경 변수에서 계정 정보를 로드합니다.
        
        환경 변수에서 API 키를 찾아 계정 정보를 생성합니다.
        BITHUMB_API_KEY_1, BITHUMB_API_KEY_2 형식의 다중 계정과
        BITHUMB_API_KEY 형식의 단일 계정을 모두 지원합니다.
        
        Returns:
            계정 정보 딕셔너리의 리스트
        """
        accounts = []
        account_num = 1
        
        while True:
            # BITHUMB_API_KEY_1, BITHUMB_API_KEY_2, ... 형식으로 찾기
            api_key = os.getenv(f'BITHUMB_API_KEY_{account_num}')
            api_secret = os.getenv(f'BITHUMB_SECRET_KEY_{account_num}')
            
            if not api_key or not api_secret:
                # 번호 없는 기본 키도 확인
                if account_num == 1:
                    api_key = os.getenv('BITHUMB_API_KEY')
                    api_secret = os.getenv('BITHUMB_SECRET_KEY')
                    if api_key and api_secret:
                        accounts.append({
                            'account_id': 'main',
                            'api_key': api_key.strip("'\""),
                            'api_secret': api_secret.strip("'\"")
                        })
                break
            
            accounts.append({
                'account_id': f'account_{account_num}',
                'api_key': api_key.strip("'\""),
                'api_secret': api_secret.strip("'\"")
            })
            account_num += 1
        
        logger.info(f"로드된 계정 수: {len(accounts)}")
        return accounts
    
    def participate_event_single(self, account_info: Dict[str, str], symbol: str) -> bool:
        """단일 계정으로 이벤트 참여합니다.
        
        지정된 계정으로 에어드랍 이벤트에 참여합니다.
        매수 → 대기 → 매도 순서로 진행됩니다.
        
        Args:
            account_info: 계정 정보 딕셔너리
                - account_id: 계정 식별자
                - api_key: API 키
                - api_secret: API 시크릿
            symbol: 거래할 코인 심볼 (예: 'BTC', 'ETH')
            
        Returns:
            거래 성공 여부
        """
        account_id = account_info['account_id']
        
        try:
            logger.info(f"[{account_id}] 에어드랍 이벤트 시작")
            
            # 거래소 초기화
            credentials = {
                'apiKey': account_info['api_key'],
                'secret': account_info['api_secret']
            }
            exchange = BithumbExchange(credentials)
            
            # 심볼 포맷 조정
            if '/' not in symbol:
                symbol = f"{symbol.upper()}/KRW"
            
            # 1. 초기 잔고 확인
            initial_balance = exchange.get_balance()
            if initial_balance and 'KRW' in initial_balance:
                krw_balance = initial_balance['KRW']['free']
                logger.info(f"[{account_id}] KRW 잔고: {krw_balance:,.0f} KRW")
            
            # 2. 시장가 매수
            logger.info(f"[{account_id}] {symbol} 매수 시작 ({self.trade_amount:,.0f} KRW)")
            buy_order = exchange.market_buy_krw(symbol, self.trade_amount)
            
            if not buy_order:
                logger.error(f"[{account_id}] 매수 실패")
                self.results.put({
                    'account': account_id,
                    'success': False,
                    'error': '매수 실패'
                })
                return False
            
            logger.info(f"[{account_id}] 매수 완료: {buy_order}")
            
            # 3. 대기
            time.sleep(self.wait_time)
            
            # 4. 잔고 확인 및 전량 매도
            coin = symbol.split('/')[0]
            balance = None
            available_amount = 0
            
            # 잔고 확인 재시도
            for retry in range(3):
                balance = exchange.get_balance(coin)
                
                if balance and coin in balance:
                    available_amount = balance[coin]['free']
                    if available_amount > 0:
                        break
                
                if retry < 2:
                    time.sleep(2)
            
            if not available_amount:
                logger.error(f"[{account_id}] {coin} 잔고 없음")
                self.results.put({
                    'account': account_id,
                    'success': False,
                    'error': '매도할 잔고 없음'
                })
                return False
            
            # 5. 시장가 매도
            logger.info(f"[{account_id}] {coin} 매도 시작 (수량: {available_amount})")
            sell_order = exchange.create_market_order(symbol, 'sell', available_amount)
            
            if not sell_order:
                logger.error(f"[{account_id}] 매도 실패")
                self.results.put({
                    'account': account_id,
                    'success': False,
                    'error': '매도 실패'
                })
                return False
            
            logger.info(f"[{account_id}] 매도 완료: {sell_order}")
            
            # 6. 최종 잔고 확인
            final_balance = exchange.get_balance()
            if final_balance and 'KRW' in final_balance:
                final_krw = final_balance['KRW']['free']
                logger.info(f"[{account_id}] 최종 KRW 잔고: {final_krw:,.0f} KRW")
            
            self.results.put({
                'account': account_id,
                'success': True,
                'buy_order': buy_order,
                'sell_order': sell_order
            })
            
            logger.info(f"[{account_id}] 에어드랍 이벤트 완료 ✅")
            return True
            
        except Exception as e:
            logger.error(f"[{account_id}] 오류 발생: {e}")
            self.results.put({
                'account': account_id,
                'success': False,
                'error': str(e)
            })
            return False
    
    def participate_all_accounts(self, symbol: str, max_workers: int = 5) -> None:
        """모든 계정으로 동시에 이벤트 참여합니다.
        
        ThreadPoolExecutor를 사용하여 여러 계정으로 동시에
        에어드랍 이벤트에 참여합니다.
        
        Args:
            symbol: 거래할 코인 심볼 (예: 'BTC', 'ETH')
            max_workers: 동시 실행할 최대 스레드 수 (기본값: 5)
        """
        logger.info(f"=== 다중 계정 에어드랍 시작 ===")
        logger.info(f"참여 계정 수: {len(self.accounts)}")
        logger.info(f"거래 심볼: {symbol}")
        logger.info(f"거래 금액: {self.trade_amount:,.0f} KRW")
        
        if not self.accounts:
            logger.error("등록된 계정이 없습니다")
            return
        
        # ThreadPoolExecutor로 동시 실행
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 각 계정별로 작업 제출
            futures = {
                executor.submit(self.participate_event_single, account, symbol): account
                for account in self.accounts
            }
            
            # 완료된 작업 처리
            for future in as_completed(futures):
                account = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"[{account['account_id']}] 작업 실행 중 오류: {e}")
        
        # 결과 집계
        logger.info("\n=== 실행 결과 ===")
        success_count = 0
        fail_count = 0
        
        while not self.results.empty():
            result = self.results.get()
            if result['success']:
                success_count += 1
                logger.info(f"✅ {result['account']}: 성공")
            else:
                fail_count += 1
                logger.error(f"❌ {result['account']}: 실패 ({result.get('error', '알 수 없는 오류')})")
        
        logger.info(f"\n총 {len(self.accounts)}개 계정 중 성공: {success_count}, 실패: {fail_count}")

