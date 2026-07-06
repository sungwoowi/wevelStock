---
date: 2026-07-07
topic: 라이브 첫날 하드닝 — 시황 브리핑 misfire 수리 + 장전 브리핑 실전 관점·가독성·배선 개편 (커밋 9)
status: completed
---

# 2026-07-07 · 라이브 첫날 하드닝 — 사용자와 실시간 핑퐁으로 브리핑 완성

## 배경
M1 배포 후 첫 라이브 날. 사용자가 텔레그램 실물을 받아보며 결함·개선을 실시간 제보 → 심야까지 핑퐁 9커밋. 핵심 판단 2건: **① "시황 알림 전멸"의 근본 = 파이프라인 잡만 misfire 유예 1초**(6-15 절전 보강이 loader.py 를 빠뜨림) **② 브리핑의 가치 = "홀딩/매도/매수" 판단 직결 워딩**(사용자 예시 글 → 단기/장기 관점 분리 + 조건부 대응 + 재탕/빌미 판별).

## 한 일
### 스케줄러·안정성
- `server/schedulers/loader.py` — 파이프라인 잡 misfire_grace_time=1h (시황 브리핑 09:30/12:30/14:30 3연속 침묵 근본 수리. 콘솔 로그로 유예 1초 잡 전멸 vs 1h 잡 전부 발화 대비 확정)
- `pipelines/market_briefing_pre/stages/analyze.py` — briefing 콜 `thinking_budget=0` (라이브에서 thinking 이 출력 예산 잠식 → 506토큰 잘림 → 시나리오 공백 실증, 기존 결함 시그니처)
- `core/notification/service.py` — 텔레그램 4096자 분할 연속 발송(기존: 통째 실패→파일 폴백행) + **선택적 escape**(`<a>`/`<b>` 안전 태그만 보존 — 전체 escape 가 태그를 깨던 함정) + DB/파일 폴백 plain strip(웹앱 알림 탭 태그 노출 방지)

### 장전 브리핑 — 실전 관점·배선
- `prompts/briefing.md` + `core/briefing/render.py` — scenario 에 `short_term`(1~2주)/`long_term`(1개월+) 구조 필드: 스탠스+**조건부 대응 강제**("○○이면 △△ 자리"), 재탕/빌미 판별 명시(중심 이벤트 해석 인용), 독자 세 심리에 답하기. 렌더 ⚡단기/🌊장기 블록
- `core/watchlist_view.py::render_candidate_menu_md` — **신규 후보 결정론 메뉴**(전일 큐레이션: 거래대금/거래량×주도주/눌림/바닥 컨셉×funnel 단계) 프롬프트 주입 — LLM 이 학습 지식 속 유명 대형주(한미반도체류)로 회귀하던 문제 구조 수리 + 발굴 우선순위 가이드
- `stages/load_positions.py::_load_paper_holdings` — **보유 의견 배선 구멍**: 가상매매 정본 `account_positions`(실보유 삼성전자우·SK하이닉스·테스) 를 안 읽고 레거시 sim_positions 만 읽던 결함 → `get_holdings` 재사용 합류. 라이브에서 보유 3종 HOLD+평가손익 근거 첫 발행
- `render_positions` — `sector_watch` 렌더 복원(🧭 약세·회피 = 신규 회피·비중 축소 검토 — LLM 이 만들던 걸 렌더가 버리고 있었음)

### 가독성 (사용자 실시간 제보 반영)
- 핵심 뉴스: **한국어 헤드라인**(`headline_kr` 스키마 추가) + 링크 제목 임베드(🔗 줄 제거, 3줄→2줄) + 파급 ❗중/‼️대 기호 + 범례 한 줄 (시안 2문항 인터뷰로 선택)
- 신규 후보: 종목명/이유 줄 분리 + 종목 간 빈 줄 + **종목명 볼드** + reason 문장 경계 클립(`_clip_sentence`, 80자 싹둑 끊김 해소) + 내부 라벨(Canon: 경로) scrub 재사용
- 보유 의견: HOLD ▫→🔵 (신호등 색 원 통일) / expected_open·bias 코드 라벨 한국어화

## 검증 결과
- ✅ 전체 **1416+ passed** (신규 테스트 ~25) · 라이브 발송 6회 이상 — 사용자가 매 회 실물 확인
- ✅ misfire: 등록 재현 14잡 + 콘솔 로그(scheduler_started jobs=14, 1h 유예 잡 전부 발화)로 확정
- ✅ 배선: 보유 3종(−4.6%/−0.5%/−2.8%) HOLD 의견 라이브 첫 발행, 메뉴 실측 근거("눌림목·거래대금∩거래량 교집합") 인용 관측

## 의도적으로 안 한 것
- 대형주 후보 코드 강제(최대 1개 등) — 프롬프트 우선순위만, LLM 비결정성 관찰 후
- check_principles 의 paper 보유 7계명 체크 — 신호단·계좌관리자가 커버, 백로그
- 07:00 브리핑 레거시 collect_news 수렴 — SLOT 유지

## 다음에 이어서 할 작업 (우선순위)
1. **아침 라이브 관측 (전 계층 첫 완주)** — 06:40 ingest → 07:00 새 포맷 브리핑(중심 이벤트+단기/장기+보유 의견+메뉴 후보) → **09:30 시황(misfire 수리 검증점)** → 09:35 회차 전략가 이벤트 인용. `/ops/llm-cost` 원장 병행.
2. **NEWS-EVENT-INTERPRETATION-001 M2** — 해석 퀄 며칠 관측 후: lifecycle memory + structural_inflection 만 변곡 트리거·entry_posture 기여 + N5 개정 + 클러스터 키 정밀화.
3. **GATE-VISIBILITY UI** — 게이트·중심 이벤트·후보 메뉴의 화면 노출 (뉴스 탭 카드·데스크 배지·시황 칩).

## 커밋 상태
- 코드 9커밋 push 완료 (`456a7e5`~`207eaa4`) + docs(wrap-up) 1커밋 (본 wrap-up 수행).
