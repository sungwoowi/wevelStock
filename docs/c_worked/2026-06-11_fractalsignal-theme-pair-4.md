---
date: 2026-06-11
topic: FractalSignal 네이밍 확정 + 다크/라이트 테마 쌍 완성 (S-B 변환·로고 마크·테마 토글·가상매매 용어·지수 라인·등락 종목 수)
status: completed
---

# 2026-06-11 · FractalSignal + 테마 쌍 완성 (4세션)

## 배경
S-A 풀셋 이후 연속 작업. **핵심 결정 2개**: ① 서비스명 = **FractalSignal** (사용자 작명 "프랙탈 시그널" → 한 단어 영문 확정. FractalWave 는 fractalwave.works 선점 — 웹 체크로 배제) ② S-A/S-B = 후보 비교가 아니라 **다크/라이트 테마 쌍** (수동+시스템 자동 전환, UI 토글 신설). wevelStock = 코드네임 유지.

## 한 일 (양쪽 .pen — 사용자 저장 확인 21:38/21:42)
### design-spec.pen (다크) — 사용자 피드백 연쇄 반영
- **용어 전면 교체**: "데스크"→"가상매매" 27곳 + 프레임명 3 (북극성 표어는 "가상매매 (페이퍼 트레이딩)" 자연화)
- **자산 곡선 차트 개편**: 기간 토글 1M·3M·6M·1Y·전체 5단 (PC 2곳+모바일 2곳 신설) / 성장 목표선 → **지수 라인** (가상매매 총합=코스피+나스닥, 계좌상세=코스피) + 레전드 교체
- **FractalSignal 로고**: 텍스트 8곳 치환 + **프랙탈 파동 마크** 7곳 (작은 파동→큰 파동→시그널 도트 한 획, Rausch #FF385C + 도트 화이트)
- **테마 토글**: PC 네비 7 ("🌓 시스템 ▾") + 모바일 헤더 7 ("🌓")
- **등락 종목 수 UI**: PC 참고 지표 카드 하단 (시장별 ▲─▼ 색 분리 + 비율 바) + 모바일 시황 카드. **데이터 체크 선행: KIS `inquire-index-price` `*_issu_cnt` 로 이미 매일 적재 중** (`market_macro_snapshot.advancing/unchanged/declining`, 코스피·코스닥 각각, source=kis_index) — 구현 시 신규 수집 0
### design-spec2.pen (라이트) — S-B 전면 변환
- 색 변환 ~930 노드 (화이트 캔버스·ink·헤어라인, CTA·로고=Rausch) + 16:17 복사본에 빠졌던 동기화 (용어·로고·차트 개편·**모바일 2× 재스케일**) + 매핑 외 색 3종 보정 (#FCA5A5·#FCD34D·#2A1216) + 로고 마크·테마 토글·등락 UI 미러링 (라이트 대비 색)

## 검증 결과
- ✅ snapshot_layout problemsOnly — 양 파일 실제 오버플로 0 (차트 path 비가시 클립·신규 노드 유령 오프셋 오탐만)
- ✅ FractalWave/FractalSignal 웹 선점 체크 (WebSearch — FractalWave 동명 서비스 실존, FractalSignal 없음)
- ✅ 등락 데이터 라이브 확인 (06-11: 코스피 ▲576 ─25 ▼320 / 코스닥 ▲1,219 ─59 ▼457 — UI 목업 수치로 사용)
- ⚠️ 에이전트 세션 한도 1회 (5pm 리셋, 재투입 멱등 완료) / Pencil 앱 재시작 시 MCP 재연결 필요 (`/mcp` Reconnect 로 해소)

## 미결 / 사용자 결정 대기
- **CTA 액센트 불일치**: 다크=에메랄드 #10B981 / 라이트=Rausch #FF385C. 로고가 Rausch 라 통일 권고 — 두 모드 보고 결정 (치환 5분)
- 미장 계좌 상세 화면의 지수 라인 = 나스닥/S&P (화면 자체가 미존재, SPEC 명시 사항)
- connectors/kis/client.py 수정 + tests/test_kis_token.py 신규 = **이 세션 작업 아님** (다른 창 추정) — 미커밋 보존, 사용자 확인 필요

## 다음에 이어서 할 작업 (우선순위)
1. **PAPER-DESK-UX-001 `/spec-interview` → Next.js 구현** — 디자인 스펙 쌍 완성으로 전제 충족. SPEC 명시 사항: 테마 = next-themes (light/dark/system, 현 shadcn dark 고정 해제) / 모바일 수치 = .pen ÷2 / 채팅 = team_outputs read+서술 1콜 (fan-out 금지) / 등락 수 = `market_macro_snapshot` read / 신규 수집 (WTI·브렌트·야간선물, 알림 영속 테이블) / 미장 계좌 지수 라인.
2. **CTA 액센트 통일 결정** — 에메랄드 vs Rausch, 결정 즉시 해당 파일 일괄 치환.
3. **오른쪽 뇌 verified 게이트 모니터링 (organic)** — WEALTH 스냅샷 ≥5영업일(~06-16) / AM 체결 ≥1 / GUIDANCE 청산 ≥3.

## 커밋 상태
- 본 wrap-up 에서 .pen 2 + docs 커밋 (kis client 변경은 제외·보존)
