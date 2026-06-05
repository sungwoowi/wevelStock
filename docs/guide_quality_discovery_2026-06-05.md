# 가이드 품질 검증 — production-chat (provider=gemini)

_총 2개 질의 · 실 배포 경로(classify→route→format)_

---
## 질의: 단기로 빠르게 수익 낼 만한 종목 있어?

### 분류 (intent)
- scenario `5` · route `track_b` · 종목 `None` (None) · 확신도 0.90 · stage cache
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
_model=gemini-2.5-flash-lite · is_mock=False · err=None · $0.0006 · 3991ms_

> 지금은 선별해서 접근하는 게 좋아요
> 
> 추천 후보:
> - LG이노텍 (011070): 높은 상대강도와 건강한 과열도로 주도주 강도가 매우 높아요. 단기 급등에 따른 변동성 확대 가능성은 염두에 두세요.
> - 삼성전기 (009150): 견조한 상대강도와 양호한 과열도로 주도주 강세 흐름을 보여요. 시장 전반의 변동성에 영향을 받을 수 있어요.
> - SK하이닉스 (000660): 상대강도는 중간 수준이지만, 건강한 과열도를 유지하며 주도주로서의 잠재력이 있어요. 시장 방향성에 더 민감할 수 있어요.
> - LG전자 (066570): 양호한 상대강도 대비 과열도가 낮아 단기 급등에 따른 조정 위험이 있으니 신중한 접근이 필요해요.
> 
> KOSDAQ 시장에 매매 중단 킬 스위치가 발동되었고, 외국인 매도 전환 등 시장 전반의 위험 신호가 누적되고 있어 보수적으로 접근하는 것이 좋습니다.

---

## 질의: 지금 주도주 추천해줘

### 분류 (intent)
- scenario `5` · route `both` · 종목 `None` (None) · 확신도 0.80 · stage deterministic
- 호출 분석가: []

### 에이전트 7개 (route.error=None)
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
- `strategist` **track_a** ok
- `strategist` **track_b** ok

### 종합 가이드 (사용자가 보는 답변)
_model=gemini-2.5-flash-lite · is_mock=False · err=None · $0.0004 · 3311ms_

> 지금은 선별해서 접근하는 게 좋아요
> 
> 추천 후보:
> - 삼성전기 (009150): 시장 대비 강하고 추세가 건강해요. 다만, 과열 구간 진입 가능성이 있어 주의가 필요해요.
> - SK하이닉스 (000660): 시장 대비 강하고 추세가 안정적이에요.
> - LG전자 (066570): 시장 대비 강하지만, 단기 과열 위험이 있어 주의해야 해요.
> 
> 전반 보수적, 분할 접근

---

