# 가이드 품질 검증 — production-chat (provider=gemini)

_총 8개 질의 · 실 배포 경로(classify→route→format)_

---
## 질의: 삼성전자 지금 사도 돼?

### 분류 (intent)
- scenario `2` · route `both` · 종목 `005930` (삼성전자) · 확신도 0.80 · stage deterministic
- 호출 분석가: []

### 에이전트 8개 (route.error=None)
- `analyst_prefetch` **stock_picker** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': 6.5, 'buyscore_failures': ['C(분기 EPS YoY) 중립 — EPS 5분기 미만/부재', 'N 뉴스부(신제품) 0시드 — 52주 신고가만 (SLOT: NEWS-SOURCE-001)'], 'buyscore_ticker_used': '005930', 'advisory_buy_score': 6.5}`
- `analyst_prefetch` **stock_analyst** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **market_state_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **principle_guardian** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **flow_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': 3.0, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **trader** ok
  - 점수: `{'advisory_t_score': 4.0, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `strategist` **track_a** ok
- `strategist` **track_b** ok

### 종합 가이드 (사용자가 보는 답변)
_model=gemini-2.5-flash-lite · is_mock=False · err=None · $0.0006 · 2452ms_

> 삼성전자 매수는 지금 보류하는 것이 좋겠습니다.
> 
> 근거:
> - **수급**: 외국인 매도세가 지속되고 있으며, KOSPI 시장의 전반적인 수급 환경이 좋지 않습니다.
> - **차트**: 월봉 추세는 유지되고 있으나, 주봉 가속도가 과열 구간에 진입했고 KOSDAQ 시장의 분산일이 많아 시장 전반의 불확실성이 높습니다.
> - **실적**: 연간 실적은 양호하나, 단기적인 매수 진입을 뒷받침할 만한 명확한 신호가 부족합니다.

---

## 질의: NAVER 지금 들어가도 될까?

### 분류 (intent)
- scenario `2` · route `both` · 종목 `035420` (NAVER) · 확신도 0.90 · stage deterministic
- 호출 분석가: []

### 에이전트 8개 (route.error=None)
- `analyst_prefetch` **stock_picker** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': 4.5, 'buyscore_failures': ['C(분기 EPS YoY) 중립 — EPS 5분기 미만/부재', 'N 뉴스부(신제품) 0시드 — 52주 신고가만 (SLOT: NEWS-SOURCE-001)'], 'buyscore_ticker_used': '035420', 'advisory_buy_score': 5.0}`
- `analyst_prefetch` **stock_analyst** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **market_state_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **principle_guardian** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **flow_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': 4.0, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **trader** ok
  - 점수: `{'advisory_t_score': 3.5, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `strategist` **track_a** ok
- `strategist` **track_b** ok

### 종합 가이드 (사용자가 보는 답변)
_model=gemini-2.5-flash-lite · is_mock=False · err=None · $0.0005 · 2687ms_

> ## NAVER 지금 들어가도 될까?
> 
> 지금은 NAVER에 신규 진입하기보다 관망하는 것이 좋겠습니다. KOSDAQ 시장의 약세 전환 신호와 함께 매매 중단 기준을 초과한 분배일이 발생했으며, 단기 진입에 필요한 명확한 신호가 부족합니다.
> 
> 근거:
> - **수급**: KOSPI 시장 전체 수급은 외국인 매도 흐름이며, NAVER 개별 종목의 정확한 수급 데이터는 부족합니다.
> - **차트**: 일봉과 월봉은 과열 상태이고 주봉은 추세가 이탈했으며, 이격도가 높아 단기 과열 구간입니다.
> - **실적**: 분기 및 연간 EPS 성장률이 낮고, ROE가 낮은 편이며, 신고가 대비 이격이 크지 않아 매력적인 진입 시점은 아닙니다.

---

## 질의: 삼성전자 들고 있는데 팔아야 해?

### 분류 (intent)
- scenario `1` · route `track_a` · 종목 `005930` (삼성전자) · 확신도 0.80 · stage deterministic
- 호출 분석가: []

### 에이전트 4개 (route.error=None)
- `analyst_prefetch` **stock_analyst** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **principle_guardian** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **flow_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': 3.0, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `strategist` **track_a** ok

### 종합 가이드 (사용자가 보는 답변)
_model=gemini-2.5-flash-lite · is_mock=False · err=None · $0.0004 · 2051ms_

> 삼성전자 보유는 현재로서는 유지하는 것이 좋겠으나, 매도 계획을 미리 세우고 신중하게 접근해야 합니다.
> 
> 근거:
> - **수급**: 외국인 매도세가 지속되고 개인 매수세가 강해지는 흐름은 주의가 필요합니다.
> - **차트**: 주봉 기준 가속계수가 상승 발산 시작 구간에 있어 추세 추종에 유리한 환경입니다.
> - **실적**: 현재 분석에서는 실적 관련 명확한 매도 신호는 포착되지 않았습니다.

---

## 질의: 삼성전자랑 SK하이닉스 중에 뭐가 나아?

### 분류 (intent)
- scenario `4` · route `analyst_direct` · 종목 `000660` (SK하이닉스) · 확신도 0.90 · stage llm
- 호출 분석가: ['stock_picker', 'market_state_analyzer']

### 에이전트 2개 (route.error=None)
- `analyst` **stock_picker** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': 7.5, 'buyscore_failures': ['C(분기 EPS YoY) 중립 — EPS 5분기 미만/부재', 'N 뉴스부(신제품) 0시드 — 52주 신고가만 (SLOT: NEWS-SOURCE-001)'], 'buyscore_ticker_used': '000660', 'advisory_buy_score': 6.5}`
- `analyst` **market_state_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`

### 종합 가이드 (사용자가 보는 답변)
_model=gemini-2.5-flash-lite · is_mock=False · err=None · $0.0004 · 2762ms_

> ## 사용자 발화
> 삼성전자랑 SK하이닉스 중에 뭐가 나아?
> 
> ## 분석가 raw 응답 (prefetch 동시 호출)
> 
> ### stock_picker
> 삼성전자와 SK하이닉스 중 어느 종목이 더 나은지 문의하셨습니다. 현재 제공된 데이터에 따르면 SK하이닉스에 대한 상세한 주도주 점수(주도주 점수)와 매수 점수(매수 점수) 입력 지표가 있으므로, 이를 바탕으로 SK하이닉스를 분석해 드리겠습니다. 삼성전자의 경우, 시장 스냅샷에서는 주도주로 언급되었으나 상세 점수 산출을 위한 개별 지표는 제공되지 않았습니다.
> 
> ### SK하이닉스 (000660) 분석
> 
> SK하이닉스는 현재 **주도주 점수 7.33**으로 **'리더(leader)'** 등급에 해당하며, **매수 점수 6.71**로 **'매수 후보(buy_candidate)'**에 해당합니다.
> 
> **1. 주도주 점수 (주도주 점수=7.33) 상세:**
> SK하이닉스의 주도주 점수는 세 가지 핵심 축을 바탕으로 산출됩니다.
> 
> *   **상대강도(상대강도): 8.0/10점**
>     *   60일간 KOSPI 대비 +182.3%의 높은 상대강도를 보이며, 종목 풀 내에서도 최상위권에 속합니다.
> *   **수급망 일치도(Supply Chain Alignment): 4.0/10점**
>     *   AI 반도체 섹터에 속하며, 해당 섹터의 상대강도(KODEX AI반도체핵심장비 섹터 상대강도 4.0)를 반영합니다.
> *   **정배열 위계(Alignment): 10.0/10점**
>     *   **월봉 종가가 7월선 위에 위치**하여 시대적 중장기 주도주로서의 구조를 갖추고 있습니다.
>     *   **주봉 역시 정배열(10MA > 20MA > 60MA)** 상태입니다.
>     *   **일봉은 4일선을 타고 상승하는 '초강세 주도주'**의 모습을 보이고 있습니다. 이는 `stock_selection canon`의 `momentum_leaders.ma_ride` 원칙에 따라, 가장 빠른 이평선인 4일선을 타고 오르는 종목이 단기적으로 가장 강한 주도주임을 의미합니다.
> 
> **2. 매수 점수 (매수 점수=6.71, CAN SLIM) 상세:**
> SK하이닉스의 매수 점수는 CAN SLIM 7축을 종합하여 산출됩니다.
> 
> *   **C (Current quarterly earnings): 5.0점** (분기 EPS YoY 지표 부재로 중립 처리)
> *   **A (Annual earnings): 10.0점** (연간 EPS YoY +112.5%로 매우 높은 성장세)
> *   **N (New): 9.0점** (52주 신고가 대비 -2.0% 이격으로 신고가에 근접한 강한 흐름)
> *   **S (Supply & demand): 2.0점** (수급 모멘텀 및 누적 지표가 다소 약함)
> *   **L (Leader or laggard): 7.5점** (강한 주도주로서의 면모를 보임)
> *   **I (Institutional sponsorship): 6.5점** (기관 비중이 긍정적인 수준)
> *   

---

## 질의: 지금 시장 어때?

### 분류 (intent)
- scenario `3` · route `analyst_direct` · 종목 `None` (None) · 확신도 0.90 · stage deterministic
- 호출 분석가: ['market_state_analyzer']

### 에이전트 1개 (route.error=None)
- `analyst` **market_state_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`

