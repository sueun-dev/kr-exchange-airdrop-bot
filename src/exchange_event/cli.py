"""Command-line interface for the exchange event bot."""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager, nullcontext
from datetime import datetime, timedelta
from typing import Iterator, Optional, Sequence
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from exchange_event.airdrop_event import AirdropBot
from exchange_event.logging_config import configure_logging, default_log_file
from exchange_event.types import AccountInfo

logger = logging.getLogger(__name__)

EXCHANGE_NAME = "bithumb"
KST = ZoneInfo("Asia/Seoul")
SCHEDULED_WAIT_TIME_SECONDS = 2
SCHEDULE_HOUR = 0
SCHEDULE_MINUTE = 1


def _parse_account_indices(selection: str, max_index: int) -> list[int]:
    """Parses an account selection string into 1-based indices."""
    indices: set[int] = set()
    for part in selection.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            try:
                start_raw, end_raw = part.split("-", 1)
                start = int(start_raw)
                end = int(end_raw)
            except ValueError:
                logger.warning("잘못된 범위: %s", part)
                continue

            if start > end:
                start, end = end, start
            indices.update(i for i in range(start, end + 1) if 1 <= i <= max_index)
            continue

        try:
            index = int(part)
        except ValueError:
            logger.warning("잘못된 숫자: %s", part)
            continue
        if 1 <= index <= max_index:
            indices.add(index)

    return sorted(indices)


def _select_accounts(accounts: Sequence[AccountInfo]) -> list[AccountInfo]:
    """Prompts the user to select which accounts to use."""
    if len(accounts) <= 1:
        return list(accounts)

    logger.info("\n계정을 선택하세요:")
    logger.info("  - all: 모든 계정 사용")
    logger.info("  - 숫자: 특정 계정 선택 (예: 1 또는 1,3)")
    logger.info("  - 범위: 계정 범위 선택 (예: 1-3)")

    choice = input("\n계정 선택 (기본: all): ").strip().lower()
    if not choice or choice == "all":
        return list(accounts)

    selected_indices = _parse_account_indices(choice, len(accounts))
    if not selected_indices:
        logger.warning("유효한 계정이 선택되지 않았습니다. 모든 계정을 사용합니다.")
        return list(accounts)

    selected = [accounts[i - 1] for i in selected_indices]
    logger.info("\n선택된 계정 (%d개):", len(selected))
    for account in selected:
        logger.info("  - %s", account["account_id"])
    return selected


def _prompt_yes_no(prompt: str, *, default: bool = False) -> bool:
    """Prompts the user for a y/n response."""
    raw = input(prompt).strip().lower()
    if not raw:
        return default
    return raw in ("y", "yes")


def _prompt_int(
    prompt: str, *, default: int, min_value: int = 1, max_value: Optional[int] = None
) -> int:
    """Prompts the user for an integer value with validation."""
    while True:
        raw = input(prompt).strip()
        if not raw:
            value = default
        else:
            try:
                value = int(raw)
            except ValueError:
                logger.warning("숫자를 입력하세요: %s", raw)
                continue

        if value < min_value:
            logger.warning("%d 이상 입력하세요.", min_value)
            continue
        if max_value is not None and value > max_value:
            logger.warning("%d 이하 입력하세요.", max_value)
            continue
        return value


def _prompt_symbols() -> list[str]:
    """Prompts the user for one or more coin symbols."""
    while True:
        symbol_input = input(
            "\n거래할 코인 심볼을 입력하세요 (단일: BTC / 여러개: BTC,ETH,XRP): "
        ).strip()
        symbols = [s.strip().upper() for s in symbol_input.split(",") if s.strip()]
        if symbols:
            return symbols
        logger.warning("심볼을 하나 이상 입력하세요.")


def _next_run_time(now: datetime) -> datetime:
    """Returns the next scheduled run time in KST."""
    scheduled = now.replace(
        hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, second=0, microsecond=0
    )
    if scheduled <= now:
        scheduled += timedelta(days=1)
    return scheduled


