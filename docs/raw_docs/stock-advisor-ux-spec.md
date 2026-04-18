# 📱 Stock Advisor — UX/UI 시각적 기획서

---

## 1. 디자인 철학

### 원칙
- **데이터 우선**: 장식보다 숫자가 먼저 보여야 한다. 투자자는 3초 안에 시장 상태를 파악해야 한다.
- **위험은 눈에 띄게**: 원칙 위반, 손실, 경고는 반드시 시각적으로 구분 (빨강/주황 배지)
- **전략별 분리**: 단타/스윙/자산 전략이 UI에서도 명확히 구분되어야 한다
- **모바일 퍼스트**: 출퇴근길, 장중에 폰으로 확인하는 것이 주 사용 시나리오

### 색상 체계 (시맨틱)
| 색상 | 의미 | 사용처 |
|------|------|--------|
| Green | 상승, 안전, 원칙 준수 | 수익률, 상승장 배지, 체크마크 |
| Red/Coral | 하락, 위험, 경고 | 손실, 하락장, 원칙 위반 |
| Amber | 주의, 관찰 | 조정장, FOMO 경고, 이벤트 임박 |
| Blue | 정보, 중립 | 리포트 링크, 기술지표, 상세보기 |
| Purple | 시스템, AI 분석 | 오케스트레이터 판단, 신뢰도 |

### 타이포그래피
- 숫자 (주가, 수익률): 모노스페이스, 16~24px, weight 500
- 라벨: 11~12px, 대문자, color-text-tertiary
- 본문: 13~14px, 기본 sans

---

## 2. 화면 구조 (Information Architecture)

### 화면 구조도

![App Sitemap](./images/01-sitemap.png)

```
Bottom Navigation (5 tabs)
│
├── Dashboard (Home)
│   ├── Market state banner (상승장/조정장/하락장)
│   ├── Key indicators grid (KOSPI, S&P500, DXY, VIX)
│   ├── Strategy signal cards (horizontal scroll)
│   ├── Portfolio snapshot
│   └── Recent alerts list
│
├── Macro Analysis
│   ├── Market state detail + confidence
│   ├── Key economic indicators list
│   ├── Yield curve chart
│   ├── Geopolitical events calendar
│   └── → Tap indicator → Historical trend view
│
├── Charts
│   ├── Search bar (ticker/name)
│   ├── TradingView chart widget
│   ├── Indicator toggle pills (RSI, MACD, BB, etc.)
│   ├── Technical summary card
│   ├── Supply & demand card (기관/외국인)
│   └── → Tap → Stock detail page
│
├── Portfolio
│   ├── Total value + total return
│   ├── Account split (Asset / Trading / Cash)
│   ├── Risk status (MDD, Sharpe, Risk meter)
│   ├── Principle check list (7계명)
│   ├── Holdings list (by strategy)
│   └── → Tap → Trade history detail
│
├── Watchlist
│   ├── Filter pills (All, 국내, 미국, Signal, Alert)
│   ├── Active signals section
│   ├── Watching section
│   ├── → Tap stock → Chart detail
│   └── → Long press → Edit/Remove
│
└── Reports (accessible from Dashboard or tab)
    ├── Today's briefing (featured card)
    ├── Report timeline (weekly)
    ├── Report type grid (Daily/Signal/Weekly/Evolution)
    └── → Tap → Full report reader
```

---

## 3. 화면별 상세 스펙

### 3-1. Dashboard (Home)

![Dashboard Wireframe](./images/02-dashboard.png)

**목적**: 아침에 3초 만에 시장 상태와 할 일을 파악

| 컴포넌트 | 데이터 소스 | 업데이트 주기 |
|----------|-----------|-------------|
| Market state banner | 오케스트레이터 → daily_summary | 1일 1회 (아침 배치) |
| Indicator grid (4칸) | KIS API + yfinance | 실시간 (장중 1분) |
| Strategy cards (3장) | 오케스트레이터 → 전략별 판단 | 1일 1회 + 실시간 시그널 |
| Portfolio snapshot | KIS API → 잔고 조회 | 1시간 1회 |
| Alert list | alert_log 테이블 | 실시간 push |

**인터랙션**:
- Market state 탭 → Macro 화면으로 이동
- Strategy card 탭 → 해당 전략의 상세 시그널 목록
- Alert 탭 → 관련 화면으로 딥링크 (종목 → Charts, 원칙 → Portfolio)
- Pull-to-refresh → 전체 데이터 리프레시

