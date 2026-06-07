---
date: 2026-06-08
topic: INFRA-US-MACRO-SNAPSHOT-001 SPEC + 구현(MS-1~4) → verified = 왼쪽 뇌 4/4 완성
status: completed
plan_file: C:\Users\HOME\.claude\plans\logical-petting-tulip.md
---

# 2026-06-08 · INFRA-US-MACRO-SNAPSHOT-001 — 미장 매크로 스냅샷 (왼쪽 뇌 마지막 조각)

## 배경
LEFT-BRAIN-COMPLETION-001 roadmap 의 유일한 미완 자식. user_want_spec Task2(당일 시장 데이터)의 **미장 절반**(달러인덱스·미10년물·VIX·나스닥·필반·금)을 채워 왼쪽 뇌(수집→분석→답변)를 완성. **핵심 발견**: 미장 6지표는 이미 `connectors/yfinance/get_indices()`·`collectors/us_markets.fetch_overnight()`로 수집되고 있었다 → SPEC 본질이 "어댑터 신설"이 아니라 **영속 + risk-on/off 결정론 분류 + 시장관 흡수**로 좁혀짐. MARKET-VIEW-SYNTHESIS-001 이 비워둔 `us-macro-hook` SLOT 충족.

## 한 일
### SPEC (spec-interview 5라운드)
- `docs/specs/INFRA-US-MACRO-SNAPSHOT-001-us-macro-snapshot.md` — 신설. 3 결단 확정 → draft → 같은 세션 구현·라이브 후 **verified**.

### MS-1 코어
- `collectors/us_macro.py` — `USMacroSnapshot` + `classify_us_risk`(순수 결정론: 주식모멘텀 반도체가중 + VIX 레벨/패닉 게이트 + 달러·금리 역풍 → risk_on/neutral/risk_off + extreme) + `compute_us_macro` DB-first(get_indices 재사용, graceful unavailable) + DB layer + `refresh_us_macro` cron + render/흡수 helper.
- `config/us_macro.yaml` — 분류 임계 외부화(VIX elevated/panic·달러/금리 역풍·signal 밴드).
- `core/db/schema.sql` — v12 `us_macro_snapshot`(date PK, CREATE IF NOT EXISTS — ALTER 불필요).
- `tests/test_us_macro.py` — 12 (classify 매트릭스·DB-first·graceful·vix_panic·흡수 helper).

### MS-2 MarketView 흡수
- `collectors/market_view.py` — `apply_us_macro_to_posture`(U2 risk_off 단계강등·vix_panic 방어게이트·비대칭) + `entry_posture(us_macro=)` + `synthesize_market_view(us_macro=)` reason·one_liner 토큰 + `build_market_view` 가 compute_us_macro DB-first read + `render_market_view_md` 미장 야간 라인(get_today_us_macro 디커플, 스키마 변경 0).
- `config/market_view.yaml` — `us_macro.enabled` 토글.
- `tests/test_market_view_us_macro.py` — 10 (강등·게이트·비대칭·synthesize 흡수·하위호환).

### MS-3 영속 배선 (U3 둘 다)
- `server/schedulers/jobs/snapshot_macro.py` — 18:05 허브 3단계 us_macro append(market_view 앞 — DB-hit).
- `pipelines/market_briefing_pre/stages/collect_overnight_us.py` — 장전 persist 트리거(graceful, double-fetch dedupe SLOT).
- `agents/analysts/market_state_analyzer/persona.md` — 미장 야간 해석 지침(반도체 연동·raw 인용 OK).
- `tests/test_snapshot_macro_job.py` + `pipelines/market_briefing_pre/tests/test_smoke.py` — 신규 단계 mock 갱신(실 yfinance 차단).

### MS-4 라이브
- `scripts/_us_macro_probe.py` — capability + 실 yfinance fetch + 분류 + MarketView 흡수 실증.
- `docs/specs/LEFT-BRAIN-COMPLETION-001` — 자식 상태판 us-macro verified, 4/4.

## 검증 결과
- ✅ 전체 회귀 **966 passed**(944→+22) / `validate.py` 0 errors / project_status LEFT-BRAIN **4/4 (100%)** 전 자식 verified.
- ✅ **라이브 probe** — 실 yfinance 7/7 → **risk_off**(필반 -10.26%·VIX 21.5·signal_score -8.335, 실제 risk-off 장 포착) → build_market_view 흡수: entry_posture neutral→**defensive** 강등, one_liner "· 미장 위험회피", [7] 미장 야간 라인.
- ✅ **사용자 직접 확인** — 웹앱(localhost:3000 production-chat/analyst-chat)에서 왼쪽 뇌 검증 완료. 서버 재시작 후 확인.

## 의도적으로 안 한 것
- FRED 권위 값(DXY/DGS10) — yfinance 로 충분, SLOT.
- buy_score N 흡수(미장=시장 레벨) / risk_on 자동 상향(비대칭 보수) / KOSDAQ / 전략가 publish / 임계 다일 캘리브레이션 / 브리핑 double-fetch dedupe — 전부 SLOT.
- LEFT-BRAIN roadmap status 를 `done` 으로 닫는 것 — 오른쪽 뇌 착수와 묶인 사용자 결정이라 보류.

## 기술 부채/미완
- **dev cron 미작동 근본 해소** — 18:05·장전 둘 다 서버 상주 전제. 미상주 시 us_macro/sector_rs/뉴스 다일 누적 차단(라이브 누적의 실 전제).
- **gemini transient 503 + provider 명시 fallback 없음** — production-chat 경로 retry 배선(작은 부채).
- top_themes 친화 라벨링(C2 잔여) / 임계 캘리브레이션 다일 누적 후.

## 다음에 이어서 할 작업 (우선순위)
1. **오른쪽 뇌 roadmap 착수 결정** — 왼쪽 뇌 4/4 완성 → LEFT-BRAIN roadmap `done` 닫고 `RIGHT-BRAIN-*`(비중 Layer4 → 가상매매 → 시장대비 채점 → 복리) 신설. 사용자 본질("매일 도는 책임지는 페이퍼 트레이딩 데스크")의 미착수 절반. **사용자 사인오프 + roadmap SPEC 작성 필요**.
2. **dev cron 미작동 근본 해소** — 18:05·장전 적재가 서버 미상주 시 미발동. 수동 트리거 endpoint or 상주 운영 + 뉴스 일일 적재 cron 합류. 라이브 다일 누적의 실 전제.
3. **gemini transient 503 retry 배선** — `provider="gemini"` 명시 호출 503 재시도. `core/llm/client.py` 작은 부채.

## 커밋 상태
- 코드(us_macro.py/market_view.py/schema/snapshot_macro/collect_overnight_us/persona/config 2/tests 3) + SPEC 2 + probe + docs wrap-up → main 직접 커밋 + push (이 wrap-up 후반).
