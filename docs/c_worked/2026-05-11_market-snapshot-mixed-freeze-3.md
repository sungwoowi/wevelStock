---
date: 2026-05-11
topic: market_snapshot mixed 테스트 시각 freeze (사전 부채 보강)
status: completed
plan_file: C:\Users\HOME\.claude\plans\bright-stargazing-moonbeam.md
---

# 2026-05-11 · market_snapshot mixed 테스트 시각 freeze

## 배경

직전 두 세션 (Phase 2 M2 + M3) 로 KNOWLEDGE-SYNC-001 Phase 2 풀세트 = 프로토타입 1차 동작점 도달. M3 작업과 무관하게 식별만 해두고 미뤘던 사전 부채 1건 (`test_render_data_source_line_mixed`) 보강 — `kr/us_threshold_seconds(now_kst)` 가 가장 최근 cron 발동 시각과의 차로 임계를 계산하는데, 테스트가 시각 freeze 없이 실행돼 환경(시각)에 따라 fresh/stale 판정이 흔들려 깨졌다. 베이스라인 -1 (134/135) 회복이 목적.
핵심 판단: 모듈의 `datetime` 참조를 통째로 fake class 로 monkeypatch — `build_market_snapshot` 안의 `datetime.now(_KST)` 호출이 단일이라 부수효과 없음. snapshot.py 손 안 댐.

## 한 일

- `tests/test_market_snapshot.py` (L745~) — `test_render_data_source_line_mixed` 에 `_FrozenDateTime(datetime)` 클래스 + `monkeypatch.setattr(snap_mod, "datetime", _FrozenDateTime)` 추가. freeze 시각 = **2026-05-12 (화) KST 20:30** → KR threshold ~6h (kr_age 3일 stale → fetch), US threshold ~13.5h (us_age 12h fresh → DB). docstring 에 의도 명시.

## 검증 결과

- ✅ 단일 테스트 통과: `pytest tests/test_market_snapshot.py::test_render_data_source_line_mixed -v` → PASSED (1.01s)
- ✅ 전체 회귀 통과: `pytest tests/ -q` → **135 passed** in 27.35s (이전 134 → +1, 회귀 0)
- ✅ TESTING=1 + PYTHONUTF8=1 + PYTHONIOENCODING=utf-8 environment

## 의도적으로 안 한 것

- `collectors/snapshot.py` 에 `_now_kst()` helper 분리 — production 코드 손 안 대고 monkeypatch 만으로 의도 달성. helper 분리는 다른 호출처 생길 때 자연 도입.
- freezegun 의존성 추가 — 같은 결과를 10줄 fake class 로 달성, 외부 의존성 추가 불필요.
- 다른 `test_render_data_source_line_*` 들의 시각 freeze — 현재 `full_fetch` / `both_fresh` 등은 시각 무관 path 라 깨지지 않음. 필요해지면 같은 패턴.

## 맥락 재진입 힌트

- **freeze 시각 결정 식**: weekday<5 + now ≥ today_700(KST) 면 `_last_expected_us_cron` 이 오늘 07:00 KST 반환. now-07:00 = us threshold. us_age(12h) 가 threshold 이하면 fresh. 따라서 now ≥ 20:00 KST 평일이면 us_age 12h fresh 가 안정적으로 성립.
- **monkeypatch 모듈 단위 datetime 패치 패턴**: `from datetime import datetime` 으로 import 한 모듈은 `<module>.datetime` 이 모듈 attribute. `setattr(<module>, "datetime", FakeCls)` 로 갈아끼우면 해당 모듈 내 호출만 영향. 다른 모듈은 자기 import 본위라 무관.
- **fake class 는 datetime subclass**: `class _FrozenDateTime(datetime)` 으로 정의하면 isinstance/생성자 호환 + `now()` 만 override. snapshot.py 안에 datetime 생성자 호출 없어 안전하지만, 패턴 자체는 다른 모듈에도 응용 가능.

## 다음에 이어서 할 작업 (우선순위)

1. **M3 분석가 분화 SPEC 작성** (3~5 세션) — **프로토타입 가동 핵심**. 9 분석가 페르소나 8-섹션 portable 양식. 자료 있는 4명 (원칙수호자/트레이더/종목분석가/자산전략가) → 자료 0 시드 5명 (시장상태/종목선정/매매저널/수급/뉴스). 페르소나의 `canon_categories: [<dept>/<category>, ...]` 가 Phase 2 자동 sync 와 결합 동작 확인 시점. 자산전략가 1명 → 4명 즉시 확장.
2. **stock-analysis dept 첫 인덱싱 + 검증** (~1 세션) — 어댑터 5종 (md/txt/pdf/xlsx/png) 다 굴리는 첫 사례. `just knowledge-sync stock-analysis` 또는 reference drop 자동 sync. xlsx sheet 분리 여부 실 자료 (`4.로그차트_advanced/`) 보고 결정. retrieve smoke 4건 + 카테고리 분포 검증.
3. **streaming 토글 UI + AbortController** (~1.5h) — webapp 의 streaming on/off 토글 + 응답 도중 cancel 버튼. default ON 유지하되 회귀 옵션 + 응답 길어질 때 사용자 중단 가능. analyst-chat page 의 fetch ReadableStream 부분에 AbortController 결합.

## 커밋 상태

- `a10f651 fix(tests): freeze now_kst in test_render_data_source_line_mixed` — push 완료
- wrap-up commit (이 파일 + RESUME + SESSIONS) 별도 진행 예정
