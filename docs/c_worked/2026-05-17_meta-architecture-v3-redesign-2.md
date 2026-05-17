---
date: 2026-05-17
topic: wevelStock v3.0 메타 페르소나·시스템 아키텍처 재설계 — 9+3+1+회고N + Track A/B + 결정론 채점 + 적중도 5 KPI (R&D → 엔지니어링 인수인계)
status: completed
plan_file: C:\Users\HOME\.claude\plans\parsed-dazzling-stearns.md
---

# 2026-05-17 · v3.0 메타 재설계 (R&D 인수인계)

## 배경
같은 날 사용자가 chat Claude Opus 와 본질 토론 마침 — 결과물 2 메모 (`idea_memo/2026-05-17-wevelstock-rd-meta-design-by-chat-claude-opus.md` 시스템 아키텍처 + `idea_memo/prism-insight-비교차용2.md` v3.0 이원 트랙 페르소나 디자인) 던지고 "페르소나·시스템 아키텍처 재설계" 요청. 본 세션 = **R&D (챗AI Opus) → 엔지니어링 (Claude Code) 인수인계 첫 사이클**, 챗AI 결과물을 SPEC + docs 로 명문화. 핵심 판단: 16 페르소나는 참고용일 뿐 9+3+1+회고N 골격 절대, 결정론 채점은 코드 stage + canon 명제 ID 분리 (옵션 b), 회고분석가는 N 제한 X (창의성 보존).

## 한 일
- `docs/specs/ANALYST-PERSONAS-001-...md` (v1→v2) — frontmatter version 2 + generates 에 `collectors/scoring.py` 추가 + 새 § 5 개 (9+3+1+회고N 골격 / 16 페르소나 흡수 매핑 표 (신규 5명만 ⭐) / 결정론 채점 권위 (옵션 b) / 한국어 친화 용어 강제 / F-Score 신설 § flow_analyzer 4 축 가중치) + SLOT S7/S8/S9 추가 + 관련 SPEC 2 개 링크
- `docs/specs/STRATEGY-TRACK-001-two-track-strategists.md` (신설) — Track A (중장기 수익금 게임, 자본 70-80%·승률 70%+·MDD -8% 보호) + Track B (단기 손익비 게임, 자본 20-30%·R/R 1.5:1+·trailing stop) 정식 분화. α 가속계수 오버라이드 룰 (1.3-1.5 T max 5 / 1.5-2.0 T max 7 / 2.0+ T min 3). Track Selector = manifest `input_routing` 룰 (별도 페르소나 X). plugin 확장 (Track C 향후 = manifest 드롭만). `strategist-recommendation-v1` 계약 + DB schema
- `docs/specs/GUIDANCE-ACCURACY-TRACKER-001-five-kpi-tracking.md` (신설) — 5 KPI (방향 적중률 / 타점 정밀도 / R/R 실현율 / 자가 진단 정확도 / 트랙 분리 효과) + 트랙별 가중치 차별 (A 방향 30% + 분리 25% / B R/R 35% + 타점 20%). `guidance-record-v1` 계약 + `guidance_records` 테이블 schema + 30·60·90 일 daily 18:00 KST cron + `회고` 단축어 양식
- `CLAUDE.md` — 5-Layer 표 → **9+3+1+회고N 골격** (Layer 5 회고분석가 N 제한 X), 전략가 라우팅 § Track A/B 갱신 (단타·중장기 삭제)
- `docs/STRUCTURE.md` — 9/9/2+/1+/N 표 + 9 학습부 1:1 매핑 (mechanics → trading 외 5 신규) + Layer 3 트랙 표 + plugin 패턴 회고분석가 추가 + canon 트리 9 학습부 × 36 카테고리 정합
- `C:\Users\HOME\.claude\projects\C--Users-HOME-claude-wevelStock\memory\feedback_concise_summary_first.md` (신설) — 긴 분석 글 끝에 "한눈에 무엇을 하라" 명료 요약 강제 + MEMORY.md 인덱스 1 줄 추가

## 검증 결과
- ✅ `PYTHONIOENCODING=utf-8 uv run python scripts/validate.py` → 0 errors, 1 warning (registry.yaml 무관)
- ✅ `TESTING=1 PYTHONIOENCODING=utf-8 uv run pytest tests/ -q` → **135 passed**, 회귀 0 (코드 변경 0, 문서·SPEC 만)

