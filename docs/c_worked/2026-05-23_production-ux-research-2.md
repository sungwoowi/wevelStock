---
date: 2026-05-23
topic: production UX 자연어 채팅창 SPEC 진입 머티턴 조사 + LLM 3계층 정책 신설 (FAST/BALANCED/DEEP)
status: completed
plan_file: C:\Users\HOME\.claude\plans\jazzy-roaming-snail.md
---

# 2026-05-23 · production UX 머티턴 조사 + LLM 3계층 정책 신설

## 배경

cycle 14.3 (WAVE-ALPHA 14.2/14.3 풀세트, commit `e2ee94b` + wrap-up `2cdfaf3`) 완료 직후 **MS4 베이스라인 도달**. RESUME Top 1 = production UX (사용자 가치 최대 = 자연어 채팅창 종합 답변, 30 시나리오 우주 라우팅). 본 세션 = **머티턴 인터뷰 모드** (조사 + 3안 비교 + 합의 후 다음 세션 SPEC 인터뷰 진입). 코드 변경 0, plan 파일 (`jazzy-roaming-snail.md`) 만 7차 갱신.

세션 중 사용자 추가 결단 3건: (1) 기존 webapp = 데모 보존, 신규 채팅창 0 부터 자유 설계, (2) LLM 유연 대응 (Gemini Flash 현재 default), (3) Anthropic Haiku/Sonnet/Opus 의 비용 계층 전략을 Gemini Flash-lite/Flash/Pro 에 1:1 mirror.

## 한 일

- `C:\Users\HOME\.claude\plans\jazzy-roaming-snail.md` 신규 작성 + 7차 점진 갱신 — production UX 머티턴 조사 풀세트
  - 조사 3 explore: webapp 신규 라우트 mount 위치 + 30 시나리오 우주 본문 + 기존 intent/routing 인프라
  - Plan agent 1: Intent 분류 3안 비교표 + 추천 + sub-cycle 3 분할 + SPEC 인터뷰 vs 직진 권고
  - LLM 모델 3계층 정책 신설 (FAST/BALANCED/DEEP) + 영역별 매핑표 + config 스키마 (`llm.tiers` + `llm.areas`)
  - 사용자 합의 8건 확정

### 조사 결과 핵심 (Phase 1 — Explore 3 병렬)

- **인프라 80% 완성** = `track_selector.select_tracks` / `run_strategist*` / `/api/strategists/{id}/chat*` SSE / `resolve_ticker` (30 종목) 모두 작동
- **신설 필요 2개** = Intent Classifier + 종합 답변 포맷터 + 신규 라우트 `webapp/src/app/production-chat/page.tsx` (Next.js 15 App Router, 0 부터 자유)
- **30 시나리오 우주 전체 도출** (사용자 명시 5 + Claude 1차 6 + 2차 6 + 3차 6 + 4차 7). 1~11 = SPEC 매핑 완료, 12~30 = `input_routing` 확장 미완
- **anchors.py 2-Stage 하이브리드 패턴 (cycle 14 검증)** = Intent 분류에 1:1 mirror 가능
- **`core/llm/client.py`** = 이미 provider-agnostic (mock/claude_code/gemini/anthropic 분기 + fallback chain). `config/runtime.yaml:21` = `provider=gemini`, `model=gemini-2.5-flash`. 무료 티어 1,500회/일

### 사용자 합의 8건 확정

1. ✅ **오늘 작업 = Top 1 production UX** (Top 2 SLOT 후속 / Top 3 KIS breadth 보류)
2. ✅ **진입 방식 = 머티턴 인터뷰** (SPEC 인터뷰 즉시 X / 직진 X / 조사 후 결정)
3. ✅ **기존 webapp = 데모 보존, 신규 채팅창 0 부터**
4. ✅ **Intent 분류 = C 하이브리드** (Stage 1 결정론 + Stage 2 LLM + cache + manual fallback, anchors.py 패턴 mirror)
5. ✅ **다음 세션 진입 = SPEC 인터뷰 5라운드 먼저** (`docs/specs/PRODUCTION-UX-001-natural-language-chat.md`)
6. ✅ **LLM 모델 3계층 정책 신설** (FAST/BALANCED/DEEP, Gemini-Anthropic 1:1 mirror)
7. ✅ **3계층 적용 범위 = D** (정책만 박고 점진 — 신규 영역만 즉시, 기존 영역은 후속 SPEC `LLM-TIER-MIGRATION-001`)
8. ✅ **SLOT S6 (Gemini JSON 파싱 결함)** = 본 SPEC 의 Intent Classifier 파서 강건화로 본질 동일 해소

