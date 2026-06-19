---
date: 2026-06-19
topic: 노출·알림 단의 종목코드 전부 종목명으로 (텔레그램+가상매매 계좌)
status: completed
plan_file:
---

# 2026-06-19 · 노출·알림 단 종목코드 → 종목명

## 배경
사용자가 텔레그램 알림과 가상매매 각 계좌 화면에서 "005935 3차 — 20.8만 도달 시
자동 체결" 처럼 **종목코드가 그대로 노출**되는 걸 발견("코드는 내가 봐도 알 수가
없다"). systematic-debugging 으로 근본 원인 추적: 종목명 리졸버(`get_stock_name`
+`KR_TICKER_TO_NAME`)가 일부 경로에만 배선돼 있었고 누락 경로는 코드로 폴백.
005935 같은 코드도 정적 매핑에 이미 존재(삼성전자우) — 단지 리졸버를 안 거쳤을 뿐.
핵심 판단: 땜질 금지, **중앙 리졸버 1개를 만들어 모든 노출·알림 단이 통과**하게.

## 한 일
- `collectors/universe_membership.py` — **중앙 진입점 `resolve_stock_name(ticker, hint)` 신설**: hint(이미 이름) → 멤버십 DB → 정적 매핑 → 최후에만 코드 폴백.
- `core/account/desk_view.py` — `_resolve_display_name` 을 리졸버 위임으로 축소 + `_with_name` 헬퍼 + `get_account_pending`(빈문자열/raw→리졸버)·`get_account_closed`·`recent_fills` 에 `display_name` 주입.
- `core/account/holdings.py` — `get_holdings` 각 보유에 `display_name` 추가(보유중·회차헤더 코드 차단).
- `core/signal/auto_signal.py` — 🟢 매매 알림 제목 `이름(코드)` → **이름만** + 리졸버 사용.
- `core/briefing/render.py` — 브리핑 보유/관심 의견 `이름 (코드)` → **이름만**(텔레그램 발송).
- `server/telegram/commands.py` — `/계좌` 보유 목록 `pos['ticker']` → `display_name` 우선.
- `webapp/src/lib/api.ts` — `Holding`·`ClosedFill`·`FillEntry` 타입에 `display_name` 추가.
- `webapp/src/components/desk/AccountDetail.tsx` — 보유중·회차헤더·이익실현 `display_name || ticker`.
- `webapp/src/components/desk/DeskBoard.tsx` — 매매일지 `display_name || ticker`.
- `webapp/src/app/production-chat/page.tsx` — 디버그 칩 `이름 (코드)` → 이름만.
- `tests/test_account_desk_view.py` — 리졸버 우선순위 + 매수대기/보유/청산/일지 종목명 테스트 5건 추가.
- `tests/test_auto_signal.py` — 알림 제목 코드 부재 단언으로 교체(`삼성전자` in, `005930` not in).

## 의도적으로 안 한 것
- **LLM 입력 컨텍스트는 코드 병기 유지**: `config/analyst_subtasks.yaml`(분석가 sub-task 프롬프트)·`collectors/snapshot.py`(시황 md)·`auto_signal._signal_directive`(전략가 지시문). 화면이 아니라 모델 입력이라 코드가 정확도에 도움 — "노출단/알림단"만 정리.
- R&D probe 스크립트(`_trade_plan_probe` 등) 콘솔 출력은 그대로(개발자 디버그용).

## 검증 결과
- ✅ 전체 `pytest` **1344 passed** (신규 테스트 7건 포함, 회귀 0).
- ✅ webapp `tsc --noEmit` 클린(타입 에러 0).

## 다음에 이어서 할 작업 (우선순위)
1. **매핑 밖 종목 폴백 강화** — 정적 매핑·멤버십 어디에도 없는 종목은 여전히 코드 노출(최후 폴백). 실사용에서 코드로 보이는 사례 발견 시 정적 매핑 추가 or 멤버십 백필(universe daily refresh) 점검. 현재는 거래대금 상위·주요 종목 전부 이름.
2. **데스크 "지켜보는 권고" actionable 정리** — watchlist 페이지 자리잡았으니 데스크 섹션을 actionable 권고만 남기게 개선(사용자 지시 2026-06-16, watchlist 메모 FOLLOW-UP).
3. **종목 상세 + 채팅 prefill** — watchlist/데스크에서 종목 클릭 → 상세 + 채팅 자동 채움(관심종목 페이지 후속).

## 커밋 상태
- wrap-up 시점 커밋 예정 (코드 12파일 + 테스트 + 본 로그/RESUME/SESSIONS).