## 의도적으로 안 한 것
- **코드 변경 0**: `collectors/scoring.py` (S/T/α/buy_score/F-Score 결정론 함수), `agents/strategists/track_a/track_b/{persona.md, manifest.yaml}`, `core/strategist/run_strategist.py`, `core/guidance/recorder.py` 모두 SLOT 만. 다음 세션 진입
- **`INFRA-RELIABILITY-VALIDATOR-001`** (Layer 2.5/3.5 Haiku 검증) — 백로그. 운용 1 개월 데이터 후 환각·내부 모순 빈도 보고 결정
- **`RETROSPECT-ANALYST-001`** / **`SYSTEM-EVOLUTIONIST-001`** (Layer 5 회고분석가 본체) — 백로그. M4 (16주) 후 진입
- **`WAVE-ALPHA-001`** (Module A α 공식 canon + scoring.py) — 백로그. `stock_analyst` 페르소나 작성 시 동시
- **`INFRA-CHART-DATA-001`** (KIS daily chart + pandas-ta + matplotlib vision) — 백로그. `stock_analyst`·`trader` 페르소나 작성 직전 필수 (차트 추론 환각 차단)
- **v3.1 잠정 풀이 6 개 (M2/C1/I2/C3/C5/I6) canon 원문 정정 patch** — 사용자 manual 검증 필요 (사전 부채, Track A persona 작성 직전 처리 권장)
- **`config/runtime.yaml` 의 `flow_analysis.theme_authority` 첫 정의** — 운용 데이터 누적 후 회고분석가 PROPOSAL 영역

## 다음에 이어서 할 작업 (우선순위)

1. **Track A persona.md + manifest.yaml + `core/strategist/run_strategist.py` 골격 (~2 세션)** — STRATEGY-TRACK-001 의 첫 실체. canon = 9 dept 핵심 framework + market_snapshot + `team_outputs` DB read + RAG. webapp `analyst-chat/page.tsx` default agent = `track_a` 또는 `both` 로 교체. lean startup — 통합 페르소나 production 가치 검증.
2. **`collectors/scoring.py` 함수 골격 + ANALYST-PERSONAS-001 v3.1 잠정 풀이 정정 patch (1 세션)** — 5 점수 함수 시그니처 확정 (S7 SLOT), 결정론 단위 테스트 (`tests/test_scoring.py`), wealth_strategist 박힌 잠정 풀이 6 개를 canon 원문 frame 으로 정정. SPEC v2 의 S7·S9 SLOT 닫음.
3. **Track B persona.md + manifest.yaml + `core/strategist/track_selector.py` (~1.5 세션)** — Track B 단기 손익비 게임 + Track Selector manifest `input_routing` 동적 라우팅 (명시 단축어 우선 → auto.conditions → fallback). 양 트랙 동시 평가 `both:` 지원.

(추가 백로그: `agents/analysts/<id>/` 자료 있는 3 명 = `principle_guardian` · `trader` · `stock_analyst` 페르소나 v2 양식 작성 (한국어 용어 강제 § + 결정론 채점 발행 매핑) / 자료 0 시드 5 명 페르소나 / `guidance_records` DB 마이그레이션 + `recorder.py` STRATEGY-TRACK-001 권고 발행 시 자동 적재 / Layer 4 계좌관리자 1+ N (M5) / `INFRA-CHART-DATA-001` KIS 일봉 + 지표 사전계산 + matplotlib vision / Layer 5 회고분석가 SPEC)

## 맥락 재진입 힌트
- **9+3+1+회고N 골격 = 절대 흐름**: 분석가 → 전략가 → 계좌관리자 → 회고분석가 (보완·신규 부서 제안). 9·3·1 은 본질, 계좌관리자·회고분석가는 N 가변. 회고분석가 N 제한 두면 창의성 죽임 (사용자 명시).
- **단타·중장기 빼고 A/B 만**: 장기 = 믿음 영역 + 지수 투자로 대체. A/B 판단이 시급. 향후 trackplugin 확장 가능.
- **결정론 채점 = 코드 stage (`collectors/scoring.py`) + canon 명제 ID 분리** (옵션 b 채택). canon md 는 frame 원리·렌즈만, 공식·수치는 코드 함수.
- **F-Score 신설 = `flow_analyzer` 발행물**: 단순 외인 매수/매도 X. 종목·테마별 5 주체 가중치 차별 (테마-주체 매칭 0.4 + 모멘텀 0.3 + 자금 속도 0.2 + 일치도 0.1).
- **한국어 친화 용어 강제** = LLM 응답 양식. "주도주 점수 8 (S-Score=8)" 같이 한국어 + 코드 라벨 병기. 시스템 모르는 사람도 이해.
- **R&D / 엔지니어링 도구 분리** = chat Claude Opus 가 페르소나 본질 설계 / Claude Code 가 .md 받아 코드 변환. Git = 영구 메모리. 이번 세션이 첫 인수인계 사이클.
- **canon vs persona vs reference**: canon = 모든 LLM 호출 system prompt 자동 주입 (공통 매뉴얼) / persona = 분석가별 정체성·톤 (역할 정의서) / reference = Chroma RAG 회수 원본 (도서관 책장).

## 커밋 상태
- docs 만 (SPEC 3 + CLAUDE.md + STRUCTURE.md + memory + MEMORY.md) 1 commit 진행. 사용자 명시 = push 도 수행.
