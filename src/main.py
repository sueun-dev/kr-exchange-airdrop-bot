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
    logger.info("(단일/다중 계정 지원)")
    
    # 봇 초기화
    bot = AirdropBot()
    
    if not bot.accounts:
        logger.error("등록된 계정이 없습니다.")
        logger.info("\n.env 파일에 다음 형식으로 API 키를 추가하세요:")
        logger.info("\n[단일 계정]")
        logger.info("BITHUMB_API_KEY='your_api_key'")
        logger.info("BITHUMB_SECRET_KEY='your_secret_key'")
        logger.info("\n[다중 계정]")
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
    symbol = input("거래할 코인 심볼을 입력하세요 (예: BTC, ETH, XRP): ").strip().upper()
    
    # 동시 실행 스레드 수 (다중 계정인 경우만)
    max_workers = 1
    if len(bot.accounts) > 1:
        max_workers = int(input(f"동시 실행할 최대 계정 수 (기본: 5, 최대: {len(bot.accounts)}): ").strip() or "5")
        max_workers = min(max_workers, len(bot.accounts))
    
    # 설정 확인
    logger.info("\n=== 설정 확인 ===")
    logger.info(f"거래소: 빗썸")
    logger.info(f"계정 수: {len(bot.accounts)}")
    logger.info(f"심볼: {symbol}/KRW")
    logger.info(f"거래 금액: {bot.trade_amount:,.0f} KRW")
    logger.info(f"대기 시간: {bot.wait_time}초")
    if len(bot.accounts) > 1:
        logger.info(f"동시 실행: {max_workers}개 계정")
    
    confirm = input("\n위 설정으로 진행하시겠습니까? (y/n): ").strip().lower()
    if confirm != 'y':
        logger.info("취소되었습니다.")
        return
    
    # 실행
    try:
        bot.participate_all_accounts(symbol, max_workers)
    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        logger.error(f"\n오류 발생: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()