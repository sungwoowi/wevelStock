---
date: 2026-07-05
topic: AUTO-SIGNAL-INTEGRITY-001 Tier 0 구현 (TDD) + 3겹 검증 + 07-03 SK하이닉스 재구성 (같은 날 2세션)
status: completed
plan_file: C:\Users\HOME\.claude\plans\x-ipo-zany-meteor.md
---

# 2026-07-05 (2) · AUTO-SIGNAL-INTEGRITY-001 구현 + 07-03 패닉 역발상 사각 발견

## 배경
오전 진단 세션(같은 날 1세션)이 박은 Tier 0 SPEC 을 사용자 지시("구현 시작, 필요하면 인터뷰")로 즉시 구현. 핵심 인터뷰 1회 = 게이트 방식 — 사용자 의도 확인 결과 **차등 게이트 + wait 강등·원판단 기록**(blanket 기각: "공포를 기회로 삼을 고도 추론" 철학과 06-15 눌림목 철학 정합). MARKET-CONTEXT-BRAIN-001 Tier 0 전진 (AUTO-SIGNAL-INTEGRITY-001 draft→implementing).

## 한 일
- `core/signal/alpha_posture.py` — `_apply_defensive_gate`(defensive 면 buy 후보에 강세섹터+주도주+건강위치+파동 요구, 미충족 wait 강등+`pre_defensive_candidate` 기록+`defensive_release` 조건부진입) + `derive_wave_alive`(트랙별 timeframe: A=주봉/B=일봉, trend_broken=False) + `PostureInputs.entry_posture`·`PostureConfig.defensive_gate_enabled`.
- `core/signal/auto_signal.py` — T0-b 배선 3개: `_sector_rs_from_s_inputs`(S-Score supply_chain 실측 재사용, 중립 fallback 배제)·`compute_alpha_3tf`→wave 필드·`get_today_view`→entry_posture(DB read 비용 0). `_market_state_md` 태세 노출. **코드 안전핀**: defensive 강등 후보인데 LLM 이 `llm_deviation_reason` 없이 buy → 코드가 wait 강등+`posture_blocked`(persona 강제불가 교훈). `_signal_commandment_gate`(T0-c): checkers/commandments 4·5·6 **그대로 재사용**(신규 규칙 0, 비중 계명은 계좌관리자 소유) — 손절선 부재=강등, 지표<3=경고 기록.
- `collectors/news_source.py` — `get_unlabeled_items` + `backfill_unlabeled_news`(T0-d: NULL 라벨 재시도, 캐시 멱등·lookback 7d·limit 120) / `server/schedulers/jobs/news_ingest.py` 4.5단계 합류 / `config/news_source.yaml` backfill 섹션.
- `tests/test_auto_signal_integrity.py` — 신규 22건 전부 RED→GREEN(TDD). 후성 06-16 재현("defensive 아니면 buy" 증명 포함).
- `tests/test_watchlist_view.py` — **date-rot 수리**(무관 기존 결함): 절대 날짜 2026-06-16 이 10일 rolling window 밖 → 오늘 기준 상대 날짜로.
- `scripts/_replay_defensive_gate.py` — 사용자 확인용 리플레이(읽기 전용·LLM 0).
- `docs/specs/MARKET-CONTEXT-BRAIN-001` — 사용자 통찰 추가: Tier 1 **해석 질문지 3축**(novelty/펀더 정합/노이즈 반복) + Tier 2 **주도주 사이클 위치 게이지**(신고가=100)·**PANIC-REVERSAL 레인**. `AUTO-SIGNAL-INTEGRITY-001` status implementing + 게이트 설계 확정 기록.

## 검증 결과 (3겹)
- ✅ 전체 pytest **1367 passed** · validate 0 errors.
- ✅ 리플레이: 실 DB 의 과거 buy 8건(후성 3·SK하이닉스 등) → 새 게이트면 **전부 wait 차단** (당시 미배선 상태 그대로 재현).
- ✅ 라이브 probe (실 Gemini 2콜, ~$0.007): 배선 3개 실측 채워짐(SK하이닉스 섹터RS 4.0·주봉파동 True/일봉 False — LLM 사유에 "일봉 추세 이탈" 인용됨) + 오늘 dd=6 이라 **위험 게이트가 defensive 보다 우선 발동**(계층 순서 설계대로) + wait persist·단계 watching.
- ✅ 07-03 SK하이닉스 재구성(cutoff 결정론): 시스템 = 모든 층에서 wait vs 사용자 = 장초 폭락 매수 적중(저점 대비 +18.6%) — **패닉 역발상의 설계상 사각 확정**.

## 발견 (다음 사이클 재료)
- **extension_score 가 폭락 직후에도 9.5** — ma20-아래 이격 미감점(k_below 백로그)으로 "건강한 눌림"과 "패닉 이탈" 구분 불가. PANIC-REVERSAL 설계 시 함께 해소.
- **게이트 가시성 UI 부재** — 차단/강등은 좋은 일이 "안 일어나는" 스펙이라 눈에 안 보임. 데이터는 전부 영속됨(`data.alpha_posture`) → 프론트 표시만: 데스크 wait 카드 🛡 배지(원후보 buy)·시황 태세 칩·차단 알림 로그 (GATE-VISIBILITY 작은 SPEC 후보).
- 주말 등 오늘 market_view 스냅샷 부재 시 entry_posture=None → 게이트 침묵(장중 cadence 는 09:30 갱신 후라 실영향 낮음, 관측만).

## 다음에 이어서 할 작업 (우선순위)
1. **NEWS-EVENT-INTERPRETATION-001 spec-interview** — Tier 1: 격상 레인 + 해석 질문지 3축(novelty·펀더 정합·노이즈 반복) + lifecycle + `news_digest_md` 배선 + N5 개정. 메타발 06-23→07-02 가 리플레이 표본.
2. **라이브 관측** — 서버 재시작(필수) 후 평일 cadence 에서 `defensive_gate_demote`/`commandment_gate_demote` 로그·wait 사유 확인 + `/ops/llm-cost` 원장 실측 병행.
3. **GATE-VISIBILITY UI** — 게이트 판단 가시화(위 발견). 백엔드 신규 ~0, 프론트 표시 위주.

(이월: Tier 2 주도주 판별+사이클 게이지+PANIC-REVERSAL = 결정론 후보층 강화(06-20 스레드)와 합류 / k_below 튜닝.)

## 커밋 상태
- feat(코드+테스트+config+스크립트) + docs(wrap-up) 2 커밋, main push (아래 wrap-up 이 수행).
