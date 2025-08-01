# 에어드랍 이벤트 자동 참여 시스템

업비트와 빗썸에서 진행하는 에어드랍 이벤트에 자동으로 참여하는 시스템입니다.

## 주요 기능

### 🎯 핵심 기능
- **자동 거래**: 지정한 코인을 시장가 매수 → 대기 → 전량 매도
- **다중 거래소**: 업비트, 빗썸 지원
- **다중 계정**: 여러 계정으로 동시 참여 가능
- **다중 코인**: 여러 코인을 한 번에 거래 가능
- **반복 실행**: 일정 기간 동안 24시간마다 자동 실행

### 📊 상세 기능
- **병렬 처리**: ThreadPoolExecutor를 사용한 빠른 동시 처리
- **재시도 로직**: 네트워크 오류 시 자동 재시도
- **상세 로깅**: 모든 거래 내역을 파일과 콘솔에 기록
- **안전 장치**: 최소 거래 금액 확인, 잔고 확인 등

## 설치

### 1. 프로젝트 클론
```bash
git clone <repository-url>
cd exchange-event
```

### 2. uv 설치 (아직 없다면)
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 3. 의존성 설치
```bash
uv pip sync
```

## 설정

### API 키 설정

`.env` 파일을 생성하고 거래소 API 키를 설정하세요:

```env
# 업비트 API 키 (단일 계정)
UPBIT_ACCESS_KEY=your_upbit_access_key_here
UPBIT_SECRET_KEY=your_upbit_secret_key_here

# 빗썸 API 키 (단일 계정)
BITHUMB_API_KEY=your_bithumb_api_key_here
BITHUMB_SECRET_KEY=your_bithumb_secret_key_here

# 거래 설정
DEFAULT_TRADE_AMOUNT=5500  # 기본 거래 금액 (KRW)
WAIT_TIME_SECONDS=2  # 매수 후 대기 시간 (초)
```

### 다중 계정 설정

#### 업비트 다중 계정
```env
# 업비트 계정 1
UPBIT_ACCESS_KEY_1=access_key_1
UPBIT_SECRET_KEY_1=secret_key_1

# 업비트 계정 2
UPBIT_ACCESS_KEY_2=access_key_2
UPBIT_SECRET_KEY_2=secret_key_2

# 더 많은 계정 추가 가능...
```

#### 빗썸 다중 계정
```env
# 빗썸 계정 1
BITHUMB_API_KEY_1=api_key_1
BITHUMB_SECRET_KEY_1=secret_key_1

# 빗썸 계정 2
BITHUMB_API_KEY_2=api_key_2
BITHUMB_SECRET_KEY_2=secret_key_2

# 더 많은 계정 추가 가능...
```

### 혼합 설정 예시
```env
# 업비트 메인 계정
UPBIT_ACCESS_KEY=main_access_key
UPBIT_SECRET_KEY=main_secret_key

# 업비트 추가 계정
UPBIT_ACCESS_KEY_1=sub_access_key_1
UPBIT_SECRET_KEY_1=sub_secret_key_1

# 빗썸 계정들
BITHUMB_API_KEY_1=bithumb_key_1
BITHUMB_SECRET_KEY_1=bithumb_secret_1
BITHUMB_API_KEY_2=bithumb_key_2
BITHUMB_SECRET_KEY_2=bithumb_secret_2

# 거래 설정
DEFAULT_TRADE_AMOUNT=5500
WAIT_TIME_SECONDS=2
```

## 실행 방법

### 기본 실행
```bash
uv run python src/main.py
```

### 실행 과정

1. **거래소 선택**
   ```
   거래소를 선택하세요 (1: 업비트, 2: 빗썸): 1
   ```

2. **코인 선택**
   - 단일 코인: `BTC`
   - 여러 코인: `BTC,ETH,XRP`

3. **이벤트 기간 설정**
   - 1회만 실행: `1`
   - 3일간 실행: `3` (24시간마다 자동 실행)

4. **다중 계정 시 동시 실행 수 설정** (선택사항)
   ```
   동시 실행할 최대 계정 수 (기본: 5): 3
   ```

5. **설정 확인 및 실행**
   ```
   === 설정 확인 ===
   거래소: upbit
   계정 수: 2
   심볼: BTC, ETH (총 2개)
   거래 금액: 5,500 KRW (코인당)
   대기 시간: 2초
   이벤트 기간: 3일
   실행 주기: 24시간마다
   동시 실행: 2개 계정
   
   위 설정으로 진행하시겠습니까? (y/n): y
   ```

## 사용 예시

### 예시 1: 업비트에서 XRP 1회 거래
```
거래소 선택: 1 (업비트)
코인: XRP
이벤트 기간: 1
→ XRP를 5,500원어치 매수 후 2초 대기하고 전량 매도
```

### 예시 2: 빗썸에서 여러 코인 3일간 거래
```
거래소 선택: 2 (빗썸)
코인: BTC,ETH,XRP
이벤트 기간: 3
→ 3개 코인을 각각 5,500원어치 매수/매도, 3일간 매일 반복
```

### 예시 3: 다중 계정으로 여러 코인 거래
```
거래소 선택: 2 (빗썸)
계정 수: 3개 감지됨
코인: ETH,DOGE
이벤트 기간: 1
→ 3개 계정에서 동시에 ETH와 DOGE 거래 (총 6개 작업)
```

## 실행 결과 예시

```
=== 실행 결과 ===
✅ account_1 - BTC: 성공
✅ account_1 - ETH: 성공
❌ account_2 - BTC: 실패 (잔고 부족)
✅ account_2 - ETH: 성공

=== 전체 결과 요약 ===
총 작업 수: 4 (계정 2개 × 코인 2개)
성공: 3, 실패: 1

코인별 결과:
  BTC: 성공 1, 실패 1
  ETH: 성공 2, 실패 0
```

## 주의사항

### API 키 관련
- API 키에 **거래 권한**이 있어야 합니다
- API 키는 절대 외부에 노출하지 마세요
- `.env` 파일은 `.gitignore`에 포함되어 있습니다

### 거래 관련
- **최소 거래 금액**: 
  - 업비트: 5,000원
  - 빗썸: 1,000원
- **거래 수수료**가 발생합니다 (거래소별 상이)
- 시장가 주문이므로 **슬리피지**가 발생할 수 있습니다

### 실행 관련
- 네트워크 상태에 따라 거래가 지연될 수 있습니다
- 24시간 실행 시 컴퓨터가 계속 켜져 있어야 합니다
- 거래소 점검 시간에는 거래가 불가능합니다

## 로그 파일

실행 로그는 `logs/airdrop_event.log` 파일에 저장됩니다.

## 문제 해결

### API 키 오류
- API 키가 올바른지 확인하세요
- API 키에 거래 권한이 있는지 확인하세요
- API 키 앞뒤의 따옴표를 확인하세요

### 잔고 부족
- 계정에 충분한 KRW 잔고가 있는지 확인하세요
- 최소 거래 금액 이상인지 확인하세요

### 심볼 오류
- 거래소에서 지원하는 코인인지 확인하세요
- 코인 심볼을 대문자로 입력했는지 확인하세요

## 라이선스

이 프로젝트는 개인 사용 목적으로 제작되었습니다.