#!/usr/bin/env python3
"""에어드랍 이벤트 자동 참여 시스템의 메인 진입점."""

import logging
import sys
from airdrop_event import AirdropBot

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('Main')


def main() -> None:
    """프로그램의 메인 진입점.
    
    사용자 입력을 받아 에어드랍 봇을 설정하고 실행합니다.
    """
    logger.info("=== 에어드랍 이벤트 자동 참여 시스템 ===")
    logger.info("(업비트/빗썸 지원)")
    
    # 거래소 선택
    exchange_choice = input("\n거래소를 선택하세요 (1: 업비트, 2: 빗썸): ").strip()
    
    if exchange_choice == '1':
        exchange_name = 'upbit'
        logger.info("업비트 거래소를 선택했습니다.")
    elif exchange_choice == '2':
        exchange_name = 'bithumb'
        logger.info("빗썸 거래소를 선택했습니다.")
    else:
        logger.error("잘못된 선택입니다.")
        return
    
    # 봇 초기화
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
        else:
            logger.info("\n[빗썸 단일 계정]")
            logger.info("BITHUMB_API_KEY='your_api_key'")
            logger.info("BITHUMB_SECRET_KEY='your_secret_key'")
            logger.info("\n[빗썸 다중 계정]")
            logger.info("BITHUMB_API_KEY_1='your_api_key_1'")
            logger.info("BITHUMB_SECRET_KEY_1='your_secret_key_1'")
            logger.info("BITHUMB_API_KEY_2='your_api_key_2'")
            logger.info("BITHUMB_SECRET_KEY_2='your_secret_key_2'")
        return
    
    # 계정 정보 출력
    if len(bot.accounts) == 1:
        logger.info(f"단일 계정 모드 ({bot.accounts[0]['account_id']})")
    else:
        logger.info(f"다중 계정 모드 (총 {len(bot.accounts)}개)")
        for account in bot.accounts:
            logger.info(f"  - {account['account_id']}")
    
    # 사용자 입력 받기
    symbol_input = input("거래할 코인 심볼을 입력하세요 (단일: BTC / 여러개: BTC,ETH,XRP): ").strip().upper()
    symbols = [s.strip() for s in symbol_input.split(',') if s.strip()]
    
    # 이벤트 기간 설정
    event_days = int(input("이벤트 진행 일수 (1회만 실행: 1): ").strip() or "1")
    
    # 동시 실행 스레드 수 (다중 계정인 경우만)
    max_workers = 1
    if len(bot.accounts) > 1:
        max_workers = int(input(f"동시 실행할 최대 계정 수 (기본: 5, 최대: {len(bot.accounts)}): ").strip() or "5")
        max_workers = min(max_workers, len(bot.accounts))
    
    # 설정 확인
    logger.info("\n=== 설정 확인 ===")
    logger.info(f"거래소: {exchange_name}")
    logger.info(f"계정 수: {len(bot.accounts)}")
    if len(symbols) == 1:
        logger.info(f"심볼: {symbols[0]}/KRW")
    else:
        logger.info(f"심볼: {', '.join(symbols)} (총 {len(symbols)}개)")
    logger.info(f"거래 금액: {bot.trade_amount:,.0f} KRW (코인당)")
    logger.info(f"대기 시간: {bot.wait_time}초")
    logger.info(f"이벤트 기간: {event_days}일")
    if event_days > 1:
        logger.info(f"실행 주기: 24시간마다")
    if len(bot.accounts) > 1:
        logger.info(f"동시 실행: {max_workers}개 계정")
    
    confirm = input("\n위 설정으로 진행하시겠습니까? (y/n): ").strip().lower()
    if confirm != 'y':
        logger.info("취소되었습니다.")
        return
    
    # 실행
    try:
        if event_days == 1:
            # 1회만 실행
            bot.participate_all_accounts(symbols, max_workers)
        else:
            # 여러 날 동안 실행
            import schedule
            import time
            from datetime import datetime
            
            # 실행 카운터
            execution_count = 0
            
            def run_event():
                nonlocal execution_count
                execution_count += 1
                logger.info(f"\n=== {execution_count}일차 실행 (총 {event_days}일) ===")
                logger.info(f"실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                bot.participate_all_accounts(symbols, max_workers)
                
                if execution_count >= event_days:
                    logger.info(f"\n모든 이벤트 완료! 총 {event_days}일 동안 실행했습니다.")
                    return schedule.CancelJob
            
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