### 3-2. Macro Analysis

![Macro + Charts Wireframe](./images/03-macro-charts.png)

**목적**: 매크로 전문가 수준의 시황 분석 열람

| 컴포넌트 | 데이터 소스 | 비고 |
|----------|-----------|------|
| Market state + 신뢰도 | macro_analysis.state | 근거 텍스트 포함 |
| Key indicators | daily_macro 테이블 | 전일 대비 변동 표시 |
| Yield curve | FRED API | TradingView 차트 위젯 |
| Event calendar | 수동 입력 + 크롤링 | D-day 카운트다운 |

**특수 UX**:
- 인디케이터 행을 탭하면 → 30일 히스토리 차트가 인라인으로 확장
- 시장 상태가 "하락장"이면 banner 배경색이 빨강으로 변경 (시각 경보)

### 3-3. Charts (기술적 분석)

**목적**: 개별 종목의 차트와 기술적/수급 분석

| 컴포넌트 | 기술 | 비고 |
|----------|------|------|
| Chart widget | TradingView Lightweight Charts | 일봉/주봉/분봉 전환 |
| Indicator pills | Toggle on/off | RSI, MACD, BB, MA20, MA60, Stochastic, Volume |
| Technical summary | 기술적 분석팀 출력 | Trend, RSI, MACD, 지지/저항 |
| Supply card | KIS API → 투자자별 매매 | 기관/외국인 순매수 |

**특수 UX**:
- 차트를 좌우 스와이프 → 타임프레임 전환 (1분 → 5분 → 일봉 → 주봉)
- 지지/저항선은 차트 위에 수평선으로 오버레이
- 종목이 watchlist에 없으면 "Add to watchlist" 버튼 표시

### 3-4. Portfolio (계좌관리)

![Portfolio + Watchlist + Reports](./images/04-portfolio-watchlist-reports.png)

**목적**: 계좌 안정성 확인 + 원칙 준수 모니터링

| 컴포넌트 | 데이터 소스 | 비고 |
|----------|-----------|------|
| Total value | KIS API → 잔고 | 총 평가액 + 총 수익률 |
| Account split | portfolio_log | 자산/트레이딩/현금 비중 |
| Risk status | risk_calculator | MDD, Sharpe, Risk score |
| Principle check | principle_checker | 7계명 각각의 준수 상태 |

**특수 UX**:
- Risk meter: 5칸 바 형태. 위험도에 따라 녹→황→적 색상 변화
- Principle 위반 시: 해당 행이 빨간 테두리 + 경고 아이콘
- "자산 계좌" / "트레이딩 계좌" 탭 전환 가능

### 3-5. Watchlist (관심종목)

**목적**: 추적 중인 종목의 상태를 한눈에 파악

**특수 UX**:
- Active signals 섹션이 항상 최상단 (시그널 있는 종목 강조)
- 종목 아이콘: 시그널 타입에 따라 색상 변화
  - 빨강: 매수 시그널
  - 주황: 관찰 중 (변동성 감지)
  - 회색: 일반 관찰
- 종목 롱프레스 → Bottom sheet: Edit / Remove / Move to strategy
- Filter pills: 전략별, 시장별, 시그널 유무별 필터링

### 3-6. Reports

**목적**: 자동 생성된 분석 리포트 열람

**리포트 타입**:
| 타입 | 빈도 | 내용 |
|------|------|------|
| Daily macro | 매일 09:15 | 매크로 시황 + 시장 판단 |
| Trade signal | 수시 (시그널 발생 시) | 종목/전략/진입가/손절가 |
| Weekly review | 매주 일요일 | 주간 성과 + 원칙 준수율 |
| Evolution log | 매주 (수동) | 시스템 개선 이력 |

**특수 UX**:
- 오늘의 브리핑은 파란 좌측 테두리로 강조
- 리포트 목록은 타임라인 형태 (날짜별 그룹핑)
- "Acted" 배지: 리포트의 시그널을 실제 실행한 경우 표시

---

## 4. 화면 전환 (Navigation Flow)

### 4-1. 주요 네비게이션 패턴

```
[Bottom Tab] → 각 메인 화면 (5개)
[Dashboard Alert Tap] → 관련 화면 딥링크
[Watchlist Stock Tap] → Charts 화면 (해당 종목)
[Charts Search] → 종목 검색 → Charts 화면
[Strategy Card Tap] → 해당 전략 시그널 목록 (Modal/Sheet)
[Report Tap] → 리포트 상세 (Full screen)
[Indicator Tap (Macro)] → 히스토리 차트 (Inline expand)
[Long Press (Watchlist)] → Bottom sheet (Edit/Remove)
```

