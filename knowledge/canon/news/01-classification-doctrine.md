---
canon_id: news.classification_doctrine
analyst: news_curator
title: 뉴스 분류 독트린 — 카테고리·시간축·방향·강도·범위 + tone 집계 철학
source: docs/specs/NEWS-SOURCE-001-news-source.md (LB-MS3 SPEC frozen 2026-06-07, MS-B 구현)
distilled_at: 2026-06-07
---

# 뉴스 분류 독트린 (N1~N5)

> 뉴스큐레이터(news_curator) 가 개별 뉴스를 라벨링하고, 거친 종합(digest) 을 해석하는 기준.
> **개별 뉴스 판단 = LLM(정성적, 불가피) / 집계 = 결정론(카운트·톤). 정밀 점수(0~10)는 의도적 폐기**(N5).
> 라벨링은 **제목·본문에 실제로 담긴 내용으로만** — 학습 데이터의 추측을 더하지 않는다(환각 차단).

## 5 명제 구조

| 영역 | prefix | 역할 |
|------|--------|------|
| 카테고리 6분류 | **N1** | 무엇에 관한 뉴스인가 |
| 시간축 3단 | **N2** | 영향이 단발인가 지속인가 |
| 방향·강도·확신 | **N3** | 호재/악재 · 크기 · 확신도 |
| 영향 범위 귀속 | **N4** | 시장/섹터/종목 중 누구에게 |
| tone 집계 철학 | **N5** | 거친 5단 tilt — 정밀 점수 폐기 |

**시퀀스**: 분류(N1) → 시간성(N2) → 방향성(N3) → 귀속(N4) → 집계 철학(N5).

---

## N1 — 카테고리 6분류 ★★★★★

**한 줄**: 모든 뉴스는 6 카테고리 중 **하나**로 분류한다 (가장 지배적인 성격).

**형식**: `category ∈ {macro_policy, industry_trend, geopolitics, policy_political, corporate_events, market_sentiment}`

**왜**:
- `macro_policy` (거시·통화·재정): 금리·유동성·환율·중앙은행. *예: "Fed 25bp 인하"*.
- `industry_trend` (산업 흐름): 특정 산업의 수급·기술·사이클. *예: "HBM 공급 부족 심화"*.
- `geopolitics` (지정학): 전쟁·제재·공급망 차단. *예: "호르무즈 해협 긴장"*.
- `policy_political` (정치·정책): 선거·규제·입법. *예: "반도체 보조금 법안 통과"*.
- `corporate_events` (기업 이벤트): 실적·M&A·신제품. *예: "삼성전자 어닝 서프라이즈"*.
- `market_sentiment` (시장심리): 공포·탐욕·버블·조정 내러티브. *예: "AI 버블 우려 확산"* — 6/5형 시황 입력의 핵심, market_view 흡수에 최적.
- 경계 사례는 **시장에 작동하는 1차 채널**로 가른다 (예: "전쟁으로 유가 급등" 은 충격 채널이 지정학 → `geopolitics`).

---

## N2 — 시간축 3단 (단발 → 지속) ★★★★★

**한 줄**: 영향이 **얼마나 오래 가는가**로 가른다 — 가격에 이미 반영되고 끝날 일인가, 분기를 관통할 흐름인가.

**형식**: `time_axis ∈ {ephemeral_shock, short_theme, structural_trend}`

**왜**:
- `ephemeral_shock` (단발 충격, 당일~수일): 1회성 헤드라인. 반등·소멸이 빠름. *예: 단발 지정학 헤드라인, 일회성 루머*.
- `short_theme` (단기 테마, ~1~2주): 순환매·테마 플레이로 며칠~2주 끄는 모멘텀. *예: 특정 섹터 단기 수급 쏠림*.
- `structural_trend` (지속 흐름, 분기+): 사이클·정책·산업 구조를 바꾸는 흐름. *예: 금리 사이클 전환, AI capex 확대*.
- **카테고리×시간축 디폴트 경향** (절대 아님 — 본문이 우선): `geopolitics`·단발 루머 → 대개 `ephemeral_shock` / `macro_policy`·산업 사이클 → 대개 `structural_trend` / 테마 순환 → `short_theme`.
- 단발 충격이 **지속 흐름으로 승격**할 수 있다(가변): 일회성처럼 보여도 구조를 바꾸면 `structural_trend`. 판단은 *지속성의 근거가 본문에 있는가*.

