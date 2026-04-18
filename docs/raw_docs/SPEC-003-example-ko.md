# SPEC-003: 기술 지표 계산 엔진

## 목표
주어진 종목의 RSI, MACD, 볼린저밴드, 이동평균을 계산한다.
결과를 SQLite에 저장하고, 모든 지표를 한번에 반환하는 함수를 제공한다.

## 입력 함수
```python
def calculate_indicators(ticker: str, period_days: int = 60) -> dict | None:
    """
    KIS API MCP 서버에서 캔들 데이터를 가져와서
    기술 지표를 계산하고, DB에 저장하고, 결과 dict를 반환한다.
    API 실패 시 None 반환 (크래시 금지).
    """
```

## 출력 스키마
```python
{
    "ticker": "005930",
    "date": "2026-04-14",
    "close": 72300,
    "rsi_14": 58.3,
    "macd": {"value": 450, "signal": 380, "histogram": 70, "cross": "골든크로스"},
    "bollinger": {"upper": 74500, "middle": 72000, "lower": 69500, "position": "중간"},
    "ma": {"ma5": 72100, "ma20": 71500, "ma60": 70200},
    "volume_ratio": 1.3  # 20일 평균 대비 비율
}
```

## 구현 조건
- 라이브러리: pandas-ta (ta-lib 금지 — 크로스 플랫폼 문제)
- 데이터 소스: KIS API MCP → get_daily_chart(ticker, period_days)
- DB 테이블: technical_indicators — ON CONFLICT REPLACE로 INSERT
- 에러 처리: KIS API 실패 시 None 반환 + 에러 로그. 절대 크래시하지 않음.

## DB 스키마
```sql
CREATE TABLE IF NOT EXISTS technical_indicators (
    ticker TEXT NOT NULL,
    date TEXT NOT NULL,
    close REAL,
    rsi_14 REAL,
    macd_value REAL,
    macd_signal REAL,
    macd_histogram REAL,
    macd_cross TEXT,
    bb_upper REAL,
    bb_middle REAL,
    bb_lower REAL,
    ma5 REAL,
    ma20 REAL,
    ma60 REAL,
    volume_ratio REAL,
    updated_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (ticker, date)
);
```

## 테스트 케이스
1. 삼성전자 60일 mock 데이터 → RSI가 0~100 범위인지 확인
2. MACD 골든크로스 시나리오 → cross="골든크로스" 확인
3. 같은 날짜에 두 번 실행 → 중복 행 없음 확인 (멱등성)
4. KIS API 실패 상황 → None 반환, 크래시 없음 확인

## 파일 위치
- 구현: teams/technical-analysis/src/indicator-engine.py
- 테스트: teams/technical-analysis/tests/test_indicator_engine.py

## 의존성
- pandas-ta, pandas, sqlite3 (표준 라이브러리)
- MCP 서버: kis-api (실행 중이어야 함)

## 완료 기준
- [ ] 4개 테스트 케이스 전부 통과
- [ ] Mac에서 동작 확인
- [ ] Windows에서 동작 확인
- [ ] DB에 데이터 저장 확인 (sqlite3 CLI로 SELECT 실행)