### 종합 가이드 (사용자가 보는 답변)
_model=gemini-2.5-flash-lite · is_mock=False · err=None · $0.0001 · 2705ms_

> 현재 시장은 코스피와 코스닥의 흐름이 다르고, 코스닥의 분배일 누적이 높아 보수적인 접근이 필요해요.
> 
> 근거:
> - [수급] 코스닥 시장의 분배일 누적이 매매 중단 임계치를 넘어서며 전반적인 시장에 대한 보수적인 접근이 요구됩니다.
> - [차트] 코스피와 코스닥 지수 모두 60개월선 위에 위치하고 있으나, 코스닥의 추세는 불확실합니다.
> - [실적] 실적 관련 정보는 부족합니다.

---

## 질의: 단기로 빠르게 수익 낼 만한 종목 있어?

### 분류 (intent)
- scenario `5` · route `track_b` · 종목 `None` (None) · 확신도 0.90 · stage llm
- 호출 분석가: []

### 에이전트 6개 (route.error=None)
- `analyst_prefetch` **stock_picker** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': ['target_ticker_absent'], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **stock_analyst** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **market_state_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **flow_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': 4.0, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **trader** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `strategist` **track_b** ok

### 종합 가이드 (사용자가 보는 답변)
_model=gemini-2.5-flash-lite · is_mock=False · err=None · $0.0004 · 2259ms_