---

## N3 — 방향·강도·확신 ★★★★☆

**한 줄**: 증시·해당 자산에 **호재(up)/중립(neutral)/악재(down)** + 영향 **크기(1~3)** + 분류 **확신도(0~100)**.

**형식**: `direction ∈ {up, neutral, down}`, `magnitude ∈ {1,2,3}`, `confidence ∈ [0,100]`

**왜**:
- `direction` = 자산 가격에 작동하는 방향. 양가적이면 *지배적* 채널로. 애매하면 `neutral`.
- `magnitude` = 시장 영향 크기. 1=주변부 / 2=의미 있음 / 3=시장을 움직임. 헤드라인 과장에 휘둘리지 말 것.
- `confidence` = 이 *분류*에 대한 확신 (뉴스의 진위가 아님). 제목만 있고 본문이 없으면 낮게.
- 셋은 **독립**: 강한 악재(down/3)도 확신이 낮을 수 있고(루머), 약한 호재(up/1)도 확신이 높을 수 있다(확정 사실).

---

## N4 — 영향 범위 귀속 ★★★★☆

**한 줄**: 이 뉴스가 **누구에게** 작동하는가 — 시장 전반인가, 한 섹터인가, 한 종목인가.

**형식**: `affected = {scope ∈ {market, sector, ticker}, refs: [...]}`

**왜**:
- `market`: 지수 전반 (금리·환율·거시 심리). `refs` 비움.
- `sector`: 한 산업 (반도체·2차전지·방산). `refs` = 섹터명.
- `ticker`: 특정 종목. `refs` = 종목코드.
- **귀속이 소비처를 가른다** (M7 — *종목 뉴스→종목 점수, 시장 뉴스→시장관*): `market` scope → market_view 내러티브 / `ticker`·`sector` scope → buy_score N축 촉매. 시장 전반 뉴스를 종목 점수에 섞지 않는다.
- 사람이 수동 입력한 `affected_refs`(ManualNewsSource) 는 LLM 추정보다 **우선** — 사람이 종목을 지정했으면 보존.

---

## N5 — tone 집계 철학: 거친 5단 tilt (정밀 점수 폐기) ★★★★★

**한 줄**: digest 의 tone·catalyst_tilt 는 **거친 5단 기울기**이지 정밀 점수가 아니다. 뉴스는 상황의존·비선형·희소충격이라 단일 0~10 점으로 누르는 건 정직하지 않다.

**형식**: `tone ∈ {bearish, lean_bearish, neutral, lean_bullish, bullish}` = `Σ(부호×magnitude×confidence) / Σweight` → [-1,1] → 5단 매핑(config 임계).

**왜**:
- **집계만 결정론, 판단은 LLM**(N3): 같은 라벨 묶음 → 같은 tone (백테스팅 재현). 그러나 라벨 자체는 정성적 LLM 판단.
- 정밀 점수를 안 만드는 이유 = *상황의존*(같은 금리 뉴스도 국면 따라 호·악재) · *퀄리티 편차*(헤드라인 ≠ 본질) · *비선형 상호작용*(뉴스끼리 증폭·상쇄) · *희소 충격*(꼬리 사건은 점수 분포 밖). → 프로젝트 원칙(결정론 점수 게이트키핑 금지, 원시 지표 LLM 주입, 점수는 advisory)과 동일.
- 해석자(news_curator)는 tone·tilt 를 **방향 감각**으로 쓰고, 결론은 raw 라벨·테마를 직접 읽어 내러티브로 — *점수를 매수/관망 게이트로 쓰지 않는다*.
- `catalyst_tilt{direction, strength∈{weak,mid,strong}}` 는 종목·섹터 scope 에서 buy_score N축에 **블렌드(advisory)** 되며, 원시 라벨을 동반한다 (MS-C).
