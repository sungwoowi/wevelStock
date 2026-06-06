---
date: 2026-06-06
topic: MARKET-VIEW-SYNTHESIS-001 (LB-MS2) 시장관 종합 — 결정론 종합 + 순환매 결정론⨯Gemini 크로스체크 + 답변 1줄 prepend
status: completed
plan_file: C:\Users\HOME\.claude\plans\eager-snuggling-kay.md
---

# 2026-06-06 · 시장관 종합 (LB-MS2) 구현 + 라이브 검증

## 배경
`LEFT-BRAIN-COMPLETION-001` 다음 자식(LB-MS2). 왼쪽 뇌 채점표상 순환매(~40%)·시장타이밍(~50%)이 *종합 판단*으로 안 올라옴 — 재료(섹터 RS·regime·매크로)는 라이브인데 "돈이 A→B로 돈다 / 지금 들어갈 때냐"를 묶는 **종합자 한 겹이 비어 있음**. SPEC 면담 4결단(① 결정론 함수+기존 분석가 해석 ② 모든 답변 머리 1줄 prepend ③ 미장매크로 별 SPEC ④ 순환매=섹터 RS 변화) 후 구현. **핵심 판단**: 사용자 보강으로 순환매를 *결정론 단독(하루치 오해)·LLM 단독(환각)* 둘 다 피하려 **결정론 다일 후보 ⨯ LLM 크로스체크**(WAVE-ALPHA anchor 패턴 mirror)로 설계.

## 한 일
### SPEC + 거버넌스
- `docs/specs/MARKET-VIEW-SYNTHESIS-001-market-view-synthesis.md` — 신규 implementation SPEC(parent=LEFT-BRAIN). 면담 4결단 + SLOT 5 + 구현기록. status draft→verified
- `docs/specs/LEFT-BRAIN-COMPLETION-001-left-brain-completion.md` — 자식 상태판/마일스톤/채점표 LB-MS2 완료 반영 (순환매·타이밍 ~70%)

### M1 결정론 코어
- `collectors/market_view.py` — 신규. MarketView/Rotation dataclass, synthesize_market_view(결정론), entry_posture(regime+breadth+DD kill switch), build_rotation_stage1(다일 RS 변화, ticker 매칭), one_liner, build_market_view(DB-first), render/metadata, get_cached_one_liner, **ETF ticker→섹터명 라벨**
- `collectors/sector_rs.py` — persist_sector_rs / load_sector_rs_snapshot / load_prev_sector_rs(다일 윈도우) 추가
- `core/db/schema.sql` — v10 2테이블(sector_rs_snapshot, market_view_snapshot)
- `config/market_view.yaml` — 신규. rotation 윈도우/임계 + entry_posture 매트릭스 + cross_check(provider=gemini) + prepend 토글 + sector_labels(ticker→섹터명)

### M2 LLM 크로스체크 (검증 전용)
- `collectors/market_view.py` — cross_check_rotation_via_llm(LLM이 후보 **생성 X 검증만** = 환각 차단) + llm_call_cache type='market_rotation' 일1회 캐싱 + _apply_rotation_cross_check(agree +10/disagree −15, method=hybrid, agreement 노출). **provider=gemini 고정**(Anthropic 미결제)

### M3 배선
- `core/intent/formatter.py` — _market_view_prefix: 모든 답변 머리 시장관 1줄 prepend(DB 캐시 read, 비용 0)
- `core/inference/run_analyst.py` — reads_market_view 플래그 + _maybe_build_market_view_md hook(sync+stream) + metadata
- `core/knowledge/compose.py` — build_pipeline_prompt market_view_md 파라미터 + [3b] 블록
- `agents/analysts/market_state_analyzer/{manifest.yaml,persona.md}` — reads_market_view:true + 순환매·진입자세 해석 규칙(disagree 노출/none 추정금지) + Inputs [7] 항목

### 테스트 + 검증 도구 + 부채 정정
- `tests/test_market_view.py` — 신규 33 (결정론 매트릭스·rotation·DB round-trip·크로스체크 mock·캐싱 멱등·prepend·analyst hook·라벨)
- `tests/test_project_status.py` — **stale 테스트 구조화 정정**(transient status 하드코딩→실 SPEC 데이터 기준 거버넌스 불변식)
- `scripts/_market_view_probe.py` — 라이브 검증 프로브(서버 없이 실 데이터+실 Gemini)

## 검증 결과
- ✅ 회귀 **901 passed**(+33 신규, project_status stale 1 정정), validate **0 errors**
- ✅ **라이브**(실 KIS 데이터 + 실 Gemini flash-lite): regime=moderate_bull, 섹터 RS 15종 실측, 순환매 결정론 후보→**Gemini 크로스체크 agree**(신뢰도 60→70), one_liner "주도 금융 · 순환 바이오→금융"(ETF명 정제), 답변 머리 prepend 정상
- ✅ 모델 확정: `gemini-2.5-flash-lite` / provider `gemini` — Anthropic 호출 0
- ✅ 단계 지도: LEFT-BRAIN **2/4 (50%)**, MARKET-VIEW verified

## 다음에 이어서 할 작업 (우선순위)
1. **sector_rs_snapshot 일일 적재 cron 배선** — 순환매가 매일 누적·활성화되려면 장후 적재 필요(현재 첫 호출 자가적재만). `refresh_market_macro_all` 옆에 build_market_view 적재 추가. dev cron 미작동 이슈와 함께
2. **LB-MS3 뉴스부 NEWS-SOURCE-001 SPEC 착수** (가장 무거움) — 6/5형 "버블/조정" 내러티브 + buy_score N 7/7축. LB-MS2 시장관에 먹일 재료. `/spec-interview`
3. **INFRA-US-MACRO-SNAPSHOT-001 (미장 매크로)** — entry_posture 미장 야간(SPX/NDX/VIX/DXY/US10Y) 축, MARKET-VIEW SLOT 흡수

## 커밋 상태
- 코드+테스트+SPEC = `feat/market-view-synthesis` 브랜치 (커밋 예정 → main FF → push, 사용자 요청)
