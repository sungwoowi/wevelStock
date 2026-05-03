---
date: 2026-05-03
topic: 5-Layer 도메인 아키텍처 합의 (모바일 토론, 코드 변경 0)
status: completed
plan_file: C:\Users\HOME\.claude\plans\snazzy-kindling-willow.md
---

# 2026-05-03 · 5-Layer 도메인 아키텍처 합의

## 배경

`/resume` Top 1 candidate 가 "canon 4 파일 인터뷰" 였으나, 사용자가 모바일 환경 → 자료 업로드 제한 → **아키텍처 도메인 구조 토론** 으로 즉시 전환. 사용자가 던진 "5 학습부 (원칙·실전·장기생존·종목분석·뉴스) + 투자성격군별 조언" 의 큰 그림을 7라운드 인터뷰로 정형화하여 **5-Layer 도메인 모델** 합의 도출. 코드 변경 0, 합의 산출만.

## 한 일

### 합의된 5-Layer 도메인 모델 (이번 세션 핵심 산출)

```
Layer 1 — 학습부 (5)         : 원칙부 · 실전부 · 장기생존부 · 종목분석부 · 뉴스부
Layer 2 — 분석가 (5, 1:1)    : 원칙수호자 · 매매코치 · 거시분석가 · 종목분석가 · 뉴스큐레이터
Layer 3 — 전략가 (3, horizon): 단타 · 스윙 · 중장기
Layer 4 — 계좌관리자 (1)     : 4 계좌 (국장/미장 × 단/중장) + 자산배분(분산) 흡수
Layer 5 — 출력 채널          : 시간대 브리핑 · 종목 추천 · 매매 알림 · 매매일지
```

### 합의 산출 파일

- `C:\Users\HOME\.claude\plans\snazzy-kindling-willow.md` 신규 — 5-Layer 모델 + M1 착수 계획 (PC 복귀 시) + manifest list 기반 스키마 보강
- `C:\Users\HOME\.claude\projects\C--Users-HOME-claude-wevelStock\memory\project_5layer_model.md` 신규 — 5-Layer 모델 메모리 (다음 세션 즉시 인지)
- `C:\Users\HOME\.claude\projects\C--Users-HOME-claude-wevelStock\memory\MEMORY.md` — 인덱스에 새 entry 추가

### 합의된 핵심 원칙

1. **plugin 패턴**: 새 학습부/분석가/전략가 = 폴더 + `manifest.yaml` 드롭. 5/5/3/1 은 starting count.
2. **분산투자 = 계좌관리자 흡수** (Layer 3 X, Layer 4 모드)
3. **분화는 trigger 시**: 빈 그릇 미리 만들지 X. 운용 중 결함 발견 시 분화
4. **분석가 ↔ 학습가 1:1 매핑** (단순 책임 경계). manifest list 기반으로 미래 1:N 확장 무비용
5. **비용 신경 X**: 추정 월 1~3만원 (Sonnet 4 + cache). 비용 모니터링 hook 만 둬서 자가 보고

## 검증 결과

- ✅ ExitPlanMode 사용자 승인
- ✅ 7라운드 인터뷰 (Top3 선택 → 페이스 → 학습부 개수 → 모델 일치 → 1:1 매핑 의문 → 전략가 수 → 모델 확정 → manifest 확장성) 모두 사용자 답변 정합
- (코드 변경 0 → pytest 미실행)

## 의도적으로 안 한 것

- **canon 4 파일 인터뷰** (모바일 자료 업로드 제한) — M2 별도 세션
- **M1 코드 작업** (PC 복귀 후로 이연) — `knowledge/canon/` 폴더 재구조화 + `manifest.yaml` 스키마 + `compose.py` 수정, 1.5~2h
- **docs/STRUCTURE.md, RUNTIME.md, CLAUDE.md 의 5-Layer 모델 정식 등재** — M1 코드 작업과 묶어서
- **선물 수급 5주체 확장 / Phase 3 close+RAG** — 직전 세션 백로그 그대로 유지

## 맥락 재진입 힌트

- **다음 세션 = M1 (PC 복귀)**: 폴더 위치 결정 (`teams/` vs 신규 `agents/analysts/`), 기존 4 placeholder 파일 마이그레이션 매핑, `manifest.yaml` list 기반 스키마 확정, `core/knowledge/compose.py` `load_shared_canon()` 5 학습부 폴더 재귀 읽기 수정
- **분산투자는 종목 추천 X, 자산배분 = 계좌 단위 메타 결정** — Layer 4 계좌관리자 안의 한 모드. 새 학습부 후보 아님
- **분석가 5명 = 학습부 5개 1:1 매핑** = 각 분석가가 본인 영역 학습부만 읽음. analyst.md 1개 → 5개로 split 작업이 M3
- **horizon 정밀도 우선**: 사용자가 단타/스윙/중장기 명시 분리 요구. 단타+스윙 합치지 X
- **manifest list 기반 시작**: `analysts: [...]` / `reads: [...]` 시작은 1개만, 미래 N개 확장 무비용

## 다음에 이어서 할 작업 (우선순위)

1. **M1 — Layer 1+2 폴더 구조화** (PC 복귀 시 1.5~2h) — `knowledge/canon/` flat 4 파일 → 5 학습가 계층 폴더 재구조화 + 분석가 페르소나 디렉토리 위치 결정 (`teams/` 활용 vs 신규 `agents/analysts/`) + `manifest.yaml` list 기반 스키마 확정 + `core/knowledge/compose.py` 수정. pytest 60 passed 유지 목표. 자료 채우기는 M2 별도.
2. **M2 — 학습부 자료 채우기** (모바일/PC 둘 다 가능, 인터뷰 1~2h/파일) — 5 학습부 중 우선순위 (추천: 장기생존부 = 거시 시각이 다른 학습부의 기반). 코드 변경 0, markdown Q&A.
3. **M3 — 분석가 5명 페르소나 분화** (PC 2~3h) — `analyst.md` 1개 → 5개로 split. 각 페르소나에 본인 학습부만 읽도록 binding. 5-Layer 모델 docs 정식 등재 (STRUCTURE.md/RUNTIME.md/CLAUDE.md) 함께.

## 커밋 상태

- 코드 변경 0 — wrap-up docs (이 파일 + RESUME.md + SESSIONS.md) 만 1 커밋 예정
- `.claude/settings.json` modified / `bash.exe.stackdump` / `rag_docs/` 모두 이번 세션 무관 → 미스테이지 보존
- 5-Layer 모델 합의는 plan 파일 + memory 에 영구 보관 (다음 세션 즉시 인지)
- main 브랜치 직접 작업 (worktree 분기 없음) → FF merge 불필요
