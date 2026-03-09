# 빗썸 에어드랍 자동 참여 봇

빗썸 에어드랍 참여를 반복 실행할 수 있도록 정리한 Bithumb 전용 자동화 도구입니다. 단일 계정과 다중 계정을 모두 지원하며, 계정별 잔액 확인, 소액 코인 정리, 다일 스케줄 실행을 한 CLI 안에서 처리합니다.

## 구조

```text
src/
  bithumb_airdrop_bot/
    bot.py                 # 계정 로딩, 거래 오케스트레이션
    cli.py                 # 대화형 CLI 진입점
    logging_config.py      # 콘솔/파일 로깅 설정
    models.py              # TypedDict 모델
    clients/
      base.py              # 공통 클라이언트 인터페이스
      bithumb_client.py    # Bithumb REST API 연동

tests/
  test_bithumb_account_loading.py
  test_bithumb_bot_single_participation.py
  test_bithumb_bot_small_holdings.py
  test_bithumb_exchange_client.py
```

## 주요 기능

- 빗썸 시장가 매수 후 지정 시간 대기, 전량 매도
- 여러 계정을 동시에 선택해 병렬 실행
- 여러 코인을 한 번에 처리
- 모든 계정의 잔액 및 보유 자산 조회
- 5,000 KRW 이하 소액 코인 자동 정리
- 여러 날에 걸친 반복 실행과 KST 기준 예약 실행
- 파일 로그와 콘솔 로그 동시 기록

## 요구 사항

- Python `>= 3.9`
- [uv](https://docs.astral.sh/uv/)
- 빗썸 API 키와 시크릿

## 설치

```bash
git clone https://github.com/sueun-dev/kr-exchange-airdrop-bot.git
cd kr-exchange-airdrop-bot
uv sync
```

개발 의존성까지 설치하려면:

```bash
uv sync --extra dev
```

## 환경 변수 설정

`.env.sample`을 복사해 `.env`를 만든 뒤 값을 채우면 됩니다.

```bash
cp .env.sample .env
```

단일 계정 예시:

```env
BITHUMB_API_KEY=your_bithumb_api_key
BITHUMB_SECRET_KEY=your_bithumb_secret_key
DEFAULT_TRADE_AMOUNT=5500
WAIT_TIME_SECONDS=2
```

다중 계정 예시:

```env
BITHUMB_API_KEY_1=your_bithumb_api_key_1
BITHUMB_SECRET_KEY_1=your_bithumb_secret_key_1
BITHUMB_API_KEY_2=your_bithumb_api_key_2
BITHUMB_SECRET_KEY_2=your_bithumb_secret_key_2
DEFAULT_TRADE_AMOUNT=5500
WAIT_TIME_SECONDS=2
```

번호가 붙은 키가 있으면 다중 계정 설정을 우선 사용하고, 없을 때만 레거시 단일 계정 키를 읽습니다.

## 실행

권장 실행 방식:

```bash
uv run bithumb-airdrop-bot
```

동일한 동작을 모듈 실행으로 호출하려면:

```bash
uv run python -m bithumb_airdrop_bot
```

레거시 엔트리포인트도 유지되어 있습니다:

```bash
uv run python src/main.py
```

## 백그라운드 실행

macOS에서 `caffeinate`를 사용해 절전을 막고 백그라운드 실행하려면:

```bash
./run_bithumb_airdrop_background.sh
```

중단:

```bash
./stop_bithumb_airdrop_background.sh
```

로그 확인:

```bash
tail -f bithumb_airdrop_bot.log
```

## CLI 흐름

실행하면 아래 순서로 설정을 받습니다.

1. 사용할 계정 선택 (`all`, `1,3`, `1-3` 등)
2. 잔액 조회만 할지 여부 선택
3. 거래할 심볼 입력 (`BTC` 또는 `BTC,ETH,XRP`)
4. 이벤트 진행 일수 입력
5. 다중 계정일 경우 동시 실행 수 입력
6. 소액 코인 정리 여부 선택
7. 최종 설정 확인 후 실행

`event_days > 1`이면 첫 실행은 즉시 수행하고, 2일차부터는 매일 `00:01 KST`에 실행합니다.

## 로그 파일

- 애플리케이션 로그: `logs/bithumb_airdrop.log`
- 백그라운드 스크립트 로그: `bithumb_airdrop_bot.log`
- 백그라운드 PID 파일: `bithumb_airdrop_bot.pid`

## 테스트

```bash
uv run pytest
```

타입 체크:

```bash
uv run mypy src tests
```

## 주의 사항

- API 키에 거래 권한이 있어야 합니다.
- 시장가 주문 특성상 슬리피지가 발생할 수 있습니다.
- 수수료와 최소 주문 금액을 고려해야 합니다.
- 장시간 실행 시 네트워크 상태와 거래소 점검 시간을 확인해야 합니다.
- `.env` 파일은 절대 저장소에 커밋하지 마세요.
