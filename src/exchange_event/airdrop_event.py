"""Airdrop event participation bot."""

from __future__ import annotations

import logging
import os
import queue
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import Any, Optional, cast

import requests

from exchange_event.exchanges.base import BaseExchange
from exchange_event.exchanges.bithumb import BithumbExchange
from exchange_event.types import AccountInfo, CleanupResults, SmallHolding, TradeResult


logger = logging.getLogger(__name__)

BALANCE_RETRY_COUNT = 3
BALANCE_RETRY_DELAY_SECONDS = 2
CLEANUP_BUY_AMOUNT_KRW = 5500
SMALL_HOLDING_MAX_VALUE_KRW = 5000
REQUEST_TIMEOUT_SECONDS = 10


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
            exchange_name: 거래소 이름 ('bithumb'만 지원)
        """
        self.exchange_name = exchange_name
        self.accounts: list[AccountInfo] = self._load_accounts()
        self.trade_amount = float(os.getenv('DEFAULT_TRADE_AMOUNT', 5500))
        self.wait_time = int(os.getenv('WAIT_TIME_SECONDS', 2))
        self.results: queue.Queue[TradeResult] = queue.Queue()
        
    def _get_env_keys(self) -> list[str]:
        """환경변수 키 접두사를 반환합니다.

        Returns:
            환경변수 키 접두사 리스트
        """
        return ['BITHUMB_API_KEY', 'BITHUMB_SECRET_KEY']
    
    def _create_account_dict(
        self, account_id: str, api_key: str, api_secret: str
    ) -> AccountInfo:
        """계정 정보 딕셔너리를 생성합니다.
        
        Args:
            account_id: 계정 식별자
            api_key: API 키
            api_secret: API 시크릿
            
        Returns:
            계정 정보 딕셔너리
        """
        return {
            'account_id': account_id,
            'api_key': api_key.strip("'\""),
            'api_secret': api_secret.strip("'\"")
        }
    
    def _load_all_accounts(self, key_prefixes: list[str]) -> list[AccountInfo]:
        """모든 계정 정보를 로드합니다 (단일 및 다중 계정 모두 지원).

        Args:
            key_prefixes: API 키와 시크릿 키의 환경변수 이름 접두사

        Returns:
            계정 정보 리스트
        """
        accounts: list[AccountInfo] = []

        account_num = 1
        while True:
            api_key = os.getenv(f'{key_prefixes[0]}_{account_num}')
            api_secret = os.getenv(f'{key_prefixes[1]}_{account_num}')

            if not api_key or not api_secret:
                break

            accounts.append(
                self._create_account_dict(f'account_{account_num}', api_key, api_secret)
            )
            account_num += 1

        if accounts:
            return accounts

        api_key = os.getenv(key_prefixes[0])
        api_secret = os.getenv(key_prefixes[1])
        if api_key and api_secret:
            return [self._create_account_dict('account_1', api_key, api_secret)]

        return []
    
    def _load_accounts(self) -> list[AccountInfo]:
        """환경 변수에서 계정 정보를 로드합니다.

        환경 변수에서 API 키를 찾아 계정 정보를 생성합니다.
        단일 계정과 다중 계정을 모두 지원합니다.

        Returns:
            계정 정보 딕셔너리의 리스트
        """
        env_keys = self._get_env_keys()
        accounts = self._load_all_accounts(env_keys)

        logger.info(f"로드된 계정 수: {len(accounts)}")
        return accounts
    
    def create_exchange(self, account_info: AccountInfo) -> BaseExchange:
        """계정 정보를 바탕으로 거래소 객체를 생성합니다.

        Args:
            account_info: 계정 정보.

        Returns:
            거래소 객체.
        """
        credentials = {'apiKey': account_info['api_key'], 'secret': account_info['api_secret']}
        return BithumbExchange(credentials)
    
    def _execute_buy_order(
        self, exchange: BaseExchange, symbol: str, account_id: str
    ) -> Optional[dict[str, Any]]:
        """매수 주문을 실행합니다.
        
        Args:
            exchange: 거래소 객체
            symbol: 거래 심볼
            account_id: 계정 ID
            
        Returns:
            매수 주문 결과 또는 None
        """
        logger.info(f"[{account_id}] {symbol} 매수 시작 ({self.trade_amount:,.0f} KRW)")
        buy_order = exchange.market_buy_krw(symbol, self.trade_amount)
        
        if buy_order:
            logger.info(f"[{account_id}] 매수 완료: {buy_order}")
        else:
            logger.error(f"[{account_id}] 매수 실패")
            
        return buy_order
    
    def _wait_for_balance(self, exchange: BaseExchange, coin: str, account_id: str) -> float:
        """매수 후 잔고를 확인합니다. 최대 3회 재시도합니다.
        
        Args:
            exchange: 거래소 객체
            coin: 코인 심볼
            account_id: 계정 ID
            
        Returns:
            사용 가능한 코인 수량
        """
        available_amount = 0.0
        
        for retry in range(BALANCE_RETRY_COUNT):
            balance = exchange.get_balance()
            
            if balance and coin in balance:
                available_amount = balance[coin]['free']
                if available_amount > 0:
                    break
            
            if retry < BALANCE_RETRY_COUNT - 1:
                time.sleep(BALANCE_RETRY_DELAY_SECONDS)
        
        if not available_amount:
            logger.error(f"[{account_id}] {coin} 잔고 없음")
        
        return available_amount
    
    def _execute_sell_order(
        self, exchange: BaseExchange, symbol: str, amount: float, account_id: str
    ) -> Optional[dict[str, Any]]:
        """매도 주문을 실행합니다.
        
        Args:
            exchange: 거래소 객체
            symbol: 거래 심볼
            amount: 매도 수량
            account_id: 계정 ID
            
        Returns:
            매도 주문 결과 또는 None
        """
        logger.info(f"[{account_id}] {symbol} 매도 시작 (수량: {amount})")
        sell_order = exchange.create_market_order(symbol, 'sell', amount)
        
        if sell_order:
            logger.info(f"[{account_id}] 매도 완료: {sell_order}")
        else:
            logger.error(f"[{account_id}] 매도 실패")
            
        return sell_order
    
    def _report_result(
        self,
        account_id: str,
        symbol: str,
        success: bool,
        buy_order: Optional[dict[str, Any]] = None,
        sell_order: Optional[dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """거래 결과를 결과 큐에 추가합니다.
        
        Args:
            account_id: 계정 ID
            symbol: 거래 심볼
            success: 성공 여부
            buy_order: 매수 주문 결과
            sell_order: 매도 주문 결과
            error: 오류 메시지
        """
        result: TradeResult = {
            'account': account_id,
            'symbol': symbol,
            'success': success
        }
        
        if buy_order is not None:
            result['buy_order'] = buy_order
        if sell_order is not None:
            result['sell_order'] = sell_order
        if error:
            result['error'] = error
            
        self.results.put(result)
    
    def participate_event_single(self, account_info: AccountInfo, symbol: str) -> bool:
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
            
            exchange = self.create_exchange(account_info)
            symbol = f"{symbol.upper()}/KRW"
            
            self._log_balance(exchange, account_id, "초기")
            
            buy_order = self._execute_buy_order(exchange, symbol, account_id)
            if not buy_order:
                self._report_result(account_id, symbol, False, error='매수 실패')
                return False
            
            time.sleep(self.wait_time)
            
            coin = symbol.split('/')[0]
            available_amount = self._wait_for_balance(exchange, coin, account_id)
            
            if not available_amount:
                self._report_result(account_id, symbol, False, 
                                  buy_order=buy_order, error='매도할 잔고 없음')
                return False
            
            sell_order = self._execute_sell_order(exchange, symbol, available_amount, account_id)
            if not sell_order:
                self._report_result(account_id, symbol, False, 
                                  buy_order=buy_order, error='매도 실패')
                return False
            
            self._log_balance(exchange, account_id, "최종")
            
            self._report_result(account_id, symbol, True, 
                              buy_order=buy_order, sell_order=sell_order)
            logger.info(f"[{account_id}] 에어드랍 이벤트 완료 ✅")
            return True
            
        except Exception as e:
            logger.error(f"[{account_id}] 오류 발생: {e}")
            self._report_result(account_id, symbol, False, error=str(e))
            return False
    
    def _log_balance(self, exchange: BaseExchange, account_id: str, prefix: str = "") -> None:
        """KRW 잔고를 로깅합니다.
        
        Args:
            exchange: 거래소 객체
            account_id: 계정 ID
            prefix: 로그 메시지 앞에 붙일 문자열
        """
        balance = exchange.get_balance()
        if balance and 'KRW' in balance:
            krw_balance = balance['KRW'].get('free', 0.0)
            logger.info(f"[{account_id}] {prefix} KRW 잔고: {krw_balance:,.0f} KRW")
    
    def _execute_parallel_tasks(
        self, accounts: list[AccountInfo], symbols: list[str], max_workers: int
    ) -> None:
        """여러 계정과 심볼에 대해 병렬로 작업을 실행합니다.
        
        Args:
            accounts: 계정 정보 리스트
            symbols: 거래할 코인 심볼 리스트
            max_workers: 동시 실행할 최대 스레드 수
        """
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: dict[Future[bool], tuple[AccountInfo, str]] = {}
            for account in accounts:
                for symbol in symbols:
                    future = executor.submit(self.participate_event_single, account, symbol)
                    futures[future] = (account, symbol)
            
            for future in as_completed(futures):
                account, symbol = futures[future]
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"[{account['account_id']}] {symbol} 작업 실행 중 오류: {e}")
    
    def _collect_results(self) -> tuple[int, int, dict[str, dict[str, int]]]:
        """결과 큐에서 결과를 수집하고 집계합니다.
        
        Returns:
            성공 카운트, 실패 카운트, 코인별 결과 딕셔너리
        """
        success_count = 0
        fail_count = 0
        coin_results: dict[str, dict[str, int]] = {}
        
        while not self.results.empty():
            result = self.results.get()
            symbol = result['symbol'].split('/')[0]
            
            if symbol not in coin_results:
                coin_results[symbol] = {'success': 0, 'fail': 0}
            
            if result['success']:
                success_count += 1
                coin_results[symbol]['success'] += 1
                logger.info(f"✅ {result['account']} - {symbol}: 성공")
            else:
                fail_count += 1
                coin_results[symbol]['fail'] += 1
                logger.error(f"❌ {result['account']} - {symbol}: 실패 ({result.get('error', '알 수 없는 오류')})")
        
        return success_count, fail_count, coin_results
    
    def _log_summary(
        self,
        accounts: list[AccountInfo],
        symbols: list[str],
        success_count: int,
        fail_count: int,
        coin_results: dict[str, dict[str, int]],
    ) -> None:
        """실행 결과 요약을 로깅합니다.
        
        Args:
            accounts: 계정 정보 리스트
            symbols: 거래한 코인 심볼 리스트
            success_count: 성공한 작업 수
            fail_count: 실패한 작업 수
            coin_results: 코인별 결과
        """
        total_tasks = len(accounts) * len(symbols)
        logger.info(f"\n=== 전체 결과 요약 ===")
        logger.info(f"총 작업 수: {total_tasks} (계정 {len(accounts)}개 × 코인 {len(symbols)}개)")
        logger.info(f"성공: {success_count}, 실패: {fail_count}")
        
        if len(symbols) > 1:
            logger.info("\n코인별 결과:")
            for symbol in symbols:
                if symbol in coin_results:
                    logger.info(f"  {symbol}: 성공 {coin_results[symbol]['success']}, 실패 {coin_results[symbol]['fail']}")
    
    def participate_all_accounts(
        self,
        symbols: list[str],
        max_workers: int = 5,
        accounts: Optional[list[AccountInfo]] = None,
    ) -> None:
        """모든 계정으로 동시에 이벤트 참여합니다.
        
        ThreadPoolExecutor를 사용하여 여러 계정으로 동시에
        에어드랍 이벤트에 참여합니다.
        
        Args:
            symbols: 거래할 코인 심볼 리스트 (예: ['BTC', 'ETH'])
            max_workers: 동시 실행할 최대 스레드 수 (기본값: 5)
            accounts: 사용할 계정 리스트 (기본값: 모든 계정)
        """
        if accounts is None:
            accounts = self.accounts
        
        # 초기 정보 로깅
        logger.info(f"=== 다중 계정 에어드랍 시작 ===")
        logger.info(f"참여 계정 수: {len(accounts)}")
        logger.info(f"거래 심볼: {', '.join(symbols)}")
        logger.info(f"거래 금액: {self.trade_amount:,.0f} KRW (코인당)")
        
        if not accounts:
            logger.error("참여할 계정이 없습니다")
            return
        
        # 병렬 작업 실행
        self._execute_parallel_tasks(accounts, symbols, max_workers)
        
        # 결과 수집 및 요약
        logger.info("\n=== 실행 결과 ===")
        success_count, fail_count, coin_results = self._collect_results()
        
        # 결과 요약 로깅
        self._log_summary(accounts, symbols, success_count, fail_count, coin_results)
    
    def _fetch_price_data(self, account_id: str) -> Optional[dict[str, Any]]:
        """빗썸 API에서 현재 시세 정보를 가져옵니다.
        
        Args:
            account_id: 계정 ID (로깅용)
            
        Returns:
            가격 정보 딕셔너리 또는 None
        """
        try:
            ticker_response = requests.get(
                "https://api.bithumb.com/public/ticker/ALL_KRW",
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            ticker_data = cast(dict[str, Any], ticker_response.json())
            
            if ticker_data['status'] != '0000':
                logger.error(f"[{account_id}] 시세 조회 실패")
                return None
                
            return cast(dict[str, Any], ticker_data['data'])
        except Exception as e:
            logger.error(f"[{account_id}] 시세 조회 중 오류: {e}")
            return None
    
    def _identify_small_holdings(
        self,
        balance: dict[str, dict[str, float]],
        prices: dict[str, Any],
        account_id: str,
    ) -> list[SmallHolding]:
        """잔고에서 5천원 이하의 소액 코인을 식별합니다.
        
        Args:
            balance: 계정 잔고 정보
            prices: 현재 시세 정보
            account_id: 계정 ID (로깅용)
            
        Returns:
            소액 코인 정보 리스트
        """
        small_holdings: list[SmallHolding] = []
        
        for coin, info in balance.items():
            if coin == 'KRW':
                continue
                
            amount = float(info.get('free', 0.0))
            if amount <= 0:
                continue
                
            coin_key = coin.upper()

            price_info = prices.get(coin_key)
            if not isinstance(price_info, dict):
                logger.warning(f"[{account_id}] {coin} 시세 정보 없음 (보유: {amount:.8f}개)")
                continue
                
            if 'closing_price' not in price_info:
                continue
                
            try:
                current_price = float(price_info['closing_price'])
                total_value = amount * current_price
                
                logger.info(f"[{account_id}] {coin}: 수량={amount:.8f}, 현재가={current_price:,.0f}원, 평가금액={total_value:,.0f}원")
                
                if 0 < total_value < SMALL_HOLDING_MAX_VALUE_KRW:
                    small_holdings.append({
                        'coin': coin,
                        'amount': amount,
                        'value': total_value
                    })
                    logger.info(f"[{account_id}] ⚠️  소액 코인 발견: {coin} - {total_value:,.0f}원")
            except Exception as e:
                logger.error(f"[{account_id}] {coin} 가격 계산 오류: {e}")
                
        return small_holdings
    
    def _process_single_coin_cleanup(
        self, exchange: BaseExchange, coin: str, account_id: str
    ) -> bool:
        """단일 코인에 대해 추가 매수 후 전량 매도를 수행합니다.
        
        Args:
            exchange: 거래소 객체
            coin: 코인 심볼
            account_id: 계정 ID (로깅용)
            
        Returns:
            성공 여부
        """
        symbol = f"{coin}/KRW"
        
        # 5,500원 추가 매수
        buy_order = exchange.market_buy_krw(symbol, CLEANUP_BUY_AMOUNT_KRW)
        if not buy_order:
            logger.error(f"[{account_id}] {coin} 추가 매수 실패")
            return False
        
        logger.info(f"[{account_id}] {coin} 5,500원 추가 매수 완료")
        time.sleep(BALANCE_RETRY_DELAY_SECONDS)  # 잔고 반영 대기
        
        # 잔고 재확인
        updated_balance = exchange.get_balance()
        if not updated_balance or coin not in updated_balance:
            logger.error(f"[{account_id}] {coin} 잔고 재확인 실패")
            return False
        
        # 전량 매도
        sell_amount = float(updated_balance[coin].get('free', 0.0))
        if sell_amount <= 0:
            logger.error(f"[{account_id}] {coin} 매도 가능 수량 없음")
            return False
        
        sell_order = exchange.create_market_order(symbol, 'sell', sell_amount)
        if not sell_order:
            logger.error(f"[{account_id}] {coin} 매도 실패")
            return False
        
        logger.info(f"[{account_id}] {coin} 전량 매도 완료")
        return True
    
    def cleanup_small_holdings(self, account_info: AccountInfo) -> CleanupResults:
        """5천원 이하의 소액 코인들을 정리합니다.
        
        빗썸에서는 5천원 이하로는 매도가 불가능하므로,
        해당 코인들을 5,500원씩 추가 매수한 후 전량 매도합니다.
        
        Args:
            account_info: 계정 정보 딕셔너리
                
        Returns:
            정리된 코인 정보와 결과를 담은 딕셔너리
        """
        account_id = account_info['account_id']
        results: CleanupResults = {
            'cleaned_coins': [],
            'failed_coins': [],
            'total_cleaned': 0
        }
        
        # 빗썸 거래소만 지원
        if self.exchange_name != 'bithumb':
            logger.info(f"[{account_id}] 소액 정리는 빗썸 거래소만 지원합니다.")
            return results
        
        try:
            logger.info(f"[{account_id}] 소액 코인 정리 시작")
            
            # 거래소 초기화
            credentials = {
                'apiKey': account_info['api_key'],
                'secret': account_info['api_secret']
            }
            exchange = BithumbExchange(credentials)
            
            # 잔고 조회
            balance = exchange.get_balance()
            if not balance:
                logger.error(f"[{account_id}] 잔고 조회 실패")
                return results
            
            logger.info(f"[{account_id}] 보유 코인 수: {len(balance) - 1}개 (KRW 제외)")
            
            # 시세 정보 조회
            prices = self._fetch_price_data(account_id)
            if not prices:
                return results
            
            # 소액 코인 식별
            logger.info(f"[{account_id}] 보유 코인 검사 중...")
            small_holdings = self._identify_small_holdings(balance, prices, account_id)
            
            if not small_holdings:
                logger.info(f"[{account_id}] 정리할 소액 코인이 없습니다.")
                return results
            
            # 발견된 소액 코인 로그
            logger.info(f"[{account_id}] 발견된 소액 코인: {len(small_holdings)}개")
            for holding in small_holdings:
                logger.info(f"  - {holding['coin']}: {holding['value']:,.0f}원")
            
            # 각 코인 정리 처리
            for holding in small_holdings:
                coin = holding['coin']
                
                try:
                    logger.info(f"[{account_id}] {coin} 정리 중...")
                    
                    success = self._process_single_coin_cleanup(exchange, coin, account_id)
                    
                    if success:
                        results['cleaned_coins'].append(coin)
                        results['total_cleaned'] += 1
                    else:
                        results['failed_coins'].append(coin)
                        
                except Exception as e:
                    logger.error(f"[{account_id}] {coin} 정리 중 오류: {e}")
                    results['failed_coins'].append(coin)
                
                time.sleep(1)  # 다음 코인 처리 전 대기
            
            # 결과 로그
            logger.info(f"[{account_id}] 소액 코인 정리 완료")
            logger.info(f"  - 정리 성공: {len(results['cleaned_coins'])}개")
            logger.info(f"  - 정리 실패: {len(results['failed_coins'])}개")
            
        except Exception as e:
            logger.error(f"[{account_id}] 소액 정리 중 오류 발생: {e}")
            
        return results
    
    def cleanup_all_accounts(
        self, max_workers: int = 5, accounts: Optional[list[AccountInfo]] = None
    ) -> None:
        """모든 계정의 소액 코인을 정리합니다.
        
        Args:
            max_workers: 동시 실행할 최대 스레드 수
            accounts: 사용할 계정 리스트 (기본값: 모든 계정)
        """
        if self.exchange_name != 'bithumb':
            logger.info("현재 소액 정리는 빗썸 거래소만 지원합니다.")
            return
        
        # 계정이 지정되지 않으면 모든 계정 사용
        if accounts is None:
            accounts = self.accounts
            
        logger.info("=== 모든 계정 소액 코인 정리 시작 ===")
        logger.info(f"정리할 계정 수: {len(accounts)}개")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures: dict[Future[CleanupResults], AccountInfo] = {
                executor.submit(self.cleanup_small_holdings, account): account
                for account in accounts
            }
            
            total_cleaned = 0
            for future in as_completed(futures):
                account = futures[future]
                try:
                    result = future.result()
                    total_cleaned += result['total_cleaned']
                except Exception as e:
                    logger.error(f"[{account['account_id']}] 정리 작업 실행 중 오류: {e}")
        
        logger.info(f"\n=== 소액 정리 완료: 총 {total_cleaned}개 코인 정리됨 ===")
