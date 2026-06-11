---
date: 2026-06-11
topic: webapp 디자인 스펙 2벌 체제 — S-A 다크+Airbnb 풀셋 완성 (design-spec.pen) + 레퍼런스 6종 + 네이밍 탐색
status: partial
---

# 2026-06-11 · 디자인 스펙 S-A 풀셋 (3세션)

## 배경
shadcn 세팅 직후 사용자가 디자인 방향 자체를 재검토. getdesign 레퍼런스 비교 → 시황 슬라이스 4벌 스타일 샘플(S-A 다크+Airbnb / S-B Airbnb 라이트 / S-C Linear / S-D Coinbase) → **S-A·S-B 2개를 풀셋으로 보고 최종 결정**하기로. 파일 분리: `design-spec.pen`(S-A) / `design-spec2.pen`(S-B 예정). **핵심 판단: Pencil MCP filePath 무시 함정 재확인 → 사용자 탭 활성화 협업 + 고유 노드 유무로 활성 문서 검증하는 워크플로우 확립.**

## 한 일
- `webapp/design-refs/*.md` — getdesign 레퍼런스 6종 (airbnb·binance·coinbase·kraken·linear.app·revolut)
- `webapp/uiux-sample-draft` (에디터 저장본) — 시황 슬라이스 스타일 샘플 4벌 (S-A~S-D, 비교용 기록)
- `webapp/design-spec.pen` (464KB, **S-A 풀셋 완성·저장 확인**) — 작업 내역:
  - S-A 리스타일 15화면 (카드 #161616/#121212, 라운딩 12~20, 에이전트 5팀)
  - 가독성 스윕 2회 (본문 #C2C7CE·보조 #9AA0A8·부연 #7A8088 / 파랑 #6FBAFF·네이비칩 #3568BE — 사용자 "침침하다" 2회 피드백 수렴)
  - 성과 지표 6종 (승률·익절·손절·손익비·MDD·샤프) — 데스크 총합 + 계좌상세, PC·모바일 모두
  - 계좌상세 자산 곡선 카드 (PC=mdd4B 복제, 모바일=미니차트 복제)
  - 시황 수급 3열화 (코스피·코스닥·**K200 선물 박스 승격**), 모바일도 3줄
  - 모바일: 섹션 분리(강세 섹터/수급/자산군) + 업스케일(+2 폰트·패딩) + **2× 배율 확대**(전 수치 ×2, 폭 780, 프레임명 "(2× 배율)" — 구현 시 ÷2)
  - 채팅 보내기 우측 정렬(placeholder 텍스트 fill 화), 모바일 알림 색 도트(이모지→● 글리프), 텍스트 오버플로 20곳 래핑, 채팅 헤더 "wevelStock"→"채팅"
  - 00 정보구조 삭제(스펙에 불필요, uiux-sample-draft.pen 에 보존), 프레임 겹침 재배치
- `webapp/design-spec2.pen` — **S-A 최신본 복사 완료 (S-B 변환 베이스)**

## 검증 결과
- ✅ snapshot_layout problemsOnly 전 화면 — 텍스트 오버플로 0건 (차트 path 1~2px 비가시 아티팩트만)
- ✅ design-spec.pen 디스크 저장 확인 (406→464KB, 확장자 정상)
- ✅ 에이전트 격리: 활성 문서 검증(고유 노드 GGM65 부재 확인) 후 작업 — 타 문서 오염 0
- ⚠️ MCP 스크린샷/snapshot 신규 노드 렌더 버그 재현 (빈 프레임·+50 유령 오프셋) — 에디터 실화면은 정상, 사용자 육안 확인으로 대체

## S-B 라이트 변환 매핑표 (다음 세션 즉시 실행용)
배경 #0A0A0A→#FFFFFF · #121212→#F7F7F7 · #161616→#FFFFFF(+stroke #DDDDDD) · #0F0F0F→#F7F7F7 / 스트로크 #262626→#DDDDDD(행 #EBEBEB) / 텍스트 #FAFAFA→#222222 · #E6E8EB·#C2C7CE→#3F3F3F · #9AA0A8→#6A6A6A · #7A8088→#929292 / 파랑 #6FBAFF→#2563EB · #3568BE→bg#BFDBFE+text#1D4ED8 · #ABD4FF→#1D4ED8 / 그린 #34D399→#059669 · #6EE7B7→#047857 · #064E3B·#0F2A1F·#1E2A22→#ECFDF5(+#A7F3D0) / 레드 #F87171→#DC2626 · #7F1D1D→#FECACA / 앰버 #FBBF24→#B45309 · #27170A→#FFF7ED · #78350F→#FDE68A / 차트 목표선→#D97706·총자산→#059669·실현→#9CA3AF / CTA·로고 = Rausch #FF385C (S-B 샘플 정체성, 에메랄드 #10B981 대체)

## 미결 (네이밍)
wevelStock = 코드네임 확정 (서비스명 아님). 컨셉 = **파동+복리** (경제적 자유). 후보 1차(스노우볼·웨이브데스크 = "좋네" 그러나 상투적) → 2차(스웰·너울·겹·나선 = "더 이상해짐ㅋㅋ"). 기준: **흔하지 않으면서 별칭이 입에 확 붙을 것** ("프리즘 인사이트만한 게 없네"). 미정 — 다음 세션 재탐색.

## 다음에 이어서 할 작업 (우선순위)
1. **S-B 라이트 변환 (design-spec2.pen)** — 베이스 복사 완료. 사용자가 Pencil 에서 design-spec2.pen 탭 활성화 → 위 매핑표로 에이전트 스윕 (15화면, S-A 때와 동일 분담) → 두 파일 비교 → 최종 스타일 결정.
2. **서비스 네이밍 확정** — 파동+복리·입에 붙는 별칭. 결정 시 .pen 로고 텍스트 일괄 치환 + 향후 코드 표기 반영.
3. **PAPER-DESK-UX-001 `/spec-interview`** — 스타일 확정 후 SPEC 신설(RIGHT-BRAIN 연결) → Next.js 구현 (shadcn/ui 4.x + Tailwind v4 세팅 완료 상태, 모바일 수치 = .pen 표기 ÷2 주의).

## 커밋 상태
- 이 세션 선행 커밋: `ba384b4`(verified 게이트 wrap-up), `5526fdb`(shadcn+Tailwind v4)
- 본 wrap-up: design-refs + design-spec 2벌 + uiux-sample-draft(샘플 4벌) + docs → 커밋 예정
