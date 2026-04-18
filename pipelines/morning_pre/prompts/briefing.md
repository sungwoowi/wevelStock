07:00 장전 브리핑을 생성해주세요.

## 간밤 미국장
{overnight_us}

## 거시 지표
{macro}

## 야간 코스피200 선물
{night_futures}

## 뉴스 제목 목록 (본문 없음 — 제목으로만 판단)
{news}

## 보유 / 관심 종목
{positions}

## 7계명 체크 결과
{principles}

---

## 응답 형식 (반드시 준수)

다음 키를 **최상위**에 가진 단일 JSON 객체로만 응답하세요. 마크다운 코드블록 없이 JSON만.

```json
{{
  "verdict": "positive" | "neutral" | "caution" | "alert",
  "confidence": 0-100,
  "scenario": {{
    "expected_open": "gap_up_big" | "gap_up_small" | "flat" | "gap_down_small" | "gap_down_big",
    "bias": "bullish" | "neutral_positive" | "neutral" | "neutral_negative" | "bearish",
    "confidence": 0-100,
    "narrative": "단기(1~2주) 관점과 장기(3개월+) 관점을 분리하여 2~4문단"
  }},
  "news_impact": [
    {{
      "url": "<입력 받은 뉴스의 url 그대로>",
      "impact_direction": "bullish" | "bearish" | "neutral",
      "impact_magnitude": 1-3,
      "impact_note": "한 문장 영향 설명"
    }}
  ],
  "sector_watch": {{
    "bullish": ["섹터명", ...],
    "bearish": ["섹터명", ...]
  }},
  "positions_advice": [
    {{
      "ticker": "005930",
      "name": "삼성전자",
      "verdict": "HOLD" | "BUY_ADD" | "SELL_PART" | "SELL_ALL",
      "reason": "구체적 이유 (수치 포함)"
    }}
  ],
  "new_candidates": [
    {{
      "sector": "반도체장비",
      "ticker": "240810",
      "name": "원익IPS",
      "reason": "이유"
    }}
  ],
  "reasons": [
    "핵심 근거 1 (수치 포함)",
    "핵심 근거 2",
    "핵심 근거 3 (최소 3개)"
  ],
  "narrative": "scenario.narrative 와 별도로, 전체 브리핑 요약 2~3문단"
}}
```

## 작성 가이드
1. `verdict` 는 오늘 시장 전반의 리스크/기회 평가 (positive/neutral/caution/alert 중 하나).
2. `scenario.expected_open` 은 야간 선물 변동폭 기준으로 선택 (±0.3% 이하 flat, ±1% 이하 small, 초과 big).
3. `news_impact` 는 **입력받은 모든 뉴스**에 대해 url을 그대로 복사하여 평가. 모든 뉴스를 포함.
4. `positions_advice` 는 입력 받은 보유/관심 종목 각각에 대해 하나씩.
5. `new_candidates` 는 오늘 시장 상황에 맞는 **새로운** 매수 후보 (최대 3개). 이미 보유 중인 종목 제외.
6. `reasons` 는 최소 3개 — "KOSPI200 야간선물 +0.6%, SOX +2.1%, 원달러 -0.3%" 처럼 **수치 포함**.
7. 모든 판단에 "어제 대비 달라진 점" 을 언급 (연속성).
