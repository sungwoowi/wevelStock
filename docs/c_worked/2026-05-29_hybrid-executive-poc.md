---
date: 2026-05-29
topic: 하이브리드 임원 종합 레이어 PoC — 옵션 2 가설 검증 (cycle 6 후속)
status: completed
plan_file: C:\Users\HOME\.claude\plans\polymorphic-plotting-goblet.md
---

# 2026-05-29 · 하이브리드 임원 종합 레이어 PoC (ARCHITECTURE-HYBRID-EXECUTIVE-001)

## 배경
사용자가 production UX 답변 품질 저하로 방향 상실 — "미개발 분석가 탓이냐, 분석가/전략가 multi-LLM 구조가 어글리한 거냐" 혼란. git 잔존 smoke(`_smoke_track_b_resp.json`) + 라이브 베이스라인 + 코드를 직접 검증해 진단: **아키텍처가 틀려서가 아니라 종합 레이어가 "압축기 + 점수 문지기"라 통찰 서사를 못 냄.** LIVE 베이스라인이 결정적 — stock_analyst 혼자 풍부한 신호(주봉 sweet 1.19/ROE 18.9%/실적 가속)를 냈으나 track_a가 점수 누락 3건으로 기계적 wait → formatter "보류" 앵무새. **이 질문에선 데이터가 아니라 종합이 병목.** cycle 6 옵션 2(하이브리드 임원)를 별 feature 브랜치에서 PoC.

## 한 일
- `agents/executive/persona.md` + `manifest.yaml` — 투자 총괄 임원 doctrine. prism 7 패턴(결론 먼저·5-layer chain·시나리오 3·상황별 가중치·솔직 톤). 박종훈 거시 = 변곡점 전용(평상시 트레이딩 비인용, 사용자 명시). 환각 가드(가격은 입력 수치만·코드 라벨 본문 금지·전략가 verdict 맹종 금지).
- `core/executive/synthesize.py` (+`__init__.py`) — `format_answer` 풍부 버전. canon 주입 + label 사전 + `mock_fallback_allowed=False` + model override(tier A/B).
- `core/config/schema.py` + `config/runtime.yaml` — `executive_synthesis` area. 기본 BALANCED(Flash, 무료 1,500/일), Pro(deep)는 주요 트리거만 override.
- `core/llm/client.py` — gemini thinking 토큰을 cost 계산에 포함(비용 정확화) + `raw.thinking_tokens`.
- `server/api/production_chat.py` — `executive_mode` 플래그(formatter A/B, 단일+스트림).
- `scripts/smoke_executive.py` — formatter vs Pro vs Flash 1:1 비교(`--flash`로 Pro 절약).
- `tests/test_executive.py` — 단위 10 (system block·compose·mock 제외·all-missing skip·model override·박종훈 가드).
- `docs/specs/ARCHITECTURE-HYBRID-EXECUTIVE-001-...md` — PoC SPEC + 결단 5 + SLOT 7.

## 검증 결과 (005930 "삼성전자 살까?" 라이브 smoke)
- ✅ **옵션 2 가설 확정** — 같은 부분 데이터로 임원(Pro)이 prism 수준 답 산출. 전략가 기계적 wait 탈출 + 상황별 가중치 통합("섹터 힘·추세 가속이 더 중요").
- ✅ 가격 환각 0 (doctrine 가드 — 1차 smoke서 88,000 가짜가격 환각 사용자 발견 → 가드 강화 후 소멸), 잘림 0 (max_tokens 8000, Pro thinking 토큰 잠식 해소).
- ✅ Flash 튜닝: 결단력 완전 해소("분할 매수 접근"+행동가이드). 코드 라벨 누출은 개선됐으나 잔존(sweet/overheated/RS/S-Score/buy_score — Flash 능력 한계).
- ✅ pytest **620 passed**(회귀 0), validate.py 0 errors.
- 비용: formatter $0.0004 / Flash $0.003(1,500/일) / Pro $0.065(50/일).

## 의도적으로 안 한 것
- **frame_mode 결정론 배선** — LIVE 베이스라인서 principle_guardian가 이미 advisory_warning 발행 + 임원이 doctrine으로 우회 → 하드닝 백로그(SLOT S1).
- **main 머지** — PoC 격리 유지(사용자 명시 "PoC 결과 후 별 결단"). 검증 성공했으나 머지는 별 결정.
- **9 분석가 페르소나 변경** — 받아서 임원이 통합(최소 PoC scope).

## 기술 부채/미완
- **Flash 코드 라벨 잔존 누출** — doctrine만으론 한계. 결정론 후처리 스크러버(label_dictionary 치환)면 모델 무관 깔끔(SLOT 후보).
- **Pro 발동 라우팅 미확정** — 하이브리드 "주요 트리거/이벤트만 Pro" 판정 기준(SLOT S7). 사용자 "추후 검토".
- **gemini 503 transient** — 1차 smoke서 분석가 2명 503→claude_code 90s 타임아웃 실패(별 영역).
- 원인 1(데이터 미배선 = INFRA-SCORE-INPUTS-001)은 그대로 — 이번 PoC가 "종합이 병목"임을 증명했으나 데이터 배선은 별 작업.

## 다음에 이어서 할 작업 (우선순위)
1. **Flash 라벨 스크러버 + webapp 임원 토글** — 결정론 후처리로 Flash 라벨 누출 제거(production-clean) + `executive_mode` webapp UI 노출(실 채팅 체감). PoC를 시연 가능 단위로.
2. **Pro 발동 라우팅 설계(SLOT S7) + 다종목 검증** — "주요 트리거/이벤트만 Pro" 판정 기준 + 005930 외 종목(중소형·테마·거시 변곡점)으로 doctrine 견고성 확인.
3. **main 머지 결단 → INFRA-SCORE-INPUTS-001 재개** — PoC 채택 시 main 머지 + 9 분석가 cited 자연어 슬림화(풀 PoC). 이후 데이터 배선(원인 1)으로.

## 커밋 상태
- 코드 commit = `c55be19 feat: 하이브리드 임원 종합 레이어 PoC` (11 files, feature/hybrid-executive-poc).
- 본 wrap-up = docs commit 진행. **main 무변경**(PoC 격리).
