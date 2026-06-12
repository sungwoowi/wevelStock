---
date: 2026-06-12
topic: CTA/브랜드 액센트 결정 — 통일 안 함, 테마별 듀얼 액센트 확정
status: completed
plan_file: C:\Users\HOME\.claude\plans\wobbly-jingling-puppy.md
---

# 2026-06-12 · CTA 액센트 = 테마별 듀얼 액센트 확정

## 배경
RESUME 디자인 미결 항목 "CTA 액센트 통일(다크 에메랄드 vs 라이트 Rausch)"을 닫기 위한 짧은 결정 세션. 처음엔 "하나로 통일하느냐"의 문제로 잡았으나, 사용자가 "테마에 어울리는 색이면 되는 거 아니냐"고 되물으며 전제를 흔들었다. **핵심 판단: 정상적 테마 대응은 같은 hue 톤 조정이지만, 사용자가 다크 실물(핑크 로고 + 에메랄드 버튼)을 직접 보고 "작은 선 로고라 안 거슬린다"고 판단 → 통일하지 않고 테마별 의도된 듀얼 액센트로 확정.** 디자인 파일 변경 0, 결정만 문서화.

## 확정 결정
- **통일 안 함 — 테마별 듀얼 액센트 (deliberate)**:
  - 라이트(`webapp/design-spec2.pen`): 핑크 무드 — 로고·CTA 모두 Rausch `#FF385C`
  - 다크(`webapp/design-spec.pen`): 에메랄드 강조 — 핑크 로고(`#FF385C` stroke, 8곳) + CTA `#10B981` + 가상 배지(`#064E3B`/`#6EE7B7`)
- 라이브 read 로 실제 색 확인(추측 아님). 다크 CTA 는 이미 에메랄드, 로고만 핑크 — 사용자가 이 상태를 그대로 채택(옵션 b).
- Pencil MCP 활성 탭 함정 재현: `filePath` 지정해도 활성 탭만 읽음 → 다크 파일 확인 위해 사용자가 탭 활성화 후 재read 필요했음([[reference-pencil-mcp-active-tab]] 패턴 그대로).

## 한 일
- `docs/RESUME.md` — 현재 위치 갱신(CTA 결정) + 미결 표기 `미결 → ✅ 해소` + Top 3 에서 CTA 항목 제거(이제 1.PAPER-DESK-UX / 2.게이트 모니터링) + 해소 괄호줄에 기록.
- `memory/feedback_design_visual_preferences.md` — 항목 5 신설(테마별 듀얼 액센트 확정) + description 갱신. PAPER-DESK-UX 구현 시 next-themes 액센트 분기(다크 에메랄드/라이트 Rausch) 참조용.
- 디자인 `.pen` 변경 **없음**.

## 검증 결과
- ✅ 라이브 read 로 양 파일 실제 색 확인 (design-spec.pen 다크: 로고 stroke `#FF385C`, CTA fill `#10B981` / design-spec2.pen 라이트: CTA fill `#FF385C`).
- ✅ 문서뿐이라 코드/`.pen` 검증 불필요. RESUME 미결 표기 해소 확인.

## 의도적으로 안 한 것
- **다크 로고 에메랄드 치환(옵션 a) 안 함** — 사용자가 핑크 로고 현 상태를 선호. 8곳 stroke 치환 보류.
- `webapp/design-spec2.pen` M 상태 커밋 안 함 — 우리가 의도한 변경 0이라 에디터 자동저장 아티팩트로 판단, 커밋 분리(사용자 판단에 맡김).

## 다음에 이어서 할 작업 (우선순위)
1. **PAPER-DESK-UX-001 `/spec-interview`** — 디자인 쌍·네이밍(FractalSignal)·CTA 결정 모두 완료로 전제 충족. SPEC 신설(generates=webapp/src/app/*) → Next.js 구현. 원 Top 1 복귀, RIGHT-BRAIN roadmap 연결.
2. **오른쪽 뇌 verified 게이트 모니터링 (organic)** — WEALTH 스냅샷 ≥5영업일(~06-16) / ACCOUNT-MANAGER 체결 ≥1 / GUIDANCE 청산 ≥3. 매일 18:05 cron 누적.
3. **regime 히스테리시스 (백로그)** — 경계 요동 점검, 급하지 않음.

## 커밋 상태
- 본 wrap-up 에서 docs 1커밋(`docs: wrap-up ...`) + main push. `webapp/design-spec2.pen` 은 의도적 제외.

## 맥락 재진입 힌트
- "CTA 통일"은 **닫힌 항목**. 다음 세션이 이걸 다시 미결로 들추면 안 됨 — 테마별 듀얼 액센트가 최종.
- PAPER-DESK-UX 구현 시 액센트 토큰: 다크 = 에메랄드 `#10B981`, 라이트 = Rausch `#FF385C`. next-themes 로 분기.
