# 🏗️ AI 주식 분석 & 매매가이드 시스템 — Claude Code 아키텍처 가이드

---

## 0. 크로스 플랫폼 & 한국투자증권 API 환경 명세

### 0-1. macOS / Windows 양쪽 구동 보장 전략

이 시스템은 개발자가 Mac과 Windows를 오가며 작업할 수 있어야 합니다.

#### 핵심 원칙: OS에 종속되는 코드를 절대 쓰지 않는다

| 이슈 | 해결 방법 |
|------|----------|
| **경로 구분자** (`/` vs `\`) | Python `pathlib.Path` 전용 사용. 문자열 경로 조합 금지 |
| **쉘 스크립트** (.sh vs .bat) | Python 스크립트(`scripts/*.py`)로 통일. `subprocess`로 실행 |
| **환경 변수** | `.env` 파일 + `python-dotenv`. OS별 export/set 차이 제거 |
| **줄바꿈** (LF vs CRLF) | `.gitattributes`에 `* text=auto eol=lf` 설정 |
| **타임존** | `pytz` 또는 `zoneinfo`로 KST/EST 명시 관리 |
| **cron (스케줄러)** | Mac: `launchd` 또는 cron / Windows: `Task Scheduler` → **통합: APScheduler (Python)** 사용 |
| **ta-lib 설치** | Mac: `brew install ta-lib` / Windows: 미리 빌드된 wheel 사용 → **대안: `pandas-ta` (순수 Python, 무설치)** 권장 |

#### 프로젝트 루트에 필수 설정 파일들

```
stock-advisor/
├── .env.example          # API 키 템플릿 (절대 .env를 커밋하지 않음)
├── .gitattributes        # eol=lf 강제
├── .gitignore            # .env, __pycache__, *.sqlite, node_modules
├── pyproject.toml        # Python 의존성 (pip 대신 uv 또는 poetry 권장)
├── package.json          # Node.js 의존성 (웹앱 + MCP 서버)
└── Makefile / justfile   # 크로스 플랫폼 태스크 러너 (just는 Windows 네이티브 지원)
```

#### `.env.example` 파일

```bash
# === 한국투자증권 API ===
KIS_APP_KEY=your_app_key_here
KIS_APP_SECRET=your_app_secret_here
KIS_ACCOUNT_NO=00000000-00       # 계좌번호 (8자리-2자리)
KIS_IS_PAPER=true                # true=모의투자, false=실전투자

# === 외부 데이터 ===
FRED_API_KEY=your_fred_key       # 미 연준 경제 데이터
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id

# === 시스템 ===
DB_PATH=./data/db/stock-advisor.sqlite
TIMEZONE=Asia/Seoul
LOG_LEVEL=INFO
```

> **중요**: Claude Code에서 `claude mcp add` 명령으로 MCP 서버를 등록할 때, `--env` 플래그로 `.env`의 값을 MCP 서버 프로세스에 전달할 수 있습니다.

#### 크로스 플랫폼 스케줄러 통합 예시

```python
# scripts/scheduler.py — Mac/Windows 양쪽에서 동일하게 동작
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import platform

scheduler = BlockingScheduler()

# 한국장 장전 분석 (매일 오전 8시 30분 KST)
scheduler.add_job(run_daily_macro, CronTrigger(hour=8, minute=30, timezone="Asia/Seoul"))

# 미국장 장전 분석 (매일 오후 10시 KST = 미국 개장 전)
scheduler.add_job(run_us_market_pre, CronTrigger(hour=22, minute=0, timezone="Asia/Seoul"))

# 관심종목 차트 리프레시 (매 1시간)
scheduler.add_job(refresh_watchlist, "interval", hours=1)

print(f"Scheduler started on {platform.system()}")
scheduler.start()
```

### 0-2. 한국투자증권 (KIS) OpenAPI 연동 상세

한투 API 키를 이미 발급받은 상태이므로, MCP 서버로 래핑하여 모든 팀이 공유합니다.

#### KIS API 핵심 엔드포인트 매핑

| 팀 | 필요 API | KIS 엔드포인트 | 용도 |
|----|---------|---------------|------|
| **매크로 분석** | 지수 시세 | `/uapi/domestic-stock/v1/quotations/inquire-index-price` | KOSPI, KOSDAQ, 환율 |
| **기술적 분석** | 일/분 차트 | `/uapi/domestic-stock/v1/quotations/inquire-daily-chartprice` | 봉차트 데이터 |
| **수급/종목** | 거래 상위 | `/uapi/domestic-stock/v1/quotations/volume-rank` | 거래대금 상위 종목 |
| **수급/종목** | 투자자별 매매 | `/uapi/domestic-stock/v1/quotations/inquire-investor` | 기관/외국인 수급 |
| **계좌관리** | 잔고 조회 | `/uapi/domestic-stock/v1/trading/inquire-balance` | 보유 종목, 평가손익 |
| **계좌관리** | 주문 | `/uapi/domestic-stock/v1/trading/order-cash` | 매수/매도 (실전 주의!) |
| **계좌관리** | 체결 내역 | `/uapi/domestic-stock/v1/trading/inquire-daily-ccld` | 당일 체결 조회 |
| **매크로 분석** | 해외 지수 | `/uapi/overseas-price/v1/quotations/inquire-daily-chartprice` | S&P500, 나스닥, 달러인덱스 |
| **기술적 분석** | 해외 종목 | `/uapi/overseas-stock/v1/quotations/inquire-search` | 미국 개별 종목 |

#### MCP 서버: KIS API 래퍼 구조

```
mcp-servers/
└── kis-api/
    ├── package.json
    ├── src/
    │   ├── index.ts              # MCP 서버 진입점
    │   ├── auth.ts               # OAuth 토큰 관리 (자동 갱신)
    │   ├── tools/
    │   │   ├── domestic-price.ts  # 국내 시세 조회
    │   │   ├── overseas-price.ts  # 해외 시세 조회
    │   │   ├── chart-data.ts      # 차트 데이터 (일봉/분봉)
    │   │   ├── volume-rank.ts     # 거래량 상위
    │   │   ├── investor-flow.ts   # 투자자별 매매동향
    │   │   ├── account-balance.ts # 계좌 잔고
    │   │   └── order.ts           # 주문 (안전장치 포함)
    │   └── utils/
    │       ├── rate-limiter.ts    # 초당 20건 제한 관리
    │       └── market-hours.ts    # 장 운영시간 체크
    └── CLAUDE.md                  # KIS API 사용 규칙
```

#### KIS API 안전장치 (필수)

```markdown
# mcp-servers/kis-api/CLAUDE.md

## 주문 API 절대 규칙
1. KIS_IS_PAPER=true (모의투자) 상태에서만 주문 실행 허용
2. 실전투자 전환 시 반드시 개발자의 명시적 확인 필요
3. 1회 주문 금액 상한: 총 자산의 5% 이내
4. 손절 주문은 반드시 동시에 설정 (OCO 로직)

## 토큰 관리
- OAuth 토큰은 24시간 유효 → 만료 1시간 전 자동 갱신
- 토큰은 메모리에만 보관, 파일/DB에 절대 저장하지 않음

## Rate Limit
- 초당 최대 20건 (KIS 정책)
- 연속 호출 시 100ms 간격 유지
- 429 응답 시 60초 대기 후 재시도
```

#### `.mcp.json` — KIS 서버 등록 예시

```jsonc
{
  "mcpServers": {
    "kis-api": {
      "command": "node",
      "args": ["mcp-servers/kis-api/dist/index.js"],
      "env": {
        "KIS_APP_KEY": "${KIS_APP_KEY}",
        "KIS_APP_SECRET": "${KIS_APP_SECRET}",
        "KIS_ACCOUNT_NO": "${KIS_ACCOUNT_NO}",
        "KIS_IS_PAPER": "${KIS_IS_PAPER}"
      }
    }
    // ... 다른 MCP 서버들
  }
}
```

---

## 1. 핵심 Claude Code 개념 매핑

당신이 설계한 8개 팀 구조를 Claude Code로 구현하려면 아래 5가지 핵심 개념을 조합해야 합니다.

### 1-1. `CLAUDE.md` — 프로젝트의 두뇌이자 기억

| 레벨 | 파일 위치 | 역할 |
|------|-----------|------|
| **루트** | `/CLAUDE.md` | 총괄 오케스트레이터의 관점. 전체 프로젝트 구조, 팀 간 협업 규칙, 투자 7계명, 글로벌 컨벤션 |
| **팀별** | `/teams/macro-analysis/CLAUDE.md` | 해당 팀의 전문 컨텍스트. 매크로 분석팀이라면 "채권-금리-환율 상관관계 분석 프레임워크", 참고 데이터 경로, 분석 템플릿 |
| **기능별** | `/teams/macro-analysis/fed-watcher/CLAUDE.md` | 세부 모듈의 동작 규약. "연준 발언 파싱 → 감성분석 → DB 저장" 같은 파이프라인 명세 |

> **핵심 포인트**: CLAUDE.md는 AI가 "길을 잃지 않게" 하는 **영구 컨텍스트**입니다. 팀별 CLAUDE.md에 해당 팀의 분석 프레임워크, 원칙, 데이터 스키마를 명세하면 Claude Code가 항상 그 맥락 위에서 코드를 생성합니다.

### 1-2. Custom Slash Commands — 워크플로우 자동화

`.claude/commands/` 디렉토리에 커스텀 명령어를 만들어 반복 작업을 자동화합니다.

```
.claude/commands/
├── spec-interview.md       # /spec-interview → 스펙 면담 (진화팀 면접관 역할)
├── daily-macro.md          # /daily-macro → 매크로 일일 분석 실행
├── scan-supply-demand.md   # /scan-supply-demand → 수급 스캔
├── portfolio-check.md      # /portfolio-check → 계좌 안정성 체크
├── generate-report.md      # /generate-report → 종합 리포트 생성
├── evolve-review.md        # /evolve-review → 진화팀 심층 면접 시뮬레이션
├── add-watchlist.md        # /add-watchlist $TICKER → 관심종목 추가
├── system-health-check.md  # /system-health-check → 시스템 정합성 체크
├── onboard-knowledge.md    # /onboard-knowledge $PATH → 학습 자료 투입
└── backtest.md             # /backtest $STRATEGY → 전략 백테스트
```

**예시: `/daily-macro.md`**
```markdown
매크로 경제 일일 분석을 수행하세요.

1. /teams/macro-analysis/data/sources.json의 데이터 소스를 확인
2. 최신 금리/환율/채권 데이터를 수집하여 DB에 저장
3. 전일 대비 변동 분석 수행
4. 상승장/조정장/하락장 판단 근거를 작성
5. /reports/daily/ 에 날짜별 마크다운 리포트 생성
6. 총괄 오케스트레이터용 요약을 /data/daily-summary.json에 저장
```

### 1-3. MCP (Model Context Protocol) 서버 — 외부 세계와의 연결

각 팀이 필요로 하는 외부 데이터/도구를 MCP 서버로 연결합니다.

```jsonc
// .mcp.json (프로젝트 루트) — Mac/Windows 동일하게 동작
{
  "mcpServers": {
    "kis-api": {
      "command": "node",
      "args": ["mcp-servers/kis-api/dist/index.js"],
      "env": {
        "KIS_APP_KEY": "${KIS_APP_KEY}",
        "KIS_APP_SECRET": "${KIS_APP_SECRET}",
        "KIS_ACCOUNT_NO": "${KIS_ACCOUNT_NO}",
        "KIS_IS_PAPER": "${KIS_IS_PAPER}"
      }
      // 국내 시세, 해외 시세, 차트, 수급, 계좌, 주문
    },
    "global-data": {
      "command": "python",
      "args": ["mcp-servers/global-data/server.py"],
      // FRED API, yfinance, 뉴스, YouTube 자막 추출
    },
    "sqlite-db": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-sqlite", "${DB_PATH}"]
      // Anthropic 공식 SQLite MCP 서버 (설치 없이 바로 사용)
    },
    "notification": {
      "command": "node",
      "args": ["mcp-servers/notification/index.js"],
      // 텔레그램/슬랙 알림 발송
    }
  }
}
```

### 1-4. Subagent (Task Tool) — 팀 간 병렬 실행

Claude Code의 **subagent(하위 에이전트)** 개념으로 각 팀을 병렬 실행합니다. 총괄 오케스트레이터가 여러 분석 태스크를 동시에 실행하고 결과를 종합하는 패턴입니다.

```
총괄 오케스트레이터 (메인 에이전트)
├── [Subagent 1] 매크로 분석 → macro-report.json
├── [Subagent 2] 기술적 분석 → technical-report.json  
├── [Subagent 3] 수급 스캔 → supply-demand-report.json
├── [Subagent 4] 원칙 체크 → principle-check.json
└── [Subagent 5] 계좌 상태 → portfolio-status.json
         ↓
    종합 판단 → 최종 투자 가이드 생성
```

### 1-5. Hooks — 자동 트리거

Claude Code의 Hook 시스템으로 특정 이벤트 발생 시 자동 실행됩니다.

```jsonc
// .claude/hooks.json
{
  "postSave": [
    {
      "pattern": "data/watchlist/**",
      "command": "python scripts/refresh-watchlist-charts.py"
    }
  ],
  "preCommit": [
    {
      "command": "python scripts/validate-investment-principles.py"
      // 원칙 위반 여부 자동 체크
    }
  ]
}
```

---

## 2. 프로젝트 폴더 구조

```
stock-advisor/
│
├── CLAUDE.md                          # 총괄 컨텍스트 (투자 철학, 팀 역할, 글로벌 규칙)
├── .env.example                       # API 키 템플릿 (KIS, FRED, Telegram)
├── .gitattributes                     # eol=lf 강제 (크로스 플랫폼)
├── .gitignore                         # .env, *.sqlite, __pycache__, node_modules
├── pyproject.toml                     # Python 의존성 (uv/poetry)
├── justfile                           # 크로스 플랫폼 태스크 러너
├── .claude/
│   ├── commands/                      # 커스텀 슬래시 명령어
│   │   ├── spec-interview.md          #    스펙 면담 (진화팀 면접관)
│   │   ├── daily-macro.md
│   │   ├── daily-technical.md
│   │   ├── scan-supply-demand.md
│   │   ├── portfolio-check.md
│   │   ├── generate-report.md
│   │   ├── evolve-review.md
│   │   ├── add-watchlist.md
│   │   ├── system-health-check.md
│   │   ├── onboard-knowledge.md
│   │   └── backtest.md
│   └── settings.json
│
├── .mcp.json                          # MCP 서버 설정
│
├── mcp-servers/                       # MCP 서버 구현체 (Mac/Windows 양쪽 동작)
│   ├── kis-api/                       # 한국투자증권 OpenAPI 래퍼
│   │   ├── src/
│   │   │   ├── index.ts               #   MCP 진입점
│   │   │   ├── auth.ts                #   OAuth 토큰 자동 갱신
│   │   │   └── tools/                 #   시세/차트/수급/계좌/주문
│   │   └── CLAUDE.md                  #   KIS API 사용 규칙 & 안전장치
│   ├── global-data/                   # 해외 데이터 통합 (FRED, yfinance, 뉴스)
│   └── notification/                  # 텔레그램 알림 서비스
│
├── teams/                             # 팀별 모듈 (Spec Agent)
│   ├── macro-analysis/                # 1. 경제 증시 분석팀
│   │   ├── CLAUDE.md                  #    팀 컨텍스트
│   │   ├── src/
│   │   │   ├── bond-rate-tracker.py
│   │   │   ├── fx-monitor.py
│   │   │   ├── fed-watcher.py
│   │   │   ├── liquidity-gauge.py
│   │   │   └── geopolitics-scanner.py
│   │   ├── templates/                 #    분석 템플릿
│   │   └── tests/
│   │
│   ├── fundamental-technical/         # 2. 기본적/기술적 분석팀
│   │   ├── CLAUDE.md
│   │   ├── src/
│   │   │   ├── sector-screener.py
│   │   │   ├── leading-stock-finder.py
│   │   │   ├── wave-analyzer.py       #    엘리엇 파동 등
│   │   │   └── indicator-engine.py    #    RSI, MACD, 볼린저밴드 등
│   │   └── tests/
│   │
│   ├── supply-demand/                 # 3. 수급/종목 관리팀
│   │   ├── CLAUDE.md
│   │   ├── src/
│   │   │   ├── volume-scanner.py
│   │   │   ├── institutional-flow.py
│   │   │   └── watchlist-manager.py
│   │   └── tests/
│   │
│   ├── principles/                    # 4. 심법 및 원칙 관리팀
│   │   ├── CLAUDE.md                  #    투자 7계명 명세
│   │   ├── src/
│   │   │   ├── principle-checker.py
│   │   │   └── fomo-detector.py
│   │   └── rules/
│   │       └── seven-commandments.md
│   │
│   ├── portfolio/                     # 5. 계좌관리팀
│   │   ├── CLAUDE.md
│   │   ├── src/
│   │   │   ├── asset-manager.py       #    자산 투자 계좌
│   │   │   ├── trading-manager.py     #    트레이딩 계좌
│   │   │   ├── risk-calculator.py     #    MDD, 샤프지수
│   │   │   └── emotion-guard.py       #    FOMO/공포 방지 로직
│   │   └── tests/
│   │
│   ├── orchestrator/                  # 6. 총괄 오케스트레이터
│   │   ├── CLAUDE.md
│   │   ├── src/
│   │   │   ├── synthesizer.py         #    팀 결과 종합
│   │   │   ├── strategy-router.py     #    전략별 라우팅
│   │   │   │   # 단타 / 스윙 / 자산투자 병렬 시나리오
│   │   │   └── decision-engine.py
│   │   └── templates/
│   │       ├── daily-briefing.md
│   │       └── trade-signal.md
│   │
│   ├── utility/                       # 7. 유틸팀
│   │   ├── CLAUDE.md
│   │   ├── src/
│   │   │   ├── alerter.py
│   │   │   ├── reporter.py
│   │   │   ├── memory-reloader.py     #    팀별 데이터 리로딩
│   │   │   └── data-exporter.py
│   │   └── templates/
│   │
│   └── evolution/                     # 8. 진화팀
│       ├── CLAUDE.md
│       ├── src/
│       │   ├── needs-interviewer.py   #    심층 면접 시뮬레이션
│       │   ├── improvement-proposer.py
│       │   └── knowledge-accumulator.py
│       └── evolution-log.md
│
├── webapp/                            # 개발 Agent — 웹앱
│   ├── CLAUDE.md
│   ├── package.json
│   ├── src/
│   │   ├── app/                       #    Next.js App Router
│   │   │   ├── dashboard/             #    메인 대시보드
│   │   │   ├── macro/                 #    매크로 분석 뷰
│   │   │   ├── charts/                #    차트 분석 뷰
│   │   │   ├── portfolio/             #    포트폴리오 뷰
│   │   │   ├── watchlist/             #    관심종목 뷰
│   │   │   └── reports/               #    리포트 뷰
│   │   ├── components/
│   │   └── lib/
│   └── public/
│
├── data/                              # 공유 데이터 레이어
│   ├── db/
│   │   └── stock-advisor.sqlite       #    메인 SQLite DB
│   ├── daily-summaries/               #    일일 요약 JSON
│   ├── watchlist/
│   └── reports/
│
├── docs/                              # SDD 문서
│   ├── specs/                         #    기능 명세서
│   │   ├── SPEC-001-macro-analysis.md
│   │   ├── SPEC-002-technical-analysis.md
│   │   └── ...
│   ├── architecture.md
│   ├── data-schema.md
│   └── changelog.md
│
├── scripts/                           # 유틸리티 스크립트
│   ├── daily-routine.sh               #    일일 루틴 실행
│   ├── refresh-watchlist-charts.py
│   └── validate-investment-principles.py
│
└── knowledge/                         # 지식 베이스 (진화팀 관리)
    ├── macro/                         #    매크로 학습 자료
    ├── sectors/                       #    섹터별 분석 자료
    ├── youtube-summaries/             #    유튜브 분석 요약
    └── historical-patterns/           #    역사적 패턴 DB
```

---

## 3. 데이터베이스 전략: SQLite를 권장하는 이유

| 기준 | SQLite (로컬) | Google Sheets |
|------|--------------|---------------|
| **속도** | 밀리초 단위 쿼리 | API 호출 1~3초 |
| **데이터량** | 수백만 행 가능 | 1,000만 셀 제한 |
| **복잡한 쿼리** | SQL 풀 지원 | 제한적 |
| **오프라인** | 완전 지원 | 불가 |
| **MCP 연동** | 네이티브 지원 | API 래핑 필요 |
| **백업** | 파일 복사 한 줄 | 자동 (장점) |
| **협업/공유** | 추가 작업 필요 | 즉시 가능 (장점) |

### 권장 구성

```
메인 DB: SQLite (stock-advisor.sqlite)
├── 테이블: daily_macro        # 일일 매크로 데이터
├── 테이블: watchlist          # 관심종목 관리
├── 테이블: trade_signals      # 매매 시그널 기록
├── 테이블: portfolio_log      # 계좌 이력
├── 테이블: analysis_reports   # 분석 리포트
├── 테이블: knowledge_base     # 학습 데이터 (진화팀)
└── 테이블: principles_audit   # 원칙 준수 감사 로그

보조: JSON 파일 (일일 요약, 설정, 템플릿)
선택: Google Sheets (리포트 공유/열람용 미러링)
```

> **결론**: 분석 엔진은 SQLite, 사람이 보는 리포트만 필요 시 Google Sheets로 내보내는 하이브리드 구성이 최적입니다.

---

## 4. SDD(Spec-Driven Development) + 바이브 코딩 워크플로우

### 4-1. SDD의 핵심 사이클

```
[1단계] 스펙 작성 (docs/specs/SPEC-XXX.md)
    ↓  사람이 "무엇을" 정의
[2단계] CLAUDE.md에 컨텍스트 등록
    ↓  AI가 이해할 수 있게 연결
[3단계] Claude Code로 바이브 코딩
    ↓  "이 스펙대로 구현해줘" → AI가 코드 생성
[4단계] 테스트 & 검증
    ↓  자동 테스트 + 수동 확인
[5단계] 진화팀 리뷰 (/evolve-review)
    ↓  개선점 발굴, 숨은 의도 탐색
[6단계] 스펙 업데이트 → 다시 1단계
```

### 4-2. 스펙 문서 템플릿 예시

```markdown
# SPEC-001: 매크로 경제 일일 분석

## 목적
매일 장 시작 전, 글로벌 매크로 경제 상황을 자동 수집/분석하여
상승장·조정장·하락장 판단 근거를 제공한다.

## 입력
- 미국 10년물 국채 금리 (Fred API)
- 달러 인덱스 (DXY)
- 원/달러 환율
- VIX 지수
- 연준 일정 및 발언 (RSS/뉴스)
- Fear & Greed Index

## 출력
- daily_macro 테이블에 데이터 저장
- 시장 상태 판단: { state: "상승장"|"조정장"|"하락장", confidence: 0~100, reasons: [] }
- 마크다운 리포트 생성

## 판단 로직
- 금리 상승 + 달러 강세 + VIX 상승 → 하락장 경고
- 금리 안정 + 유동성 증가 + VIX 하락 → 상승장 신호
- (상세 로직은 팀 CLAUDE.md에 점진적으로 축적)

## 연관 팀
- 기술적 분석팀: 지수 차트와 교차 검증
- 원칙 관리팀: 하락장 판단 시 비중 축소 원칙 트리거
```

### 4-3. 바이브 코딩 실전 흐름

Claude Code 터미널에서 이렇게 작업합니다:

```bash
# 1. 스펙 기반으로 팀 모듈 생성
> 이 SPEC-001 문서를 읽고 macro-analysis 팀의 코드를 구현해줘.
  MCP market-data 서버를 활용하고, SQLite에 저장하는 구조로.

# 2. 커스텀 명령어로 일일 루틴 실행
> /daily-macro

# 3. 결과를 보고 오케스트레이터로 종합
> /generate-report

# 4. 진화팀 리뷰
> /evolve-review  
  # → "현재 VIX만 보고 있는데 SKEW 지수도 추가하면 
  #    꼬리 위험 감지력이 올라갑니다. 추가할까요?"

# 5. 관심종목 추가
> /add-watchlist NVDA
  # → 자동으로 차트 분석 + 수급 체크 + DB 저장
```

---

## 5. 병렬 전략 운용 아키텍처

당신이 원하는 3가지 전략을 병렬로 운용하는 구조:

```
┌─────────────────────────────────────────────────┐
│              총괄 오케스트레이터                    │
│         (전략별 독립 판단 → 종합 브리핑)            │
└────────┬──────────────┬──────────────┬──────────┘
         │              │              │
    ┌────▼────┐   ┌────▼────┐   ┌────▼────┐
    │  단타    │   │  스윙   │   │  자산   │
    │ 트레이딩 │   │ 트레이딩│   │  투자   │
    ├─────────┤   ├─────────┤   ├─────────┤
    │시간: 당일│   │시간:수일│   │시간:수개│
    │         │   │~수주    │   │월~수년  │
    │변동성   │   │수급 모멘│   │시대적   │
    │캔들패턴 │   │텀 추적  │   │주도주   │
    │호가분석 │   │기관외국인│   │산업 성장│
    │거래대금 │   │거래대금 │   │밸류에이션│
    ├─────────┤   ├─────────┤   ├─────────┤
    │별도 계좌│   │별도 계좌│   │별도 계좌│
    │비중:소  │   │비중:중  │   │비중:대  │
    │손절:-2% │   │손절:-5% │   │손절:-15%│
    └─────────┘   └─────────┘   └─────────┘
         │              │              │
         └──────────────┼──────────────┘
                        ▼
              원칙 관리팀 교차 검증
              (총 비중, MDD, 감정 체크)
```

각 전략은 `teams/orchestrator/src/strategy-router.py`에서 독립 서브에이전트로 실행되며, 계좌관리팀이 전체 리스크를 통합 모니터링합니다.

---

## 6. 기술 스택 권장안

| 영역 | 권장 기술 | 이유 |
|------|----------|------|
| **AI 엔진** | Claude Code + MCP | 멀티에이전트, 컨텍스트 유지, 도구 연동 |
| **백엔드** | Python (FastAPI) | 금융 라이브러리 생태계 (pandas, pandas-ta, yfinance) |
| **프론트엔드** | Next.js + Tailwind | SSR, 모바일 반응형, 빠른 프로토타이핑 |
| **DB** | SQLite (개발/개인) → PostgreSQL (확장 시) | 무설치, 단일파일, SQL 풀지원, **Mac/Win 동일** |
| **차트** | Lightweight Charts (TradingView 오픈소스) | 전문 금융 차트 |
| **알림** | Telegram Bot API | 모바일 즉시 알림, 무료, 구현 간단 |
| **스케줄링** | **APScheduler** (Python) | Mac/Windows 양쪽 동일 동작 (cron/Task Scheduler 불필요) |
| **국내 데이터** | **한국투자증권 OpenAPI** (KIS) | API 키 발급 완료, 국내+해외 시세/주문 통합 |
| **해외 데이터** | yfinance + FRED API | 무료, 글로벌 지수/금리/경제지표 |
| **기술 지표** | **pandas-ta** (ta-lib 대신) | 순수 Python, Mac/Windows 설치 이슈 없음 |
| **패키지 관리** | **uv** (Python) + pnpm (Node) | 빠르고 크로스 플랫폼 안정적 |
| **태스크 러너** | **just** (justfile) | Make 대안, Windows 네이티브 지원 |

---

## 7. 개발 로드맵 — 개발자 vs Claude Code 역할 분담 상세

> 💡 **원칙**: 개발자는 "무엇을"과 "왜"를 결정하고, Claude Code는 "어떻게"를 실행한다.
> 단, 스펙 작성조차 Claude Code가 면담을 통해 도와준다.

---

### Phase 0 — 초기 환경 세팅 (개발자가 직접 해야 할 것)

이 단계는 Claude Code가 대신할 수 **없는** 것들입니다.

| # | 할 일 | 이유 |
|---|-------|------|
| 1 | **Claude Code 설치** | `npm install -g @anthropic-ai/claude-code` |
| 2 | **Anthropic API 키 등록** | 결제 및 인증은 사람만 가능 |
| 3 | **한국투자증권 API 키 발급 확인** | KIS Developers 사이트에서 앱키/시크릿 발급 (이미 완료) |
| 4 | **`.env` 파일 생성** | `.env.example`을 복사 후 실제 키 입력. **절대 커밋하지 않음** |
| 5 | **Git 저장소 초기화** | `git init` + GitHub/GitLab 리모트 연결 |
| 6 | **Node.js + Python 설치 확인** | Node 18+, Python 3.11+ |
| 7 | **패키지 매니저 선택** | Python: `uv` 또는 `poetry` / Node: `npm` 또는 `pnpm` |
| 8 | **모의투자 계좌 설정** | KIS 모의투자 신청 (실전 전까지 반드시 모의투자로 테스트) |
| 9 | **FRED API 키 발급** | https://fred.stlouisfed.org/docs/api/api_key.html |
| 10 | **Telegram Bot 생성** | @BotFather로 봇 생성 + 채팅방 ID 확보 |

```bash
# 개발자가 직접 터미널에서 실행
mkdir stock-advisor && cd stock-advisor
git init
cp .env.example .env   # 그 다음 직접 키 입력
claude                  # Claude Code 진입
```

---

### Phase 1 — 초기 스캐폴딩 (Claude Code가 해주는 것)

개발자가 Claude Code를 열고 이렇게 말합니다:

```
> 이 프로젝트의 폴더 구조를 만들어줘. 
  stock-advisor-architecture-guide.md의 "프로젝트 폴더 구조"를 참고해서.
  그리고 각 팀별 CLAUDE.md 초안도 생성해줘.
```

#### Claude Code가 자동으로 생성하는 것들

| 카테고리 | 생성물 | 설명 |
|---------|-------|------|
| **폴더 구조** | `teams/`, `mcp-servers/`, `webapp/`, `data/`, `docs/`, `scripts/`, `knowledge/` 전체 트리 | 아키텍처 문서 기반 |
| **CLAUDE.md 계층** | 루트 + 8개 팀별 CLAUDE.md | 각 팀의 역할, 원칙, 입출력 형식 초안 |
| **설정 파일** | `.env.example`, `.gitignore`, `.gitattributes`, `pyproject.toml`, `package.json` | 크로스 플랫폼 대응 |
| **DB 스키마** | `data/db/schema.sql` + 초기 SQLite 생성 스크립트 | 테이블 정의 |
| **커맨드 템플릿** | `.claude/commands/*.md` 전체 | 슬래시 명령어 틀 |
| **MCP 서버 뼈대** | `mcp-servers/kis-api/` 프로젝트 초기 구조 | package.json, tsconfig, 엔트리포인트 |
| **스펙 템플릿** | `docs/specs/SPEC-TEMPLATE.md` | 모든 스펙 문서의 기본 양식 |
| **docs 초안** | `docs/architecture.md`, `docs/data-schema.md` | 자동 문서화 시작 |

```bash
# Claude Code 안에서 이어서
> SQLite 스키마를 설계하고 초기 DB를 생성해줘.
  daily_macro, watchlist, trade_signals, portfolio_log, 
  analysis_reports, knowledge_base, principles_audit 테이블이 필요해.

> KIS API MCP 서버의 뼈대 코드를 만들어줘.
  OAuth 토큰 자동 갱신, 초당 20건 rate limit, 
  국내 시세/해외 시세/차트/수급/계좌 잔고 tool을 포함해서.
```

#### 이 단계에서 개발자가 확인할 것
- [ ] 생성된 폴더 구조가 자신의 멘탈 모델과 일치하는지
- [ ] CLAUDE.md의 팀별 역할 기술이 의도와 맞는지
- [ ] .env.example에 빠진 키가 없는지
- [ ] KIS MCP 서버가 모의투자 모드로 설정되어 있는지

---

### Phase 2 — 스펙 드리븐 개발 (개발자 스펙 명세 + Claude Code 구현)

이 단계부터가 진짜 SDD 바이브 코딩입니다.

#### 2-A. 스펙 면담 기능 — `/spec-interview` 커맨드

> 핵심: 개발자가 "매크로 분석팀 기능 만들고 싶어"라고 막연하게 말해도,
> Claude Code가 **체계적인 면담**을 통해 상세 스펙을 함께 완성합니다.

```markdown
# .claude/commands/spec-interview.md

당신은 진화팀의 심층 면접관입니다.
개발자가 만들고 싶은 기능에 대해 구조화된 면담을 진행하여
docs/specs/ 에 저장할 완전한 스펙 문서를 함께 작성합니다.

## 면담 프로토콜

### 1라운드: 본질 파악 (What & Why)
- "이 기능이 해결하려는 핵심 문제가 무엇인가요?"
- "이 기능이 없으면 어떤 불편이 있나요?"
- "이상적으로 동작한다면, 아침에 켰을 때 무엇이 보여야 하나요?"

### 2라운드: 경계 확인 (Scope & Boundary)
- "이 기능이 하지 말아야 할 것은 무엇인가요?"
- "다른 팀(모듈)과 겹치는 영역이 있나요?"
- "국장/미장/코인 중 어디까지 커버해야 하나요?"
- "데이터는 실시간이어야 하나요, 일 단위 배치로 충분한가요?"

### 3라운드: 입출력 구체화 (I/O & Data)
- "입력 데이터는 어디서 오나요? (KIS API / 크롤링 / 수동 입력)"
- "출력은 어떤 형태가 이상적인가요? (DB 저장 / 리포트 / 알림 / 차트)"
- "다른 팀이 이 결과를 어떻게 사용하나요?"

### 4라운드: 숨은 의도 발굴 (Hidden Intent)
- "혹시 이 기능을 통해 궁극적으로 하고 싶은 것이 따로 있나요?"
- "비슷한 상황에서 과거에 실수한 경험이 있다면?"
- "이 기능이 완벽하게 동작해도, 추가로 아쉬울 것 같은 점이 있나요?"
- 개발자의 답변에서 명시하지 않은 암묵적 요구사항을 추론하여 제안

### 5라운드: 우선순위 & 제약 (Priority & Constraint)
- "MVP(최소 기능)로 먼저 만든다면 어디까지가 1차인가요?"
- "성능 제약이 있나요? (KIS API 호출 제한, 실행 시간 등)"
- "크로스 플랫폼(Mac/Windows) 관련 특별 고려사항이 있나요?"

## 면담 후 자동 생성물
1. `docs/specs/SPEC-XXX-[기능명].md` — 완전한 스펙 문서
2. 해당 팀의 `CLAUDE.md` 업데이트 제안
3. 관련 다른 팀에 미치는 영향 분석
4. 구현 난이도 & 예상 시간 평가
5. "이것도 필요하지 않을까요?" 추가 제안 목록
```

#### 2-B. 스펙 작성 → 구현 → 검증 실전 흐름

```bash
# === STEP 1: 스펙 면담 ===
> /spec-interview
  # Claude: "어떤 팀의 어떤 기능을 만들고 싶으신가요?"
  # 개발자: "매크로 분석팀의 시장 상태 판단 기능"
  # Claude: (5라운드 면담 진행)
  # → docs/specs/SPEC-001-market-state-judge.md 자동 생성

# === STEP 2: 스펙 리뷰 ===
> 생성된 SPEC-001을 읽고 빠진 부분이 없는지 체크해줘.
  특히 하락장 판단 시 채권 금리 역전(역 커브) 지표가 포함되어야 해.
  # → 스펙 보완

# === STEP 3: 구현 지시 ===
> SPEC-001을 기반으로 teams/macro-analysis/src/ 에 구현해줘.
  KIS API MCP 서버로 데이터를 가져오고,
  판단 결과를 SQLite daily_macro 테이블에 저장하는 구조로.
  pandas-ta로 기술 지표 계산하고.

# === STEP 4: 테스트 ===
> macro-analysis 팀의 market-state-judge에 대한 
  유닛 테스트를 작성하고 실행해줘.
  실제 KIS API 대신 mock 데이터를 사용해서.

# === STEP 5: 연동 확인 ===
> /daily-macro 를 실행해서 end-to-end로 동작하는지 확인해줘.

# === STEP 6: 문서화 ===
> 방금 구현한 내용을 macro-analysis 팀의 CLAUDE.md에 반영해줘.
  그리고 docs/changelog.md에 변경 이력을 추가해줘.
```

#### 2-C. 팀별 스펙 개발 우선순위 로드맵

| 순서 | 팀 | 핵심 스펙 | 의존성 |
|------|-----|----------|--------|
| **1** | MCP: KIS API 서버 | 토큰 인증, 시세 조회, 차트 데이터 | `.env` 설정 완료 |
| **2** | 매크로 분석팀 | 시장 상태 판단, 금리/환율 추적 | KIS API MCP |
| **3** | 기술적 분석팀 | 지표 계산 엔진, 차트 패턴 감지 | KIS API MCP |
| **4** | 수급/종목 관리팀 | 거래대금 스캔, 관심종목 DB | KIS API MCP |
| **5** | 원칙 관리팀 | 투자 7계명 체커, FOMO 감지 | 매크로 + 계좌 데이터 |
| **6** | 계좌관리팀 | 잔고 조회, 리스크 계산, MDD | KIS API MCP + 원칙팀 |
| **7** | 총괄 오케스트레이터 | 팀 결과 종합, 전략 라우팅 | 1~6번 전체 |
| **8** | 유틸팀 | 알림, 리포트, 메모리 리로딩 | 오케스트레이터 |
| **9** | 진화팀 | 면접 프로토콜, 개선 제안 | 전체 시스템 |
| **10** | 웹앱 (개발Agent) | 대시보드, 차트 뷰, 모바일 | 전체 API 레이어 |

---

### Phase 3 — 오케스트레이션 & 웹앱

이 단계에서도 패턴은 동일합니다: `/spec-interview` → 스펙 → 구현 → 테스트

```bash
# 오케스트레이터 면담
> /spec-interview
  # "총괄 오케스트레이터의 종합 판단 로직을 만들고 싶어.
  #  3가지 전략(단타/스윙/자산)을 병렬로 돌리고 싶어."

# 웹앱 면담
> /spec-interview
  # "대시보드 메인 화면을 만들고 싶어.
  #  Mac에서도 모바일에서도 잘 보여야 해."
```

---

### Phase 4 — 지속적 진화

```bash
# 매주 실행
> /evolve-review

# 새 학습 자료 투입
> knowledge/ 폴더에 새로 넣은 매크로 분석 영상 요약을 
  매크로 분석팀의 CLAUDE.md에 반영해줘.

# 시스템 전체 건강 체크
> /system-health-check
```

---

## 8. 실전 팁

### CLAUDE.md 작성 핵심 원칙
```markdown
# 이렇게 쓰세요 (팀 CLAUDE.md 예시)

## 이 팀의 역할
매크로 경제 데이터를 수집·분석하여 시장 상태를 판단한다.

## 절대 원칙
- 단일 지표로 시장 판단하지 말 것 (최소 3개 지표 교차 검증)
- 데이터 없이 추측하지 말 것
- 모든 분석에 신뢰도(confidence) 점수를 포함할 것

## 데이터 소스
- /data/db/stock-advisor.sqlite → daily_macro 테이블
- MCP market-data 서버의 get_bond_yield, get_fx_rate 도구 사용

## 출력 형식
{ "date": "YYYY-MM-DD", "state": "상승장|조정장|하락장", 
  "confidence": 0-100, "indicators": [...], "summary": "..." }
```

### 진화팀이 진짜 작동하게 만드는 법
- `/evolve-review` 명령어에 "현재 시스템의 약점 3가지와 개선안을 제시하라"를 포함
- 매주 1회 실행하여 `evolution-log.md`에 변경 이력 축적
- 사용자가 제공하는 유튜브 링크, MD 자료를 `knowledge/` 디렉토리에 저장하면, CLAUDE.md에서 참조하여 팀의 분석 수준이 점진적으로 상승

### 메모리 리로딩 (유틸팀 핵심 기능)
```python
# memory-reloader.py 개념
# 각 팀의 CLAUDE.md에 최근 분석 결과 요약을 주입
# → Claude Code가 새 세션에서도 맥락을 유지

def reload_team_context(team_name):
    recent_data = db.query(f"SELECT * FROM {team_name}_log ORDER BY date DESC LIMIT 30")
    summary = summarize(recent_data)
    update_claude_md(f"teams/{team_name}/CLAUDE.md", summary)
```

---

## 9. 추가 보완 사항 — 놓치기 쉬운 것들

### 9-1. `.claude/commands/` 추가 커맨드

기존 커맨드에 더해 아래를 추가합니다:

```
.claude/commands/
├── spec-interview.md       # /spec-interview → 스펙 면담 (신규)
├── system-health-check.md  # /system-health-check → 전체 시스템 정합성 체크 (신규)
├── onboard-knowledge.md    # /onboard-knowledge → 새 학습 자료 투입 (신규)
├── backtest.md             # /backtest → 과거 데이터로 전략 백테스트 (신규)
├── daily-macro.md
├── daily-technical.md
├── scan-supply-demand.md
├── portfolio-check.md
├── generate-report.md
├── evolve-review.md
└── add-watchlist.md
```

### 9-2. Git 브랜치 전략 — AI 개발의 안전망

바이브 코딩에서 가장 위험한 것은 **AI가 잘 되던 코드를 망가뜨리는 것**입니다.

```
main (안정)
├── develop (통합 테스트)
│   ├── feature/macro-analysis    # 팀별 기능 개발
│   ├── feature/technical-engine
│   ├── feature/kis-mcp-server
│   └── feature/webapp-dashboard
```

**규칙**: Claude Code에게 항상 feature 브랜치에서 작업하게 하고, 동작 확인 후 develop에 머지합니다. `CLAUDE.md` 루트에 이 규칙을 명시하세요.

```markdown
# CLAUDE.md에 추가
## Git 규칙
- 새 기능은 반드시 feature/ 브랜치에서 작업한다
- main 브랜치에 직접 커밋하지 않는다
- 커밋 메시지: [팀명] 변경 내용 (예: [macro] 금리 역전 감지 로직 추가)
```

### 9-3. 에러 복구 & 롤백 전략

```markdown
# .claude/commands/system-health-check.md

전체 시스템 정합성을 검사합니다:

1. 모든 팀의 CLAUDE.md가 존재하고 필수 섹션이 있는지 확인
2. SQLite DB 스키마와 docs/data-schema.md가 일치하는지 확인  
3. MCP 서버가 정상 응답하는지 확인 (KIS API 토큰 유효성 포함)
4. 최근 daily-macro 실행 결과가 24시간 이내인지 확인
5. 관심종목 중 데이터가 3일 이상 업데이트 안 된 종목 경고
6. 원칙 관리팀의 최근 감사 로그 확인
7. 문제 발견 시 수정 제안 및 자동 수정 가능한 건 수정
```

### 9-4. 해외 시장 데이터 보조 소스

KIS API는 국내 데이터에 강하지만, 글로벌 매크로에는 보조 소스가 필요합니다:

| 데이터 | 무료 소스 | 용도 |
|--------|----------|------|
| 미국 경제 지표 | **FRED API** | 금리, CPI, 고용, GDP |
| 글로벌 지수/환율 | **yfinance** (Python) | S&P500, DXY, 금, 비트코인 |
| Fear & Greed | **CNN API** (비공식 크롤링) | 시장 심리 |
| 뉴스 헤드라인 | **NewsAPI** 또는 RSS | 이벤트 감지 |
| 연준 일정 | **FOMC Calendar** 크롤링 | 매크로 이벤트 |
| 유튜브 요약 | **yt-dlp** + 자막 추출 | 전문가 의견 수집 |

이것들을 `mcp-servers/global-data/` 라는 별도 MCP 서버로 묶습니다.

```jsonc
// .mcp.json에 추가
{
  "mcpServers": {
    "kis-api": { /* ... */ },
    "global-data": {
      "command": "python",
      "args": ["mcp-servers/global-data/server.py"],
      "env": {
        "FRED_API_KEY": "${FRED_API_KEY}"
      }
      // yfinance, FRED, 뉴스, 유튜브 자막 통합
    },
    "sqlite-db": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-sqlite", "${DB_PATH}"]
      // Anthropic 공식 SQLite MCP 서버 (즉시 사용 가능)
    },
    "notification": {
      "command": "node",
      "args": ["mcp-servers/notification/index.js"],
      "env": {
        "TELEGRAM_BOT_TOKEN": "${TELEGRAM_BOT_TOKEN}",
        "TELEGRAM_CHAT_ID": "${TELEGRAM_CHAT_ID}"
      }
    }
  }
}
```

### 9-5. 데이터 백업 자동화

```python
# scripts/backup.py — 매일 자동 실행
import shutil
from datetime import datetime
from pathlib import Path

