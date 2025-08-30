import logging
import sys
import time
from datetime import datetime, timedelta
from airdrop_event import AirdropBot
import schedule

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('Main')


def main() -> None:
    """프로그램의 메인 진입점.
    
    사용자 입력을 받아 에어드랍 봇을 설정하고 실행합니다.
    """
    logger.info("=== 에어드랍 이벤트(사고 팔기) 자동 참여 시스템 ===")
    logger.info("(업비트/빗썸 지원)")
    
    while True:
        exchange_choice = input("\n거래소를 선택하세요 (1: 업비트, 2: 빗썸): ").strip()
        
        if exchange_choice == '1':
            exchange_name = 'upbit'
            logger.info("업비트 거래소를 선택했습니다.")
            break
        elif exchange_choice == '2':
            exchange_name = 'bithumb'
            logger.info("빗썸 거래소를 선택했습니다.")
            break
        else:
            logger.error("잘못된 선택입니다. 1(업비트) 또는 2(빗썸)를 입력하세요.")
    
    bot = AirdropBot(exchange_name)
    
    if not bot.accounts:
        logger.error("등록된 계정이 없습니다.")
        logger.info("\n.env 파일에 다음 형식으로 API 키를 추가하세요:")
        
        if exchange_name == 'upbit':
            logger.info("\n[업비트 단일 계정]")
            logger.info("UPBIT_ACCESS_KEY='your_access_key'")
            logger.info("UPBIT_SECRET_KEY='your_secret_key'")
            logger.info("\n[업비트 다중 계정]")
            logger.info("UPBIT_ACCESS_KEY_1='your_access_key_1'")
            logger.info("UPBIT_SECRET_KEY_1='your_secret_key_1'")
            logger.info("UPBIT_ACCESS_KEY_2='your_access_key_2'")
            logger.info("UPBIT_SECRET_KEY_2='your_secret_key_2'")
            logger.info("...")
        else:
            logger.info("\n[빗썸 단일 계정]")
            logger.info("BITHUMB_API_KEY='your_api_key'")
            logger.info("BITHUMB_SECRET_KEY='your_secret_key'")
            logger.info("\n[빗썸 다중 계정]")
            logger.info("BITHUMB_API_KEY_1='your_api_key_1'")
            logger.info("BITHUMB_SECRET_KEY_1='your_secret_key_1'")
            logger.info("BITHUMB_API_KEY_2='your_api_key_2'")
            logger.info("BITHUMB_SECRET_KEY_2='your_secret_key_2'")
            logger.info("...")
        return
    
    # 계정 정보 출력
    logger.info(f"\n=== 사용 가능한 계정 ({len(bot.accounts)}개) ===")
    for idx, account in enumerate(bot.accounts, 1):
        logger.info(f"  {idx}. {account['account_id']}")
    
    # 계정 선택
    selected_accounts = bot.accounts  # 기본값: 모든 계정
    
    if len(bot.accounts) > 1:
        logger.info("\n계정을 선택하세요:")
        logger.info("  - all: 모든 계정 사용")
        logger.info("  - 숫자: 특정 계정 선택 (예: 1 또는 1,3)")
        logger.info("  - 범위: 계정 범위 선택 (예: 1-3)")
        
        account_choice = input("\n계정 선택 (기본: all): ").strip().lower() or "all"
        
        if account_choice != "all":
            selected_indices = []
            
            # 쉼표로 구분된 선택 처리
            for part in account_choice.split(','):
                part = part.strip()
                
                # 범위 처리 (예: 1-3)
                if '-' in part:
                    try:
                        start, end = map(int, part.split('-'))
                        selected_indices.extend(range(start, end + 1))
                    except:
                        logger.warning(f"잘못된 범위: {part}")
                else:
                    # 단일 숫자 처리
                    try:
                        selected_indices.append(int(part))
                    except:
                        logger.warning(f"잘못된 숫자: {part}")
            
            # 유효한 인덱스만 필터링
            selected_indices = [i for i in selected_indices if 1 <= i <= len(bot.accounts)]
            
            if selected_indices:
                selected_accounts = [bot.accounts[i-1] for i in sorted(set(selected_indices))]
                logger.info(f"\n선택된 계정 ({len(selected_accounts)}개):")
                for account in selected_accounts:
                    logger.info(f"  - {account['account_id']}")
            else:
                logger.warning("유효한 계정이 선택되지 않았습니다. 모든 계정을 사용합니다.")
                selected_accounts = bot.accounts
    
    # 지갑 잔액 확인 옵션
    check_balance_only = input("\n지갑 잔액만 확인하시겠습니까? (y/n): ").strip().lower()
    
    if check_balance_only == 'y':
        logger.info("\n=== 지갑 잔액 확인 중... ===")
        for account in selected_accounts:
            try:
                exchange = bot._get_exchange(account)
                balance_info = exchange.get_balance_summary()
                logger.info(f"\n[{account['account_id']}] 잔액 정보:")
                logger.info(f"  - 원화: {balance_info['krw']:,.0f} KRW")
                logger.info(f"  - 총 평가금액: {balance_info['total_krw']:,.0f} KRW")
                if balance_info['holdings']:
                    logger.info("  - 보유 코인:")
                    for coin in balance_info['holdings']:
                        logger.info(f"    • {coin['currency']}: {coin['balance']:,.8f} (평가: {coin['krw_value']:,.0f} KRW)")
            except Exception as e:
                logger.error(f"[{account['account_id']}] 잔액 조회 실패: {e}")
        logger.info("\n=== 잔액 확인 완료 ===")
        return
    
    # 사용자 입력 받기
    symbol_input = input("\n거래할 코인 심볼을 입력하세요 (단일: BTC / 여러개: BTC,ETH,XRP): ").strip().upper()
    symbols = [s.strip() for s in symbol_input.split(',') if s.strip()]
    
    # 이벤트 기간 설정
    event_days = int(input("이벤트 진행 일수 (1회만 실행: 1): ").strip() or "1")
    
    # 동시 실행 스레드 수 (다중 계정인 경우만)
    max_workers = 1
    if len(selected_accounts) > 1:
        max_workers = int(input(f"동시 실행할 최대 계정 수 (기본: 5, 최대: {len(selected_accounts)}): ").strip() or "5")
        max_workers = min(max_workers, len(selected_accounts))
    
    # 소액 정리 옵션 (빗썸만)
    cleanup_small_holdings = False
    if exchange_name == 'bithumb':
        cleanup_option = input("\n대기 중 5천원 이하 코인 정리를 하시겠습니까? (y/n): ").strip().lower()
        cleanup_small_holdings = (cleanup_option == 'y')
    
    # 설정 확인
    logger.info("\n=== 설정 확인 ===")
    logger.info(f"거래소: {exchange_name}")
    logger.info(f"선택된 계정: {len(selected_accounts)}개")
    for account in selected_accounts:
        logger.info(f"  - {account['account_id']}")
    if len(symbols) == 1:
        logger.info(f"심볼: {symbols[0]}/KRW")
    else:
        logger.info(f"심볼: {', '.join(symbols)} (총 {len(symbols)}개)")
    logger.info(f"거래 금액: {bot.trade_amount:,.0f} KRW (코인당)")
    logger.info(f"대기 시간: {bot.wait_time}초")
    logger.info(f"이벤트 기간: {event_days}일")
    if event_days > 1:
        logger.info(f"실행 주기: 24시간마다")
    if len(selected_accounts) > 1:
        logger.info(f"동시 실행: {max_workers}개 계정")
    if cleanup_small_holdings:
        logger.info("소액 코인 정리: 활성화 (5천원 이하)")
    
    confirm = input("\n위 설정으로 진행하시겠습니까? (y/n): ").strip().lower()
    if confirm != 'y':
        logger.info("취소되었습니다.")
        return
    
    # 1시간 후 실행 대기
    wait_hours = 0
    wait_seconds = wait_hours * 3600
    start_time = datetime.now() + timedelta(hours=wait_hours)
    
    logger.info(f"\n=== {wait_hours}시간 후 실행 예정 ===")
    logger.info(f"현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"실행 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("대기 중... (중단하려면 Ctrl+C를 누르세요)\n")
    
    # 대기 중 진행 상황 표시
    while wait_seconds > 0:
        if wait_seconds > 600:  # 10분 이상 남았으면 10분마다 업데이트
            time.sleep(600)
            wait_seconds -= 600
            remaining_hours = wait_seconds // 3600
            remaining_minutes = (wait_seconds % 3600) // 60
            logger.info(f"남은 대기 시간: {remaining_hours}시간 {remaining_minutes}분")
        else:
            # 10분 미만이면 1분마다 업데이트
            time.sleep(60)
            wait_seconds -= 60
            if wait_seconds > 0:
                logger.info(f"남은 대기 시간: {wait_seconds // 60}분")
    
    logger.info("\n실행 시간이 되었습니다. 프로그램을 시작합니다.\n")
    
    # 실행
    try:
        if event_days == 1:
            # 1회만 실행
            bot.participate_all_accounts(symbols, max_workers, selected_accounts)
            
            # 소액 정리 옵션 실행 (빗썸만)
            if cleanup_small_holdings:
                logger.info("\n=== 소액 코인 정리 시작 ===")
                bot.cleanup_all_accounts(max_workers, selected_accounts)
            
            logger.info("\n=== 모든 작업 완료! ===")
            logger.info(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            
            # 실행 카운터
            execution_count = 0
            
            def run_event():
                nonlocal execution_count, cleanup_small_holdings
                execution_count += 1
                logger.info(f"\n=== {execution_count}일차 실행 (총 {event_days}일) ===")
                logger.info(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                bot.participate_all_accounts(symbols, max_workers, selected_accounts)
                
                # 소액 정리 옵션 실행 (빗썸만)
                if cleanup_small_holdings:
                    logger.info("\n=== 소액 코인 정리 시작 ===")
                    bot.cleanup_all_accounts(max_workers, selected_accounts)
                    cleanup_small_holdings = False  # 한 번 실행 후 비활성화
                
                if execution_count >= event_days:
                    logger.info(f"\n=== 모든 이벤트 완료! ===")
                    logger.info(f"총 {event_days}일 동안 실행했습니다.")
                    logger.info(f"완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                    return schedule.CancelJob
                else:
                    logger.info(f"\n=== {execution_count}일차 완료 ===")
                    logger.info(f"다음 실행까지 24시간 대기합니다.")
            
            # 첫 실행
            run_event()
            
            if execution_count < event_days:
                # 24시간마다 실행 스케줄 설정
                schedule.every(24).hours.do(run_event)
                
                logger.info(f"\n다음 실행까지 대기 중... (24시간 후)")
                logger.info("중단하려면 Ctrl+C를 누르세요.")
                
                while execution_count < event_days:
                    schedule.run_pending()
                    time.sleep(60)  # 1분마다 체크
                    
    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"\n오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()