### LLM 3계층 매핑

| 계층 | Gemini | Anthropic | 적합 작업 |
|---|---|---|---|
| FAST | Flash-lite | Haiku 4.5 | Intent 분류 / 코드 라벨 → 자연어 변환 / JSON 추출 |
| BALANCED | Flash | Sonnet 4.6 | 분석가 9 본문 / 전략가 본문 / 종합 추론 |
| DEEP | Pro | Opus 4.7 | 회고분석가 (M4) / 메타 추론 / PROPOSAL |

## 검증 결과

- ✅ Explore 3 병렬 dispatch (webapp 구조 / 30 시나리오 / intent 인프라) 모두 풍부한 사실 보고
- ✅ Plan agent 1 dispatch — 3안 비교표 + sub-cycle 3 분할 + SPEC vs 직진 권고 + 7 결정 freeze 항목 도출
- ✅ plan 파일 7차 갱신 완료. 다음 세션 read 만으로 SPEC 인터뷰 즉시 진입 가능
- ✅ 코드 변경 0 (read-only 모드 + 머티턴 조사). pytest 회귀 없음 (변경 없으니 자명)

## 다음에 이어서 할 작업 (우선순위)

1. **PRODUCTION-UX-001 SPEC 인터뷰 5라운드** (~1 세션) — `/spec-interview PRODUCTION-UX-001` 시작. 7 결정 freeze: (1) 30 시나리오 ↔ agent_route 매핑 권위 / (2) 종합 답변 포맷 contract / (3) manual fallback trigger 임계 / (4) 코드 라벨 사전 권위 / (5) production-chat vs 기존 webapp 분리 경계 / (6) 30 시나리오 우주 v1 freeze 범위 / (7) Intent Classifier LLM provider/model 정책 (FAST 계층 적용 + fallback chain + JSON 파서 강건화 + 무료 티어 모니터링)
2. **PROD-UX-1 구현** (~1 세션, SPEC frozen 후) — Intent Classifier 코어 (`core/intent/{classifier.py 250, cache.py 80, router.py 180, system_prompt.md 100}`) + `config/scenario_keywords.yaml 200` + `POST /api/chat/production 150` + `webapp/src/app/production-chat/page.tsx 200` + `tests/intent/test_classifier_golden.py 250` (90건 골든 eval ≥ 85%). 시연 = "삼성전자 살까" → track_a 호출 → raw 응답 표시
3. **LLM-TIER-MIGRATION-001 SPEC 신설** (~0.5 세션 microcycle) — 기존 영역 점진 교체 (anchors.py Stage 2 Flash → Flash-lite + SLOT S6 통합 / 분석가 9 / 전략가 / 회고분석가 M4). 영역별 1 PR 단위 + 회귀 검증

## 의도적으로 안 한 것

- **SPEC 파일 (`docs/specs/PRODUCTION-UX-001-...`) 신규 작성 X** — 다음 세션 SPEC 인터뷰 5라운드 진행 후 frozen 으로 작성. 본 세션은 plan 파일 (`.claude/plans/`) 만 갱신
- **코드 변경 0** — 머티턴 조사 모드. 다음 세션 PROD-UX-1 부터 신설 코드 진입
- **기존 webapp 영역 (`/`, `/analyst-chat`) 미수정** — 데모 보존 결단 (사용자 명시)
- **anchors.py Flash → Flash-lite 강등 보류** — 적용 범위 D (점진) 결단으로 LLM-TIER-MIGRATION-001 후속에서 회귀 검증과 함께

## 커밋 상태

- 본 wrap-up 의 c_worked + RESUME.md + SESSIONS.md + memory 갱신 = 1 커밋 묶음 진행 예정
- 코드/SPEC 신규 0 → 별도 코드 커밋 없음
