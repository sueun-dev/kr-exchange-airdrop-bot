# 에어드랍 이벤트 자동 참여 시스템

업비트와 빗썸에서 진행하는 에어드랍 이벤트에 자동으로 참여하는 시스템입니다.

## 기능

- **단일/다중 계정 지원** - 하나 또는 여러 계정으로 동시 참여
- **자동 거래** - 지정한 코인을 5,500원 시장가 매수 → 2초 대기 → 전량 매도
- **동시 처리** - 다중 계정 시 병렬 처리로 빠른 실행
- **재시도 로직** - 네트워크 오류 시 자동 재시도
- **상세 로깅** - 모든 거래 내역을 파일과 콘솔에 기록

## 설치

```bash
# uv 설치 (아직 없다면)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 의존성 설치
uv pip sync
```

## 설정

`.env` 파일에서 거래소 API 키를 설정하세요:

```env
# 업비트 API 키
UPBIT_ACCESS_KEY=your_upbit_access_key_here
UPBIT_SECRET_KEY=your_upbit_secret_key_here

# 빗썸 API 키
BITHUMB_API_KEY=your_bithumb_api_key_here
BITHUMB_SECRET_KEY=your_bithumb_secret_key_here

# 거래 설정
DEFAULT_TRADE_AMOUNT=5500  # 기본 거래 금액 (KRW)
WAIT_TIME_SECONDS=2  # 매수 후 대기 시간 (초)
```

## 실행

### uv를 사용한 실행
```bash
# 가상환경 생성 및 의존성 설치 (처음 한 번만)
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
uv pip install -e .

# 프로그램 실행
uv run python src/main.py
```

### 또는 가상환경 활성화 후 실행
```bash
source .venv/bin/activate
python src/main.py
```

실행 후:
1. 계정 모드 자동 감지 (단일/다중)
2. 코인 심볼 입력 (예: BTC, ETH, XRP)
3. 설정 확인 후 실행

## 다중 계정 설정

`.env` 파일에 여러 빗썸 계정을 추가할 수 있습니다:

```env
# 메인 계정
BITHUMB_API_KEY='main_api_key'
BITHUMB_SECRET_KEY='main_secret_key'

# 추가 계정들
BITHUMB_API_KEY_1='api_key_1'
BITHUMB_SECRET_KEY_1='secret_key_1'

BITHUMB_API_KEY_2='api_key_2'
BITHUMB_SECRET_KEY_2='secret_key_2'

# 더 많은 계정 추가 가능...
```


## 주의사항

- API 키에 거래 권한이 있어야 합니다
- 최소 거래 금액: 업비트 5,000원, 빗썸 5,000원
- 거래 수수료가 발생합니다
- 네트워크 상태에 따라 거래가 지연될 수 있습니다