DB_PATH = Path("data/db/stock-advisor.sqlite")
BACKUP_DIR = Path("data/backups")
BACKUP_DIR.mkdir(exist_ok=True)

# 일별 백업 (최근 30일 보관)
today = datetime.now().strftime("%Y-%m-%d")
shutil.copy2(DB_PATH, BACKUP_DIR / f"stock-advisor-{today}.sqlite")

# 오래된 백업 삭제
for old in sorted(BACKUP_DIR.glob("*.sqlite"))[:-30]:
    old.unlink()
```

### 9-6. 실전 전환 체크리스트

모의투자에서 실전으로 전환할 때 반드시 확인:

- [ ] 모의투자로 최소 30일 운용 완료
- [ ] 백테스트 결과와 모의투자 결과 비교 검증
- [ ] 원칙 관리팀의 감사 로그에 위반 사항 0건
- [ ] MDD가 설정 한도 이내
- [ ] `.env`의 `KIS_IS_PAPER=false`로 변경 (수동으로!)
- [ ] 초기 실전 자금은 총 투자 가능 금액의 10% 이내로 시작
- [ ] 손절 로직이 모든 전략에 설정되어 있는지 확인
- [ ] Telegram 알림이 정상 동작하는지 확인

---

## 요약: 당신이 활용할 Claude Code 핵심 기능 + 워크플로우

### Claude Code 핵심 기능 6가지

| # | 기능 | 당신의 시스템에서의 역할 |
|---|------|------------------------|
| 1 | **CLAUDE.md** (계층적) | 팀별 전문 컨텍스트 = AI가 길을 잃지 않는 나침반 |
| 2 | **Custom Slash Commands** | 일일 루틴, 분석 실행, 리포트 생성, **스펙 면담** 자동화 |
| 3 | **MCP Servers** | KIS API, 글로벌 데이터, SQLite, 알림 등 외부 도구 연결 |
| 4 | **Subagents** | 팀별 병렬 분석 실행 → 오케스트레이터 종합 |
| 5 | **Hooks** | 데이터 변경 시 자동 리프레시, 원칙 위반 자동 체크 |
| 6 | **`.env` + Git** | 크로스 플랫폼 환경 통일 + AI 개발의 안전망 |

### 개발 3단계 요약

```
┌─────────────────────────────────────────────────────────────┐
│  Phase 0: 개발자 직접                                         │
│  API 키 발급, .env 설정, Git 초기화, 모의투자 신청               │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 1: Claude Code 스캐폴딩                                │
│  "이 아키텍처 문서대로 폴더 만들고 CLAUDE.md 작성해줘"            │
│  → 폴더 구조, DB 스키마, MCP 뼈대, 커맨드 템플릿 자동 생성       │
└──────────────────────┬──────────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────────┐
│  Phase 2+: SDD 바이브 코딩 반복                                │
│  /spec-interview → 스펙 생성 → "이 스펙대로 구현해줘"            │
│  → 테스트 → /evolve-review → 스펙 개선 → 반복                  │
│                                                               │
│  이 사이클을 팀 1번(KIS MCP) → 2번(매크로) → ... → 10번(웹앱)   │
│  순서로 반복하면 시스템이 점진적으로 완성됩니다                     │
└─────────────────────────────────────────────────────────────┘
```

이 6가지 기능과 3단계 워크플로우를 조합하면, Mac과 Windows를 오가면서 한국투자증권 API를 기반으로 한 "자가 발전하는 유니콘 조직"의 디지털 트윈이 됩니다.

---
---

# 📋 심화 Q&A — 실전 구축 전 반드시 알아야 할 것들

---

## Q1. 하네스 엔지니어링이란? 이 프로젝트에 어떻게 적용하는가?

### 하네스 엔지니어링의 정의

**하네스(Harness) = 모델을 제외한, AI 에이전트를 둘러싼 모든 것**

말을 다루는 마구(harness)에서 유래한 용어입니다. AI 모델 자체는 "말"이고, 하네스는 그 말이 올바른 방향으로 달리게 하는 고삐, 안장, 길, 가드레일, 신호체계 전체를 뜻합니다.

```
프롬프트 엔지니어링  →  "말에게 뭐라고 말하는가" (단일 턴)
컨텍스트 엔지니어링  →  "말이 무엇을 보게 하는가" (단일 세션)
하네스 엔지니어링    →  "말이 달리는 환경 전체를 설계" (다중 세션, 장기 운용)
```

하네스 엔지니어링은 AI 에이전트가 **자율적으로 장시간** 작동할 때 필요한 5가지 기둥으로 구성됩니다:

| 기둥 | 설명 | 이 프로젝트에서의 적용 |
|------|------|----------------------|
| **1. 도구 오케스트레이션** | 에이전트가 뭘 할 수 있고 뭘 못 하는지 경계 정의 | MCP 서버별 도구 목록 + KIS 주문 API 안전장치 |
| **2. 컨텍스트 관리** | 세션 간 기억 전달, 상태 추적 | 계층적 CLAUDE.md + 메모리 리로더 + daily-summary.json |
| **3. 가드레일** | 에이전트가 위험한 행동을 못 하게 막는 결정론적 규칙 | 원칙 관리팀, 모의투자 강제, Git 브랜치 규칙 |
| **4. 피드백 루프** | 실패 시 원인을 하네스에 반영하여 재발 방지 | 진화팀 `/evolve-review`, evolution-log.md |
| **5. 검증 체계** | 에이전트 출력이 올바른지 자동 확인 | 테스트, 원칙 체크, `/system-health-check` |

### 이 프로젝트에 적용할 하네스 설계

#### A. Feedforward (사전 안내) — "AI가 실수하기 전에 방향을 잡아준다"

```
┌──────────────────────────────────────────────────┐
│                   FEEDFORWARD                     │
│                                                   │
│  CLAUDE.md 계층        → 팀별 역할/원칙/데이터 위치  │
│  docs/specs/*.md       → 구현 명세서                │
│  seven-commandments.md → 투자 원칙 (불변)           │
│  data-schema.md        → DB 스키마 (정합성 기준)     │
│  .claude/commands/*.md → 워크플로우 정의             │
│                                                   │
│  "AI에게 지도를 주지, 1000페이지 매뉴얼을 주지 마라"  │
│   → 팀별 CLAUDE.md는 짧고 핵심만. 상세는 참조 경로    │
└──────────────────────────────────────────────────┘
```

#### B. Feedback (사후 교정) — "AI가 실수하면 환경을 고친다"

```
┌──────────────────────────────────────────────────┐
│                    FEEDBACK                       │
│                                                   │
│  테스트 실패          → 코드 수정 (자동)             │
│  원칙 위반 감지       → principles_audit 기록 + 알림 │
│  /evolve-review 결과  → CLAUDE.md 업데이트          │
│  분석 정확도 저하     → knowledge/ 자료 보강         │
│  시스템 정합성 에러   → /system-health-check 복구    │
│                                                   │
│  핵심: "출력을 고치지 말고, 하네스를 고쳐라"          │
│   → AI가 같은 실수를 반복하면 CLAUDE.md나 규칙을 보강  │
│   → 프롬프트를 다시 쓰는 게 아니라 환경을 개선        │
└──────────────────────────────────────────────────┘
```

#### C. 진화팀 = 하네스 엔지니어

당신이 설계한 **8번 진화팀**은 사실상 "하네스 엔지니어" 역할입니다:

```markdown
# 진화팀의 하네스 엔지니어링 프로토콜

## 실패 발생 시 (Feedback Loop)
1. 문제가 발생한 팀의 출력 로그 분석
2. 원인 분류: 
   a) 컨텍스트 부족 → 해당 팀 CLAUDE.md에 정보 추가
   b) 규칙 미비 → 가드레일 규칙 추가
   c) 도구 부족 → MCP 서버에 새 도구 추가 제안
   d) 데이터 부족 → knowledge/ 보강 필요
3. 하네스 수정 후 동일 시나리오 재실행하여 검증
4. evolution-log.md에 "어떤 하네스를 왜 고쳤는지" 기록

## 정기 점검 (주 1회)
- "현재 하네스에서 제거할 수 있는 과잉 규칙은?"
  (모델이 발전하면 일부 가드레일은 불필요해짐)
- "새로 발견된 패턴으로 추가할 가드레일은?"
```

> **핵심 한줄 요약**: 하네스 엔지니어링 = "AI가 틀리면 AI를 탓하지 말고, AI가 달리는 환경(하네스)을 고쳐라." 이 프로젝트의 CLAUDE.md 계층, 원칙 관리팀, 진화팀, MCP 안전장치가 모두 하네스의 구성요소입니다.

---

## Q2. 서버 멱등성 — 죽였다 켜도 맥락이 끊기지 않는 구조

### 문제: 서버가 24시간 떠있을 수 없다

개인 프로젝트에서 서버를 항상 켜둘 수는 없습니다. 3일간 서버가 꺼져있었다면, 그 3일치 데이터가 빠져서 시장 맥락이 끊깁니다.

### 해법: "마지막 스냅샷" + "갭 필링" 아키텍처

```
서버 시작
    │
    ▼
┌─────────────────────────────────────┐
│  1. 스냅샷 체크                       │
│     last_snapshot.json 읽기           │
│     → last_run: "2026-04-11 08:30"   │
│     → 현재: "2026-04-14 08:30"       │
│     → 갭: 3일                         │
└────────────┬────────────────────────┘
             ▼
┌─────────────────────────────────────┐
│  2. 갭 필링 (Gap Filling)             │
│     빠진 날짜 목록 계산:               │
│     [2026-04-11, 04-12, 04-13]       │
│                                       │
│     각 날짜별로:                       │
│     ├── KIS API: 일봉 데이터 소급 조회  │
│     ├── yfinance: 해외 지수 소급 조회   │
│     ├── FRED: 경제 지표 소급 조회       │
│     └── DB에 빠진 날짜 데이터 적재      │
└────────────┬────────────────────────┘
             ▼
┌─────────────────────────────────────┐
│  3. 소급 분석 (Retroactive Analysis)  │
│     빠진 날짜들에 대해:                │
│     ├── 매크로 상태 판단 재계산         │
│     ├── 기술적 지표 재계산              │
│     ├── 수급 동향 재분석               │
│     └── daily_summary 재생성          │
└────────────┬────────────────────────┘
             ▼
┌─────────────────────────────────────┐
│  4. 맥락 연속성 복원                   │
│     최근 30일 데이터 기반              │
│     팀별 CLAUDE.md 컨텍스트 갱신       │
│     → "4/11: 조정장 진입,              │
│        4/12: VIX 급등,                │
│        4/13: 반등 시도"               │
│     경제적 맥락이 끊기지 않음!          │
└────────────┬────────────────────────┘
             ▼
┌─────────────────────────────────────┐
│  5. 오늘자 정상 분석 실행               │
│     /daily-macro (오늘 실시간)         │
│     스냅샷 업데이트: "2026-04-14"      │
└─────────────────────────────────────┘
```

### 구현 핵심 코드 개념

```python
# scripts/startup_reconciler.py — 서버 시작 시 자동 실행

import json
from datetime import date, timedelta
from pathlib import Path

SNAPSHOT_PATH = Path("data/last_snapshot.json")

def get_missing_dates() -> list[date]:
    """마지막 실행일 이후 빠진 날짜 목록 반환"""
    if not SNAPSHOT_PATH.exists():
        # 최초 실행: 최근 30일 소급
        return [date.today() - timedelta(days=i) for i in range(30, 0, -1)]
    
    snapshot = json.loads(SNAPSHOT_PATH.read_text())
    last_run = date.fromisoformat(snapshot["last_run_date"])
    today = date.today()
    
    missing = []
    current = last_run + timedelta(days=1)
    while current <= today:
        if is_trading_day(current):  # 주말/공휴일 제외
            missing.append(current)
        current += timedelta(days=1)
    
    return missing

def fill_gaps(missing_dates: list[date]):
    """빠진 날짜의 데이터를 소급 수집 및 분석"""
    for d in missing_dates:
        # KIS API는 과거 데이터 소급 조회 지원
        macro_data = kis_api.get_daily_macro(d)
        chart_data = kis_api.get_daily_charts(d, watchlist)
        supply_data = kis_api.get_investor_flow(d)
        
        # DB에 저장
        db.insert_daily_macro(d, macro_data)
        db.insert_daily_charts(d, chart_data)
        db.insert_supply_demand(d, supply_data)
        
        # 해당 날짜 분석 실행
        run_macro_analysis(d)
        run_technical_analysis(d)
        generate_daily_summary(d)
    
    # 스냅샷 업데이트
    SNAPSHOT_PATH.write_text(json.dumps({
        "last_run_date": date.today().isoformat(),
        "last_run_time": datetime.now().isoformat(),
        "gap_filled_dates": [d.isoformat() for d in missing_dates]
    }))

# 서버 시작 시 자동 호출
if __name__ == "__main__":
    missing = get_missing_dates()
    if missing:
        print(f"🔄 {len(missing)}일치 데이터 소급 수집 중...")
        fill_gaps(missing)
        print("✅ 갭 필링 완료. 맥락 연속성 복원됨.")
    else:
        print("✅ 데이터 최신 상태. 갭 없음.")
```

### 멱등성 보장 규칙

```markdown
# CLAUDE.md에 추가

## 멱등성 원칙
- 같은 날짜에 대해 분석을 두 번 돌려도 결과가 동일해야 한다
- DB INSERT 시 ON CONFLICT REPLACE 사용 (중복 입력 안전)
- 스냅샷(last_snapshot.json)은 항상 마지막 성공 시점만 기록
- 갭 필링 중 실패하면, 성공한 날짜까지만 스냅샷 업데이트
- 서버가 갭 필링 도중 꺼져도, 다음 시작 시 남은 갭부터 이어서 처리
```

### `.claude/commands/startup.md` — 시작 커맨드

```markdown
서버 시작 루틴을 실행합니다:

1. scripts/startup_reconciler.py를 실행하여 갭 필링
2. 갭 필링 완료 후 /daily-macro 실행 (오늘자)
3. 팀별 CLAUDE.md에 최근 30일 요약 컨텍스트 갱신
4. 관심종목 차트 데이터 리프레시
5. 시스템 상태 요약 출력
```

---

## Q3 & Q4. 토큰 소비 전략 + Feature별 점진적 완성 플랜

### 현실 인식: 이 시스템을 한번에 만들 수 없다

이 시스템의 예상 규모:

```
팀 8개 × 모듈 평균 3~5개 = 약 30~40개 모듈
MCP 서버 3~4개
웹앱 페이지 5~6개
총 예상 코드: 15,000 ~ 30,000줄 (테스트 포함)
```

Claude Code로 한 번에 만들려고 하면:
- 토큰 폭발 (세션당 컨텍스트 누적 → 비효율)
- 앞서 만든 코드를 뒤에서 망가뜨리는 사이드 이펙트
- 전체 정합성 검증 불가능
- 개발자가 시스템을 이해할 수 없게 됨

### 해법: "한 피처, 한 세션, 한 검증" 원칙

```
┌─────────────────────────────────────────────────┐
│         하나의 Feature 개발 사이클                  │
│                                                   │
│  1. /spec-interview → 스펙 생성     (세션 1)       │
│  2. 구현 지시 → 코드 생성           (세션 2)       │
│  3. 데모 + 눈으로 확인              (개발자)       │
│  4. 테스트 작성 + 통과 확인          (세션 3)       │
│  5. 기존 기능 회귀 테스트            (세션 3)       │
│  6. Git 커밋 + 스냅샷               (개발자)       │
│  ────────── Feature 완성선 ──────────             │
│  7. 다음 Feature로 이동                            │
└─────────────────────────────────────────────────┘

※ 핵심: 세션을 짧게 끊고, Feature마다 확인한다.
  긴 세션 = 토큰 낭비 + 환각 증가 + 사이드이펙트 증가
```

### Feature 분해 & 우선순위 맵

**규칙**: 각 Feature는 독립적으로 동작을 확인할 수 있어야 합니다.

```
═══════════════════════════════════════════════════════════
 WAVE 1: 기반 인프라 (이것 없으면 아무것도 안 됨)
═══════════════════════════════════════════════════════════

 F01 ★필수  프로젝트 스캐폴딩 + 루트 CLAUDE.md
            예상: 세션 1회 / 토큰: 소
            검증: 폴더 구조 존재, CLAUDE.md 읽기

 F02 ★필수  SQLite DB 스키마 생성 + 초기화 스크립트
            예상: 세션 1회 / 토큰: 소
            검증: 테이블 생성 확인, 샘플 INSERT/SELECT

 F03 ★필수  KIS API MCP 서버 — 인증(토큰 발급/갱신)
            예상: 세션 2~3회 / 토큰: 중
            검증: 토큰 발급 성공, 만료 시 자동 갱신
            ※ 실제 KIS API 호출 테스트 (모의투자)

 F04 ★필수  KIS API MCP 서버 — 국내 시세 조회
            예상: 세션 1~2회 / 토큰: 중
            검증: 삼성전자(005930) 현재가 조회 성공

 F05 ★필수  갭 필링 엔진 (startup_reconciler)
            예상: 세션 2회 / 토큰: 중
            검증: 3일 갭 시뮬레이션 → 소급 데이터 DB 적재 확인

────────── WAVE 1 완료 후 통합 테스트 ──────────
  "서버 시작 → KIS 인증 → 시세 조회 → DB 저장"
  이 파이프라인이 Mac과 Windows 양쪽에서 동작하는지 확인
═══════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════
 WAVE 2: 매크로 분석팀 (첫 번째 Spec Agent 완성)
═══════════════════════════════════════════════════════════

 F06 ★필수  KIS API — 해외 지수/환율 조회 (DXY, S&P500)
            예상: 세션 1~2회 / 토큰: 중
            검증: 해외 지수 데이터 조회 + DB 저장

 F07 ★필수  Global Data MCP — FRED API 연동 (금리)
            예상: 세션 2회 / 토큰: 중
            검증: 미국 10년물 금리 조회

 F08 ★필수  매크로 분석 엔진 — 시장 상태 판단
            예상: 세션 2~3회 / 토큰: 중~대
            검증: mock 데이터 → "상승장/조정장/하락장" + 신뢰도 출력

 F09 ★필수  /daily-macro 커맨드 — E2E 일일 분석
            예상: 세션 1~2회 / 토큰: 중
            검증: 커맨드 실행 → DB 저장 + daily-summary 생성

 F10 옵셔널 뉴스 크롤러 (매크로 관련 헤드라인)
            예상: 세션 2회 / 토큰: 중

────────── WAVE 2 완료 후 통합 테스트 ──────────
  /daily-macro 실행 → 실제 KIS+FRED 데이터 → 시장 판단 → 리포트
  이 시점에서 "매일 아침 실행하면 쓸모 있는" 최소 기능 완성
═══════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════
 WAVE 3: 기술적 분석 + 수급 (분석 역량 확장)
═══════════════════════════════════════════════════════════

 F11 ★필수  KIS API — 일봉/분봉 차트 데이터 조회
            예상: 세션 1~2회 / 토큰: 중

 F12 ★필수  기술적 지표 계산 엔진 (pandas-ta)
            예상: 세션 2~3회 / 토큰: 중~대
            검증: RSI, MACD, 볼린저밴드 계산 정확성

 F13 ★필수  KIS API — 거래량 상위 + 투자자별 매매동향
            예상: 세션 1~2회 / 토큰: 중

 F14 ★필수  관심종목 매니저 (watchlist CRUD + 주기적 리프레시)
            예상: 세션 2회 / 토큰: 중
            검증: /add-watchlist NVDA → DB 저장 → 차트 데이터 자동 수집

 F15 옵셔널 엘리엇 파동 / 차트 패턴 감지
            예상: 세션 3~4회 / 토큰: 대

────────── WAVE 3 완료 후 통합 테스트 ──────────
  매크로 판단 + 개별 종목 기술적 분석 + 수급 = 의미 있는 분석 조합
═══════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════
 WAVE 4: 원칙 + 계좌 + 오케스트레이터 (판단 체계)
═══════════════════════════════════════════════════════════

 F16 ★필수  원칙 관리팀 — 투자 7계명 체커
            예상: 세션 1~2회 / 토큰: 중
            검증: "총 비중 80% 초과" 시나리오 → 경고 출력

 F17 ★필수  계좌관리팀 — KIS 잔고 조회 + 리스크 계산
            예상: 세션 2~3회 / 토큰: 중
            검증: MDD, 샤프지수 계산 정확성

 F18 ★필수  오케스트레이터 — 팀 결과 종합 + 전략 라우팅
            예상: 세션 3~4회 / 토큰: 대
            검증: 단타/스윙/자산 3가지 전략에 각각 다른 판단 출력

 F19 ★필수  /generate-report — 종합 리포트 생성
            예상: 세션 2회 / 토큰: 중

 F20 옵셔널 FOMO/공포 감지기 (emotion-guard)
            예상: 세션 2회 / 토큰: 중

────────── WAVE 4 완료 후 통합 테스트 ──────────
  전체 파이프라인: 데이터수집 → 분석 → 판단 → 리포트
  ★ 여기까지가 "CLI 기반 투자 자문 비서"의 완성형
═══════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════
 WAVE 5: 유틸 + 진화 + 알림 (운용 품질)
═══════════════════════════════════════════════════════════

 F21 ★필수  Telegram 알림 연동
            예상: 세션 1~2회 / 토큰: 소~중

 F22 ★필수  메모리 리로더 (팀별 CLAUDE.md 자동 갱신)
            예상: 세션 2회 / 토큰: 중

 F23 ★필수  /evolve-review + /spec-interview 커맨드
            예상: 세션 2회 / 토큰: 중

 F24 옵셔널 유튜브 자막 추출 + 지식베이스 축적
            예상: 세션 2~3회 / 토큰: 중

 F25 옵셔널 백테스트 엔진 (/backtest)
            예상: 세션 3~4회 / 토큰: 대

═══════════════════════════════════════════════════════════

═══════════════════════════════════════════════════════════
 WAVE 6: 웹앱 (시각화 + 모바일)
═══════════════════════════════════════════════════════════

 F26 ★필수  Next.js 프로젝트 세팅 + API 라우트
            예상: 세션 2회 / 토큰: 중

 F27 ★필수  대시보드 메인 화면 (시장 상태 + 요약)
            예상: 세션 3~4회 / 토큰: 대

 F28 ★필수  관심종목 뷰 (TradingView 차트 위젯)
            예상: 세션 2~3회 / 토큰: 중~대

 F29 ★필수  포트폴리오 뷰 (계좌 현황 + 리스크)
            예상: 세션 2~3회 / 토큰: 중~대

 F30 옵셔널 모바일 반응형 최적화
 F31 옵셔널 리포트 히스토리 뷰
 F32 옵셔널 마케팅/광고 페이지

═══════════════════════════════════════════════════════════
```

### 토큰 절약 전략

| 전략 | 설명 | 절약 효과 |
|------|------|----------|
| **세션 분리** | Feature 하나 끝나면 세션 종료 → 새 세션 시작. 누적 컨텍스트 방지 | 30~50% |
| **Sonnet 우선** | 일반 코딩은 Sonnet 4.6, 복잡한 아키텍처 설계만 Opus 4.6 | 40~60% |
| **`.claudeignore`** | 불필요한 파일을 컨텍스트에서 제외 (node_modules, data/*.sqlite 등) | 20~30% |
| **CLAUDE.md 간결화** | 팀별 CLAUDE.md는 핵심만. 상세는 별도 파일 참조 경로로 | 15~25% |
| **스펙 먼저** | 코드 생성 전 스펙을 명확히 → 재작업 횟수 감소 | 30~40% |
| **점진적 개발** | Wave별로 끊어서 개발 → 한번에 전체 만들기 방지 | 50~70% |

### Feature 완성 검증 체크리스트 (유닛 TC보다 높은 수준)

각 Feature가 완성되면 이 체크리스트로 확인합니다:

```markdown
# Feature 완성 체크리스트

## 1. 동작 확인 (눈으로)
- [ ] 해당 기능을 직접 실행하여 예상 출력이 나오는가?
- [ ] Mac에서 실행 확인
- [ ] Windows에서 실행 확인 (크로스 플랫폼)

## 2. 데이터 확인
- [ ] DB에 데이터가 올바르게 저장되었는가? (SQLite 직접 열어서 확인)
- [ ] 중복 실행해도 데이터가 꼬이지 않는가? (멱등성)

## 3. 통합 확인
- [ ] 이전 Wave의 기능이 여전히 동작하는가? (회귀)
- [ ] 이 Feature의 출력을 다른 팀이 사용할 수 있는가?

## 4. 하네스 확인  
- [ ] 해당 팀의 CLAUDE.md가 업데이트되었는가?
- [ ] docs/changelog.md에 기록되었는가?
- [ ] Git 커밋 + 태그 (예: v0.2.0-wave2-complete)

## 5. 스냅샷
- [ ] 이 시점의 동작하는 코드가 Git에 안전하게 저장되었는가?
```

---

## Q5. 프로젝트 규모 & Claude Max 플랜으로 충분한가?

### 규모 추정

```
총 Feature 수:         ~25개 (필수) + ~7개 (옵셔널) = 32개
예상 총 코드량:         15,000 ~ 30,000줄
예상 총 세션 수:        50 ~ 80 세션
예상 개발 기간:         6 ~ 12주 (파트타임 기준)
```

### 플랜 비교 및 추천

| 플랜 | 월 비용 | 5시간 윈도우 | 이 프로젝트에서 |
|------|--------|------------|----------------|
| **Pro** | $20 | ~44,000 토큰 | Wave 1~2 정도 가능. Feature가 복잡해지면 자주 한계 도달 |
| **Max 5x** | $100 | ~88,000 토큰 | **대부분의 개발 커버 가능**. Wave별로 끊어 작업하면 충분 |
| **Max 20x** | $200 | ~220,000 토큰 | 여유 있음. 웹앱 등 대규모 코드 생성 시 안정적 |

### 추천 전략: 단계별 플랜 업그레이드

```
Wave 1~2 (인프라 + 매크로):  Pro ($20) 로 시작
  → 이 단계는 모듈이 작고, 스펙이 명확해서 Pro로 충분
  → 토큰 소비 패턴을 파악하는 기간

Wave 3~4 (분석 확장 + 오케스트레이터):  Max 5x ($100) 로 업그레이드
  → 모듈이 복잡해지고, 팀 간 통합 로직이 등장
  → 한 세션에서 여러 파일을 다뤄야 하므로 컨텍스트 소비 증가

Wave 5~6 (웹앱 + 진화):  Max 5x 유지 또는 필요시 Max 20x
  → 웹앱은 코드량이 많지만, UI 컴포넌트는 독립적이라 세션 분리 용이
  → 20x는 "하루 종일 웹앱을 만드는" 집중 작업일에만 필요
```

### 토큰 사용량 현실적 추정

```
Feature 1개 평균:
  /spec-interview     →  ~5,000 토큰 (면담)
  구현 지시 + 코드 생성 → ~15,000 ~ 40,000 토큰 (복잡도에 따라)
  테스트 작성          →  ~5,000 토큰
  문서화 업데이트       →  ~3,000 토큰
  ─────────────────────────────────
  Feature 1개 합계:    ~28,000 ~ 53,000 토큰

Pro (44K/5시간):     하루에 Feature 1개 (여유 없음)
Max 5x (88K/5시간):  하루에 Feature 1~2개 (여유 있음)  ← 추천
Max 20x (220K/5시간): 하루에 Feature 3~4개 (충분)
```

### Claude Code 토큰 절약 핵심 팁

```markdown
# CLAUDE.md 루트에 추가 — Claude Code 운용 규칙

## 세션 관리 원칙
1. 하나의 Feature = 하나의 세션. 끝나면 세션 종료.
2. 새 세션 시작 시 해당 팀의 CLAUDE.md만 참조하게 유도.
3. 전체 프로젝트를 한번에 파악하려 하지 말 것.
   → "teams/macro-analysis/ 폴더만 봐줘" 식으로 범위 한정.

## 모델 선택 규칙
- 일반 코딩, 버그 수정, 테스트 작성: Sonnet 4.6 (기본)
- 아키텍처 설계, 팀 간 통합 로직, 복잡한 판단: Opus 4.6
- 문서 작성, 리팩토링: Sonnet 4.6

## .claudeignore (토큰 절약)
node_modules/
data/db/*.sqlite
data/backups/
*.pyc
__pycache__/
.next/
```

### 결론

**Max 5x ($100/월)로 시작하되, Wave별로 끊어서 점진적으로 개발하면 충분합니다.**

Pro로 시작해서 한계를 느끼면 업그레이드하는 것도 좋은 전략이고, 최근 Anthropic이 도입한 "Extra Usage" 기능으로 Pro 플랜에서 한도를 넘으면 API 요금으로 추가 사용하는 하이브리드도 가능합니다.

핵심은 플랜이 아니라 **"한 피처, 한 세션, 한 검증"** 원칙을 지키는 것입니다. 이 원칙을 지키면 Pro로도 충분히 진행할 수 있고, 안 지키면 Max 20x도 부족할 수 있습니다.