def _wait_until(target: datetime) -> None:
    """Sleeps until the target datetime (KST), printing periodic status updates."""
    while True:
        now = datetime.now(KST)
        remaining_seconds = (target - now).total_seconds()
        if remaining_seconds <= 0:
            return

        hours_until = int(remaining_seconds // 3600)
        minutes_until = int((remaining_seconds % 3600) // 60)
        if now.minute == 0 and hours_until >= 1:
            logger.info("다음 실행까지: %d시간 %d분 남음", hours_until, minutes_until)

        time.sleep(min(60.0, remaining_seconds))


@contextmanager
def _temporary_wait_time(bot: AirdropBot, wait_time_seconds: int) -> Iterator[None]:
    original_wait_time = bot.wait_time
    bot.wait_time = wait_time_seconds
    try:
        yield
    finally:
        bot.wait_time = original_wait_time


def _run_once(
    bot: AirdropBot,
    symbols: list[str],
    max_workers: int,
    accounts: list[AccountInfo],
    cleanup_small_holdings: bool,
) -> None:
    bot.participate_all_accounts(symbols, max_workers, accounts)
    if cleanup_small_holdings:
        logger.info("\n=== 소액 코인 정리 시작 ===")
        bot.cleanup_all_accounts(max_workers, accounts)

    logger.info("\n=== 모든 작업 완료! ===")
    logger.info("실행 시간: %s", datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"))


def _run_multi_day(
    bot: AirdropBot,
    symbols: list[str],
    max_workers: int,
    accounts: list[AccountInfo],
    event_days: int,
    cleanup_small_holdings: bool,
) -> None:
    for day in range(1, event_days + 1):
        is_first_run = day == 1
        current_time = datetime.now(KST)
        logger.info("\n=== %d일차 실행 (총 %d일) ===", day, event_days)
        logger.info("실행 시간: %s KST", current_time.strftime("%Y-%m-%d %H:%M:%S"))

        wait_context = (
            nullcontext()
            if is_first_run
            else _temporary_wait_time(bot, SCHEDULED_WAIT_TIME_SECONDS)
        )
        with wait_context:
            if not is_first_run:
                logger.info("스케줄 실행: 대기 시간 %d초로 설정", bot.wait_time)
            bot.participate_all_accounts(symbols, max_workers, accounts)

        if cleanup_small_holdings:
            logger.info("\n=== 소액 코인 정리 시작 ===")
            bot.cleanup_all_accounts(max_workers, accounts)
            cleanup_small_holdings = False

        if day >= event_days:
            logger.info("\n=== 모든 이벤트 완료! ===")
            logger.info("총 %d일 동안 실행했습니다.", event_days)
            logger.info("완료 시간: %s KST", current_time.strftime("%Y-%m-%d %H:%M:%S"))
            return

        next_run = _next_run_time(datetime.now(KST))
        remaining = (next_run - datetime.now(KST)).total_seconds()
        hours_until = int(remaining // 3600)
        minutes_until = int((remaining % 3600) // 60)
        logger.info("\n다음 실행까지 대기 중...")
        logger.info("다음 실행 예정: %s KST", next_run.strftime("%Y-%m-%d %H:%M:%S"))
        logger.info("남은 시간: %d시간 %d분", hours_until, minutes_until)
        logger.info("중단하려면 Ctrl+C를 누르세요.")

        _wait_until(next_run)


def main() -> None:
    """Runs the interactive CLI."""
    configure_logging(log_file=default_log_file())
    load_dotenv()

    logger.info("=== 에어드랍 이벤트(사고 팔기) 자동 참여 시스템 ===")
    logger.info("(빗썸 전용)")

    bot = AirdropBot(EXCHANGE_NAME)
    if not bot.accounts:
        logger.error("등록된 계정이 없습니다.")
        logger.info("\n.env 파일에 다음 형식으로 API 키를 추가하세요:")
        logger.info("\n[빗썸 1번 계정]")
        logger.info("BITHUMB_API_KEY_1=your_api_key_1")
        logger.info("BITHUMB_SECRET_KEY_1=your_secret_key_1")
        logger.info("\n[빗썸 추가 계정]")
        logger.info("BITHUMB_API_KEY_2=your_api_key_2")
        logger.info("BITHUMB_SECRET_KEY_2=your_secret_key_2")
        logger.info("\n[레거시 단일 계정(번호 키가 없을 때만 사용됨)]")
        logger.info("BITHUMB_API_KEY=your_api_key")
        logger.info("BITHUMB_SECRET_KEY=your_secret_key")
        return

    logger.info("\n=== 사용 가능한 계정 (%d개) ===", len(bot.accounts))
    for idx, account in enumerate(bot.accounts, 1):
        logger.info("  %d. %s", idx, account["account_id"])

    selected_accounts = _select_accounts(bot.accounts)

    if _prompt_yes_no("\n지갑 잔액만 확인하시겠습니까? (y/n): "):
        logger.info("\n=== 지갑 잔액 확인 중... ===")
        for account in selected_accounts:
            try:
                exchange = bot.create_exchange(account)
                balance_info = exchange.get_balance_summary()
                logger.info("\n[%s] 잔액 정보:", account["account_id"])
                logger.info("  - 원화: %,.0f KRW", balance_info["krw"])
                logger.info("  - 총 평가금액: %,.0f KRW", balance_info["total_krw"])
                holdings = balance_info.get("holdings", [])
                if holdings:
                    logger.info("  - 보유 코인:")
                    for coin in holdings:
                        logger.info(
                            "    • %s: %,.8f (평가: %,.0f KRW)",
                            coin["currency"],
                            coin["balance"],
                            coin["krw_value"],
                        )
            except Exception as exc:
                logger.error("[%s] 잔액 조회 실패: %s", account["account_id"], exc)
        logger.info("\n=== 잔액 확인 완료 ===")
        return

    symbols = _prompt_symbols()
    event_days = _prompt_int("이벤트 진행 일수 (1회만 실행: 1): ", default=1, min_value=1)

    max_workers = 1
    if len(selected_accounts) > 1:
        max_workers = _prompt_int(
            f"동시 실행할 최대 계정 수 (기본: 5, 최대: {len(selected_accounts)}): ",
            default=5,
            min_value=1,
            max_value=len(selected_accounts),
        )

    cleanup_small_holdings = _prompt_yes_no(
        "\n대기 중 5천원 이하 코인 정리를 하시겠습니까? (y/n): "
    )

    logger.info("\n=== 설정 확인 ===")
    logger.info("거래소: %s", EXCHANGE_NAME)
    logger.info("선택된 계정: %d개", len(selected_accounts))
    for account in selected_accounts:
        logger.info("  - %s", account["account_id"])
    logger.info("심볼: %s", ", ".join(symbols))
    logger.info("거래 금액: %,.0f KRW (코인당)", bot.trade_amount)
    logger.info("대기 시간: %d초", bot.wait_time)
    logger.info("이벤트 기간: %d일", event_days)
    if event_days > 1:
        logger.info("2일차부터: 매일 오전 %02d:%02d (KST)에 자동 실행", SCHEDULE_HOUR, SCHEDULE_MINUTE)
    if len(selected_accounts) > 1:
        logger.info("동시 실행: %d개 계정", max_workers)
    if cleanup_small_holdings:
        logger.info("소액 코인 정리: 활성화 (5천원 이하)")

    if not _prompt_yes_no("\n위 설정으로 진행하시겠습니까? (y/n): "):
        logger.info("취소되었습니다.")
        return

    logger.info("\n=== 프로그램을 시작합니다 ===")
    logger.info("현재 시간: %s", datetime.now(KST).strftime("%Y-%m-%d %H:%M:%S"))

    try:
        if event_days == 1:
            _run_once(bot, symbols, max_workers, selected_accounts, cleanup_small_holdings)
        else:
            _run_multi_day(
                bot,
                symbols,
                max_workers,
                selected_accounts,
                event_days,
                cleanup_small_holdings,
            )
    except KeyboardInterrupt:
        logger.info("\n사용자에 의해 중단되었습니다.")
    except Exception as exc:
        logger.exception("오류 발생: %s", exc)
        sys.exit(1)