> 지금은 신규 종목 진입을 보류하고 관망하는 것이 좋겠습니다.
> 
> 근거:
> - [수급] 코스닥 시장의 분배일이 8건으로 매매 중단 임계치를 초과하여 시장 전반의 하락 압력이 강합니다.
> - [차트] 특정 종목에 대한 실시간 데이터가 없어 매수 점수, 타점 점수, 수급 점수 등 진입에 필요한 지표들을 산출할 수 없습니다.
> - [실적] 현재 시장 국면이 혼조세이며, 특히 코스닥 시장의 불안정한 흐름으로 인해 신규 진입에 신중해야 합니다.

---

## 질의: 주식 처음인데 뭐부터 봐야 해?

### 분류 (intent)
- scenario `2` · route `both` · 종목 `None` (None) · 확신도 0.70 · stage llm
- 호출 분석가: []
- ⚠ manual_fallback_required (확신도 낮음/종목 미매핑)

### 에이전트 8개 (route.error=None)
- `analyst_prefetch` **stock_picker** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': ['target_ticker_absent'], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **stock_analyst** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **market_state_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **principle_guardian** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **flow_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': 4.0, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `analyst_prefetch` **trader** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`
- `strategist` **track_a** ok
- `strategist` **track_b** ok

### 종합 가이드 (사용자가 보는 답변)
_model=gemini-2.5-flash-lite · is_mock=False · err=None · $0.0007 · 3544ms_

> 주식 투자를 처음 시작하신다면, 특정 종목 분석보다는 **시장 전체의 큰 흐름과 자신만의 투자 원칙을 세우는 것**이 가장 중요합니다. 지금 당장 매매에 나서기보다는, 시장을 관찰하며 거시경제, 투자 철학, 시대의 흐름을 이해하는 시간을 가지시는 것을 권해 드립니다.
> 
> 근거:
> - **수급**: 현재 KOSPI 시장은 외국인과 기관의 매도세가 나타나고 있으며, 시장 전반의 수급 점수는 4.0점으로 혼조세를 보입니다.
> - **차트**: KOSPI 지수는 36월선과 60월선 위에 있으며 이동평균선 기울기가 상승 추세를 나타내 긍정적이나, KOSDAQ은 하락 추세로 시장 내 차별화가 존재합니다.
> - **실적**: 특정 종목에 대한 데이터가 없어 실적 분석은 불가하나, 투자 시작 단계에서는 개별 종목보다는 시대의 흐름을 주도하는 산업군에 주목하는 것이 좋습니다.

---

## 질의: 지금 환율이랑 금리 상황 어때?

### 분류 (intent)
- scenario `3` · route `analyst_direct` · 종목 `None` (None) · 확신도 0.90 · stage llm
- 호출 분석가: ['market_state_analyzer']

### 에이전트 1개 (route.error=None)
- `analyst` **market_state_analyzer** ok
  - 점수: `{'advisory_t_score': None, 'advisory_f_score': None, 'advisory_s_score': None, 'buyscore_failures': [], 'buyscore_ticker_used': None, 'advisory_buy_score': None}`

### 종합 가이드 (사용자가 보는 답변)
_model=gemini-2.5-flash-lite · is_mock=False · err=None · $0.0001 · 1863ms_

> 현재 원/달러 환율은 상승세를 보이며 1,529원대를 기록하고 있고, 미국 10년물 국채금리 역시 상승하여 4.49% 수준입니다.
> 
> 근거:
> - [수급] 정보 부족
> - [차트] 정보 부족
> - [실적] 정보 부족

---

# 종합 평가 (2026-06-04, Claude)

## 잘 되는 것 ✅
- **경로·정직성**: 8/8 `is_mock=False`, 실 배포 경로(gemini flash-lite) 작동. 비용 $0.0001~0.0007/질의로 매우 저렴.
- **분류 정확도**: 종목 매핑(삼성/NAVER/하이닉스)·트랙 라우팅(매수=both / 매도=track_a / 시장=analyst_direct / 단타=track_b) 대체로 정확.
- **변별력**: 삼성 주도주점수 6.5 vs NAVER 4.5 vs 하이닉스 7.5 — 강·약 종목 정확히 구분. 가이드 톤도 차등.
- **이번 세션 배선이 실제 LLM 응답에 살아있음**: 하이닉스에서 **A축 연간 EPS +112.5%→10점** + **일봉 4일선 초강세 MA-ride 인용**(canon momentum_leaders) 둘 다 등장. 오늘 한 작업이 production에 반영됨 실증.
- **자연어·코드라벨 0**: 대부분 질의가 "결론 1줄 + 수급/차트/실적 3근거" 친화 포맷(analyst_direct 제외).

## 핵심 약점 (우선순위) ⚠
1. **종목 발굴 경로 미작동** (단타 추천 #6): "종목 있어?"에 `target_ticker_absent`로 후보 0개. 스크리닝 풀→후보 선정이 production 라우팅에 안 붙음. **30시나리오 중 "주도주/단타 추천"이 핵심인데 종목을 못 고름 = 가장 큰 기능 공백.**
2. **비교 경로 결함** (#4 삼성 vs 하이닉스): (a) 양 종목 중 **하나만 분석**(삼성 지표 미제공으로 스킵) (b) `analyst_direct`가 formatter 안 거쳐 **raw 응답+코드라벨(buy_candidate/leader)+응답 잘림** 그대로 노출. 비교 질의=양쪽 prefetch+종합 필요.
3. **3요소 템플릿 과적합**: 시장·거시·온보딩 질의에도 "[실적] 정보 부족" 기계적으로 붙어 어색·부실해 보임(환율 질의에 수급/차트/실적 3줄 전부 "정보 부족"). formatter가 질의 유형별로 근거 축 가변 필요.
4. **(배경) transient KIS fetch 실패 + 점수 None 산재**: 첫 삼성 run chart/supply fetch 실패(KIS "Server disconnected"=rate limiter 부채). 점수가 에이전트별 흩어져 None 다발 → "데이터 부족" 가이드를 일부 유발(진짜 공백 아님).

## 한 줄 결론
**플럼빙·정직성·변별력·이번 배선 반영은 합격. 본질 기능 2개가 비었다 — ① 종목 추천(발굴) ② 종목 비교.** 이 둘이 사용자 핵심 시나리오인데 production 경로에서 작동 안 함. formatter 근거축 가변(#3)은 그 다음.

