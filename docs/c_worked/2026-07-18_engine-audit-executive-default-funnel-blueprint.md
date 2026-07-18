---
date: 2026-07-18
topic: LLM 판단 구조 전면 감사 + 채팅 임원 기본화(P0) + 5축 깔때기 엔진 청사진 SPEC
status: completed
---

# 2026-07-18 · LLM 판단 감사 + 임원 배선 P0 + 5축 깔때기 청사진

## 배경
사용자가 "채팅이 함수자판기 같다" + 기술적분석 외부 자료 6종 첨부 + "분석가/전략가가 오버엔지니어링인지 통폐합/신설 판단하고 싶다"로 시작 → 13-에이전트 워크플로우로 전면 감사(채팅 경로·분석가/전략가 인프라·페르소나 13·canon·LLM 설정·DB 실물, 핵심 주장 반박 검증) → 제로베이스 브레인스토밍에서 **5축 모델(공간·시간·뉴스검색·실행·복기) = 초심(user_want_spec 원안)** 수렴 → prism-insight/stock-analyzer 실측(WebFetch) → **"위원회→소프트 깔때기 재배선 + 동적 구조 사다리"** 청사진 확정. 핵심 판단 1줄: **비용·wait 단일음·함수자판기의 공통 뿌리 = 위원회 배선이고, 부품(압축기·계산기·지식부)은 프리즘 대비 대등 이상 — 재건축이 아니라 재배선.**

## 한 일
### 감사 (문서 산출의 근거)
- 13-에이전트 워크플로우: 함수자판기 원인 5(압축기 formatter·executive 미배선·상쇄 배선·wait 단일음 96~100%+채팅 미저장·canon 규칙표 27빈폴더) / 오버엔지니어링 판정(골격 무죄·형식 레이어 유죄) / V1~V8 커버리지 / 9분석가 중복 매트릭스. 반증: 브리핑 내러티브는 유창=모델 무죄.
- 프리즘 실측: 13+에이전트·$310/월·**결정론 5단계 압축→3종목→심층**·자동복기는 홍보문구(수동). 우리 압축기= 대등 이상(백테스트 edge), 빠진 것=탑다운 배선+심층 출구.

### P0 구현 — 채팅 임원 종합 기본화
- `core/config/schema.py` — `ChatConfig(executive_mode_default: bool = True)` + `RuntimeConfig.chat`
- `config/defaults.yaml` — `chat.executive_mode_default: true` (hot reload, 주석 문서화)
- `server/api/production_chat.py` — `executive_mode: bool|None=None`(tri-state) + `_resolve_executive_mode()`(payload 명시 우선→config) + 단일/스트림 양 분기 적용. 웹앱 수정 0(동일 `formatted` 이벤트).
- `tests/test_production_chat_executive_default.py` — 신규 6 테스트(스키마 기본 True·요청 명시 우선 4조합)
- `tests/test_auto_signal.py` — stale 수리: provider `"gemini"` 하드코딩 → `get_config().llm.provider` (0a23704 provider→claude_code 커밋부터 썩어 있던 기존 부채)

### 문서 2건 (청사진)
- `docs/specs/ENGINE-FUNNEL-REWIRE-001-five-axis-funnel-engine.md` — roadmap SPEC(NORTH-STAR 자식, draft): 진단 요약·소프트 깔때기 아키텍처(deviation 기록 포함)·결단 D1~D7·프리즘 대응표·사다리 P0(완료)~P5·가드 6·미해결. 자식 예약 4(KNOWLEDGE-INTAKE/FUNNEL-TOPDOWN/DEEP-DIVE-REPORT/LENS-REGISTRY).
- `idea_memo/2026-07-18-five-axis-funnel-engine-refocus.md` — 사람용 표 정리(결론 3문장·벤더 차용표·현재→이후 구조·기각 목록·5축 매핑·사다리+기대효과·수리 대상 7).

## 검증 결과
- ✅ 전체 회귀 **1430 passed** (신규 6 포함, stale 1건 수리 후 0 fail)
- ✅ `scripts/validate.py` 0 errors (warning 1 = 기존 teams/registry.yaml)
- ✅ 문서 검증 에이전트가 인용 12곳 실물 대조 → 사실오류 2건(임원 max_tokens 8000→3500, 빈 폴더 26→27) 등 전건 수정 반영. (교훈: 문서화 작업에 49분짜리 검증은 과함 — 메모리에 박음)
- ⚠ venv에 pytest 부재 발견 → `uv sync --extra test` 로 복구 (test extra가 dev 기본 sync에 안 들어감)

## 다음에 이어서 할 작업 (우선순위)
1. **서버 재시작 → P0 라이브 체감 + 비용 감소 관측 + 관측 체크 3건** — 채팅 탭에서 임원 서술 확인(아침 시간표 피해 재시작). 겸사: 12:35 케이던스 제거 효과 원장 관측(이월) + ①`market_briefing_pre` scenario 2회 연속 빈 `{}` ②이중 발송(03:30/05:30·02:00/09:23) ③밴드 스킵 "관망 0" 집계 착시.
2. **P1 `KNOWLEDGE-INTAKE-001` spec-interview** — 자료 반입 동적화(원안 "교육팀"): 드롭→LLM 정제→승인 화면→canon 반영. 첫 표본=보유 강의 6종(신고가·가격수급 신규 반입 + 프랙탈/로그 정제). **canon 투입 시점은 MARKET-CONTEXT-BRAIN 관측 창과 안 겹치게.**
3. **P2 채점 루프 착수** — EVOLUTION-001/MARKET-CONTEXT-BRAIN Tier 4 합류. 적합도 함수 = "확신 없음(track record 0)"의 근본 해소이자 P3 재배선·P5 동적 통폐합의 전제.

(북극성 3택(출력/매매/검증)은 ENGINE-FUNNEL 사다리로 수렴 — ③검증이 P2로 채택된 셈. 페르소나 상쇄 배선 해체·스테일 sub-task 정정은 M2 세션에 합본. 해석 콜 thinking=0 교란변수 — 해석 퀄 판정 전 설정 재검.)

## 커밋 상태
- feat 1커밋(P0 코드+테스트) + docs 1커밋(SPEC+idea_memo+wrap-up) — 해시는 RESUME 참조. push 완료.
- 부수: 루트 `data/stock-advisor.sqlite`(0바이트, 감사 중 DB probe가 잘못된 경로로 생성한 빈 파일) 삭제.
