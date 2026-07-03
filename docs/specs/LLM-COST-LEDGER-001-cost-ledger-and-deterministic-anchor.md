---
spec_id: LLM-COST-LEDGER-001
title: LLM 비용 원장 + 결정론 anchor 기본화 (Gemini 지출 폭발 대응 — 가시성 우선)
team: shared
type: feature
level: implementation
status: verified
parent: OPS-CLOUD-001
generates:
  - core/llm/ledger.py                       # 원장 writer + cost_summary 집계
  - server/api/ops.py                        # GET /api/ops/llm-cost (운영자 조회)
  - webapp/src/app/ops/llm-cost/page.tsx     # 운영자 화면 (벤더·모델·질의영역·일자별)
modifies:
  - core/db/schema.sql                       # llm_cost_ledger 테이블 + 인덱스
  - core/llm/client.py                       # call_llm 중앙 기록(call_type/target) + _record_ledger
  - core/config/schema.py                    # AlphaConfig(anchor_llm_enabled) + RuntimeConfig.alpha
  - config/defaults.yaml                     # alpha.anchor_llm_enabled=false
  - collectors/anchors.py                    # _deterministic_anchors 기본화 + config 게이트
  - collectors/theme_match.py                # call_type=theme_match 라벨
  - collectors/news_source.py                # call_type=news_classify 라벨
  - collectors/market_view.py                # call_type=market_view 라벨
  - core/inference/run_analyst.py            # call_type=analyst:<id> 라벨
  - core/strategist/run_strategist.py        # call_type=strategist:<track> 라벨
  - core/executive/synthesize.py             # call_type=executive 라벨
  - core/intent/classifier.py                # call_type=intent_classification 라벨
  - core/intent/formatter.py                 # call_type=answer_formatter 라벨
  - core/intent/router.py                    # call_type=refuse_guide 라벨
  - pipelines/market_briefing_pre/stages/analyze.py  # call_type=briefing 라벨
  - server/main.py                           # ops 라우터 등록
  - tests/test_anchors.py                    # 결정론 기본 가드 테스트 + fallback 테스트 config 게이트
contracts: []
depends_on:
  - AUTO-SIGNAL-GENERATION-001 (전략가/collector 호출이 원장의 주 기록원)
  - WAVE-ALPHA-001 (anchor 산출 — 결정론 픽커로 기본 전환)
---

# LLM-COST-LEDGER-001 — LLM 비용 원장 + 결정론 anchor 기본화

> **동기 (2026-07-04, 팩트 기반).** Gemini 월 지출이 매일 폭발적으로 늘어 사용자가 AI Studio
> 지출 상한을 걸어 며칠간 서버를 중단. "다른 LLM 벤더로 갈지 말고 현 구조에서 지출을 줄이되
> 시스템 결과물은 최대한 유지"가 요구사항. 진단 결과 **비용이 어디서 나가는지 로컬에 기록이
> 없어 추측만 가능**했던 것이 근본 장애 → 가시성(원장)을 먼저 세우고, 실증된 낭비(anchor LLM)를
> 결과물 손실 없이 제거.

## 진단 (실측)

- `llm_call_cache` 는 멱등 캐시(unique input_hash 1행)라 **실제 지출 총액을 못 담음** — 대형 호출
  (분석가·전략가·executive·브리핑)은 input_hash 없이 호출돼 기록조차 안 됨. 진짜 청구서는
  Google AI Studio 대시보드에만 존재.
- anchor 선택 LLM(α 3 timeframe × universe × 매일)은 **1콜당 입력 ~14k 토큰**의 비대 호출.
- **anchor α 검증 (실 Gemini, 2026-07-04):** LLM 이 α 를 낸 3/6 케이스는 결정론 "마지막 3 usable
  candidate" 픽과 **소수점까지 동일**. 나머지 3/6 은 LLM 이 C=최근점을 골라 current 와 날짜 충돌 →
  **α 산출 실패(None)**. 즉 anchor LLM 은 성공 시 결정론과 동일 + 절반은 실패하는 계산기.

## 결정

1. **비용 원장(`llm_cost_ledger`)** — `call_llm` 이 통과하는 모든 호출을 1행씩 기록. 축 =
   **provider(벤더) · model · call_type(질의영역) · target · tokens · cost · cache_hit · day**.
   벤더/모델을 바꿔도 같은 축으로 추적 가능. mock 응답은 제외(dev/CI 노이즈).
2. **결정론 anchor 기본화** — `config.alpha.anchor_llm_enabled=false`(기본)일 때 anchor A·B·C 를
   결정론 코드로 선택(`_deterministic_anchors`, source='deterministic'). LLM anchor 는 토글로
   되살리기 가능(runtime.yaml hot reload). universe×3tf×매일 anchor LLM 비용 → 0, α 결과물 보존/개선.
3. **운영자 화면** — webapp `/ops/llm-cost` 한 화면(유저 비노출 예정 URL). 일단위 × 벤더 × 모델 ×
   질의영역 지출 + 추세. 서버가 도는 동안 원장이 쌓여 하루만 돌려도 폭발 지점이 숫자로 드러남.

## 마일스톤

- **M-A 원장 (done):** 테이블 + `record_llm_cost`/`cost_summary` + `call_llm` 중앙 기록 +
  9개 질의영역 call_type 라벨. 실 Gemini 1콜로 provider/model/tokens/cost 매핑 검증.
- **M-B 결정론 anchor (done):** AlphaConfig 게이트 + `_deterministic_anchors` 기본 경로. 005930·
  000660 6/6 timeframe α 산출(이전 LLM 4/6 실패), source='deterministic', anchor LLM 콜 0.
- **M-C 백엔드 API (done):** `GET /api/ops/llm-cost?days=N` → cost_summary.
- **M-D 운영자 화면 (done):** 총계 + 벤더/모델/질의영역 막대 + 일자별 표. days 7/14/30 토글.

## 잔여 / 후속 (백로그)

- 원장 켠 채 하루 실가동 → 실측으로 진짜 주범 확인 후 정밀 절감(활용/횟수 재배치).
- 사용자 관찰 "종목은 좋은데 시장 상황 미반영 = 종합 판단 부재" → 아낀 예산을 시장-엮는 종합
  판단에 투입 (별도 SPEC 후보).
- 원장 retention(장기 누적 시 일별 롤업 + 원행 정리) — 여유 시.
- 결정론 JSON collector(theme/news/market_view) tier flash→flash-lite 후보(추가 절감).
