---
date: 2026-05-29
topic: Flash 코드 라벨 스크러버 + webapp 임원 모드 토글 (Top 1, 같은 날 2번째 세션)
status: completed
plan_file: C:\Users\HOME\.claude\plans\declarative-riding-breeze.md
---

# 2026-05-29 · Flash 라벨 스크러버 + webapp 임원 토글 (Top 1)

## 배경
직전 세션(하이브리드 임원 PoC, `c55be19`)이 옵션 2를 확정했으나 2가지 미완 — (1) Flash가 doctrine 지시를 따라도 `sweet`/`S-Score`/`buy_score` 등 코드 라벨을 본문에 잔존 노출(system prompt 사전 주입만으론 약한 모델 한계), (2) 백엔드 `executive_mode`는 완성됐으나 webapp이 안 보내 시연 불가. 핵심 판단 = **라벨 누출은 결정론 후처리(역치환)면 모델 무관 깔끔, 토글 노출로 PoC를 사용자 체감 단위로**. RESUME Top 1 직진.

## 한 일
- `config/label_dictionary.yaml` — α 5단계 라벨(`trend_broken`/`weak`/`modest`/`sweet`/`overheated`) 자연어+short 추가 (`collectors/scoring.py:46` AlphaLabel 기준, Flash 실제 누출 토큰)
- `core/intent/formatter.py` — `scrub_code_labels()` 신설 (코드형 라벨만·길이 내림차순·경계 인식 정규식·`short` 치환, 순수 한국어 key 제외로 이중 wrap 방지) + `_scrub_rules()` 캐시 + `reload_label_dictionary()` 캐시 클리어 확장 + `format_answer` 반환에 적용
- `core/executive/synthesize.py` — `scrub_code_labels` import + `synthesize_executive` 반환 `text`에 적용 (단일+SSE+smoke 일괄 커버)
- `server/api/production_chat.py` — `executive_tier: Literal["balanced","deep"]` 필드 + `_executive_model_override()`(deep→`model_for_tier("deep")`) + 단일/스트림 2 분기에 model override 전달
- `webapp/src/app/production-chat/page.tsx` — `executiveMode` 상태(off/flash/pro, 기본 flash) + fetch body 분기(flash→executive_mode, pro→+executive_tier:"deep") + "종합 모드" 버튼 그룹 토글 UI(analyst-chat provider 패턴 미러)
- `tests/intent/test_formatter.py` — `TestScrubCodeLabels` 8건 (점수·α단계 치환 / 한국어 key 비-이중wrap / 영단어 내부 미오치환 / RS Score > RS 우선 / format_answer 적용)
- `tests/test_executive.py` — `test_applies_code_label_scrubber` 1건
- `docs/RESUME.md` — 미해결 부채에 KIS rate limiter 전역화 + validate.py cp949 크래시 등재, Flash 스크러버 ✅ 해소 표시

## 검증 결과
- ✅ pytest **620 → 629 passed** (+9 신규, 회귀 0)
- ✅ validate.py 0 errors (1 pre-existing warning: teams/registry.yaml)
- ✅ 라이브 smoke `scripts/smoke_executive.py --flash` — Flash 답변 코드 라벨 **0건**(`sweet→적정 가속 구간`/`weak→약한 추세`/`overheated→과열 구간`/`S-Score→주도주 점수`/`operational_safeguards→운용 안전핀` 치환 확인). JSON grep 유일 매치는 classification 메타 필드 `confidence`(답변 본문 아님). Flash $0.0037 / 1180tok.

## 의도적으로 안 한 것
- **Pro 자동 발동 라우팅(SLOT S7)** — Top 2. 본 세션은 수동 토글(off/flash/pro)만. 사용자가 webapp에서 Flash vs Pro 격차 직접 체감(Flash=기계적 관망 / Pro=분석가 보류여도 장기추세 분할 진입) → Top 2 라우팅 설계 입력값으로 축적.
- **webapp 토글 런타임 육안 확인** — 코드 완료, 서버 재시작 후 사용자 확인 단계(서버 8000은 옛 코드 상태였음).
- **main 머지** — Top 3, PoC 격리 유지(사용자 "별 결단").

## 기술 부채/미완
- **Flash vs Pro doctrine 격차** = 일부는 모델 능력 천장(완전 제거 불가), 일부는 doctrine 결정론 구조화로 축소 가능 → Top 2/SLOT S1 frame_mode 배선과 연결.
- **KIS "초당 거래건수 초과" 반복** — throttle 인스턴스별+lock 없는 레이싱, 병렬 fan-out 충돌. 비차단(DB-first 폴백 자가회복). 근본=전역 token-bucket SPEC. 백로그(`INFRA-KIS-RATELIMIT-001` 후보). 메모리 등재.
- **validate.py cp949 크래시** — Windows 콘솔 마지막 `✓` 출력 `UnicodeEncodeError`. 검증 자체 정상, `PYTHONIOENCODING=utf-8` 우회. print 인코딩 가드만 추가하면 됨.

## 다음에 이어서 할 작업 (우선순위)
1. **Pro 발동 라우팅(SLOT S7) + 다종목 검증** — "분석가/전략가 verdict ↔ 추세 프레임 충돌 시 Pro" 트리거 후보(본 세션 Flash/Pro 격차 관찰서 도출) 설계 + 005930 외 종목(중소형·테마·거시 변곡점) smoke로 doctrine 견고성 확인
2. **임원 frame_mode 결정론 배선(SLOT S1)** — Pro "분할 진입" 의견이 7계명·손절선 가드 안에 머무는지 점검(가드 우회 합리화 차단). advisory 비결정성 하드닝
3. **main 머지 결단 → INFRA-SCORE-INPUTS-001 재개** — PoC 채택 시 main 머지 + 9 분석가 cited 슬림화, 이후 데이터 배선(F/S/buy/T-Score input collector, ~5세션)

## 커밋 상태
- 코드 commit + wrap-up docs commit + `git push` 진행 (feature/hybrid-executive-poc). **main 무변경**(PoC 격리, 머지는 Top 3 별 결단).