### 4-2. 크로스 화면 링크
- **어디서든 종목 이름 탭** → Charts 화면으로 이동 (종목 자동 로드)
- **Portfolio → 보유 종목 탭** → Charts 화면
- **Alert → 시그널 알림 탭** → Charts 화면 + 시그널 오버레이

---

## 5. Batch / Bot / Real-time 플로우

### 시스템 운용 플로우

![Daily Batch & Alert Flow](./images/06-batch-flow.png)

### Telegram Bot 알림 디자인

![Telegram Alert Mockups](./images/05-telegram.png)

### 5-1. 일일 배치 타임라인

```
시간       이벤트              트리거
──────────────────────────────────────────
08:30 KST  Gap check + 데이터 수집   APScheduler (cron)
08:40      병렬 분석 (4개 팀 subagent) 데이터 수집 완료
08:55      오케스트레이터 종합         분석 완료
09:00      원칙 체크                  종합 판단 완료
09:15      리포트 생성 + 알림 발송    전체 완료
09:20      메모리 리로더 실행         알림 발송 완료
──────────────────────────────────────────
장중       관심종목 1시간 리프레시     APScheduler (interval)
장중       실시간 알림 (원칙/시그널)    이벤트 트리거
──────────────────────────────────────────
22:00 KST  미국장 프리마켓 분석       APScheduler (cron)
22:15      해외 종목 시그널 체크      분석 완료
```

### 5-2. Telegram Bot 메시지 포맷

| 알림 타입 | 트리거 | 메시지 구조 |
|----------|--------|-----------|
| Morning briefing | 아침 배치 완료 | 시장 상태 + 전략 요약 + 포트폴리오 |
| Trade signal | 시그널 감지 | 종목 + 가격 + 진입/손절/목표 + R:R |
| Principle warning | 원칙 위반 감지 | 위반 항목 + 현재값 + 조치 제안 |
| Price alert | 목표가 도달 | 종목 + 현재가 + 원래 목표 |
| Weekly review | 일요일 배치 | 주간 수익률 + 원칙 준수율 |

### 5-3. 실시간 이벤트 트리거

| 이벤트 | 감지 방법 | 알림 채널 |
|--------|----------|----------|
| 원칙 위반 임박 (비중 초과 등) | 포지션 변경 시 체크 | Telegram + In-app badge |
| 스윙 매수 타점 진입 | 기술적 분석 + 수급 교차 | Telegram + Push |
| 거래대금 급증 (관심종목) | 1시간 리프레시 시 감지 | In-app alert |
| 매크로 급변 (VIX 급등 등) | 외부 데이터 모니터링 | Telegram (긴급) |
| 손절선 근접 | 실시간 가격 체크 | Telegram + Push (긴급) |

---

## 6. 반응형 레이아웃 전략

| 화면 | Mobile (< 768px) | Desktop (>= 768px) |
|------|-------------------|---------------------|
| Dashboard | 단일 컬럼, 카드 스택 | 2컬럼: 왼쪽(지표+전략) / 오른쪽(포트폴리오+알림) |
| Macro | 단일 컬럼 | 2컬럼: 왼쪽(지표) / 오른쪽(차트+이벤트) |
| Charts | 풀스크린 차트 + 하단 시트 | 왼쪽(차트 60%) / 오른쪽(분석 패널 40%) |
| Portfolio | 단일 컬럼 | 2컬럼: 왼쪽(잔고+리스크) / 오른쪽(원칙+홀딩) |
| Watchlist | 단일 컬럼 리스트 | 2컬럼: 왼쪽(리스트) / 오른쪽(선택 종목 미니차트) |

---

## 7. 기술 구현 스펙 요약

| 컴포넌트 | 기술 |
|----------|------|
| 프레임워크 | Next.js 14+ (App Router) |
| 스타일링 | Tailwind CSS |
| 차트 | TradingView Lightweight Charts |
| 상태 관리 | Zustand (경량) |
| API 통신 | SWR (실시간 리프레시) |
| 알림 | Telegram Bot API + Web Push API |
| 모바일 | PWA (Progressive Web App) |
| 배포 | Vercel (프론트) + 로컬 Python 서버 (분석 엔진) |
