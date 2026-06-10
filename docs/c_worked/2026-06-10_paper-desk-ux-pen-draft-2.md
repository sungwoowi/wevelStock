---
date: 2026-06-10
topic: PAPER-DESK-UX 디자인 드래프트 (.pen) — webapp 전체 IA 확정 + 계좌 시드 1억
status: completed
plan_file: C:\Users\HOME\.claude\plans\valiant-riding-globe.md
---

# 2026-06-10 (2) · PAPER-DESK-UX .pen 드래프트 + 시드 1억

## 배경
오른쪽 뇌 화면(PAPER-DESK-UX) 착수. 사용자가 SPEC 전에 Pencil(.pen) 시각 드래프트로 먼저
핑퐁하길 원해 캔버스에서 IA 를 라이브로 굳혔다. **핵심 판단: 본질 정렬 3원칙(채팅=백단 0 노출 /
데스크=책임지는 가상 4계좌 / 코드 라벨 금지 자연어)을 화면 구조로 번역**. 세션 중 사용자 결정
다수 반영(아래).

## 확정된 IA (사용자 결정 누적)
- **탭 5축 = 시황(홈) · 데스크 · 채팅 · 뉴스 · 알림** (모바일 탭 5개 제한 기준).
  **가이드 = 헤더 ❔ 버튼** 진입(탭 아님). **브리핑 탭 폐지 → 시황에 흡수**(히스토리 선택 →
  그 시점 대시보드 + 브리핑 서술 두 레이어 — 데이터 원천 동일, 중복 제거).
- **계좌 시드 1,000만 → 1억** (고가 종목 몇 개면 1천만 소진 — backend 실반영).
- 분석가는 화면에 비노출(채팅 "근거 보기" 안에서만) — production 철학 유지.
- 알림 6종 체계: 🔴위험(변곡점 `is_macro_inflection` 재사용·VIX동결·MDD·손절임박) /
  🟢체결·청산·새권고 / 🔵계좌 안심 알리미(매일 1회)·브리핑·뉴스 촉매. 정책 = 🔴즉시·🟢발생시·🔵정량.
- 관심 종목(와치리스트)은 **보류** (사용자 결정).

## 한 일
- `webapp/uiux-sample-draft.pen` — **PC 7화면 + 모바일 6화면** (Pencil MCP batch_design):
  00 정보구조 보드 / 01 시황(홈: 좌측 히스토리·한줄평·지표 12종(값·변동액·%·기준시각 4요소)·
  거래대금 상위·강세 섹터·매크로 자산군·수급 5주체·브리핑 펼치기) / 02 데스크(자산 곡선 2시리즈+
  연18% 목표선 path·KPI(누적+승률+건수 묶음)·4계좌 카드) / 02a 계좌 상세(계좌 탭·요약 5칸·보유
  테이블·회차 사다리 체결 내역·매수 대기·이익실현) / 03 채팅 / 04 뉴스(단기 테마·장기 내러티브·
  피드) / 05 알림(필터 칩·오늘/어제 그룹) / 06 가이드(목표·동작구조 6단계·분석가9·7계명·용어사전)
  + M-01~06 모바일(하단 탭바·테이블→카드 변환).
- `config/accounts.yaml` — 4계좌 `seed_krw` 1억 + 주석. 시드 권위=config(DB는 비중 %만)라
  이것만으로 전파. 라이브 DB 체결·스냅샷 0 확인 → 마이그레이션 불요.
- `tests/test_account_{api,portfolio,paper_trading,compounding}.py`·`test_wealth_api.py` —
  시드 의존 단언 13건 1억 기준 갱신.
- 리서치: prism-insight(GitHub+라이브)·investing.com → 반영 ①지표 4요소 포맷 ②KPI 정직 묶음
  (누적+승률+건수). 백로그: 경제 캘린더·시즌제·급등 감지 알림.

## 검증 결과
- ✅ 전체 회귀 **1121 passed** (시드 변경 후).
- ✅ 캔버스 프레임 좌표 무결(snapshot_layout, 무겹침) + 사용자 시각 확인("좋네").
- ⚠️ 디자인 정본: 에디터가 `webapp/uiux-sample-draft`(확장자 없음, 406KB)에 저장 →
  wrap-up 에서 `.pen` 으로 복사 동기화. **다음 Pencil 열 때 `.pen` 파일을 열 것**.

## 사고/도구 함정 (재발 방지)
- **Pencil MCP 는 `filePath` 인자를 무시하고 "활성 탭" 문서에 쓴다** — 작업 중 사용자가
  momentum(사주앱) 탭을 보고 있어 그 문서에 프레임이 들어감 → 전부 롤백(디스크 무수정 확인).
  교훈: Pencil 작업 전 `get_editor_state` 로 활성 문서 확인 + 사용자에게 탭 고정 요청.
- 스크린샷/export 가 "최근 생성 노드"를 렌더 안 하는 버그 — 데이터는 정상, 검증은
  snapshot_layout(기계) + 사용자 육안으로 대체.

## 다음에 이어서 할 작업 (우선순위)
1. **PAPER-DESK-UX-001 `/spec-interview`** — 확정 IA(.pen) 기반 SPEC 신설 + RIGHT-BRAIN roadmap
   연결. generates=webapp/src/app/{market,desk,chat,news,alerts}/* + 차트 라이브러리 선정.
   구현 전제 신규 수집 2건 명시: WTI·브렌트·야간선물(yfinance 확장) / 알림 영속 테이블.
2. **오른쪽 뇌 verified 마감** — 라이브 청산 누적(cron 시간 영역), 시장 신호 시 자동.
3. **regime 히스테리시스** — 변곡점 플래그 빈발 방지(`collectors/market_macro.py` sticky 밴드).

## 커밋 상태
- 코드(config+tests)+`.pen`+wrap-up docs → main 직접 + push (본 wrap-up 에서).
