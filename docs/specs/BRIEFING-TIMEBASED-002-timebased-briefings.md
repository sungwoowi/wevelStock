---
spec_id: BRIEFING-TIMEBASED-002
title: 컨텐츠 성격별 3종 브리핑 — 장전/장중/장후 + 시간 validation + RAG
team: shared
type: feature
status: draft
version: 1
owner: platform
generates:
  - pipelines/market_briefing/manifest.yaml
  - pipelines/market_briefing/stages/__init__.py
  - pipelines/market_briefing/stages/collect_kr_market.py
  - pipelines/market_briefing/stages/analyze.py
  - pipelines/market_briefing/stages/persist.py
  - pipelines/market_briefing/stages/notify.py
  - pipelines/market_briefing/prompts/briefing.md
  - pipelines/close_briefing/manifest.yaml
  - pipelines/close_briefing/stages/__init__.py
  - pipelines/close_briefing/stages/collect_kr_market.py
  - pipelines/close_briefing/stages/load_today_briefings.py
  - pipelines/close_briefing/stages/analyze.py
  - pipelines/close_briefing/stages/persist.py
  - pipelines/close_briefing/stages/notify.py
  - pipelines/close_briefing/prompts/briefing.md
  - collectors/kr_indices.py
  - collectors/kr_sectors.py
  - collectors/kr_leading_stocks.py
  - core/knowledge/ingest.py
  - tests/test_market_briefing.py
  - tests/test_close_briefing.py
  - tests/test_briefing_validation.py
modifies:
  - server/api/briefings_on_demand.py
  - server/telegram/commands.py
  - server/telegram/bot.py
  - core/briefing/render.py
  - core/briefing/parts_store.py
  - core/knowledge/retrieve.py
  - pipelines/morning_pre/stages/analyze.py
  - docs/RESUME.md
depends_on:
  - BRIEFING-ON-DEMAND-001
contracts:
  - name: briefing-part-v1
    version: "1.0"
---

# BRIEFING-TIMEBASED-002: 컨텐츠 성격별 3종 브리핑

## 목적

하루 투자 판단 사이클의 **세 지점** 에서 각기 다른 성격의 브리핑을 제공한다. 세 브리핑이 누적되면 적중률 채점 + 도메인 고도화의 기반이 완성된다.

## 배경 / 문제

BRIEFING-ON-DEMAND-001 v1 은 **단일 파이프라인(morning_pre)** 의 공통 플랫폼을 증명했다. 하지만:

- **장중** 에 코스피/코스닥이 어떻게 흐르고 있는지 확인할 수단 없음
- **장 마감 후** 오늘 예상이 실제와 일치했는지 채점 못함 → LLM 판단 품질 개선 근거 부재
- `user_want_spec.md` 의 "도메인 고도화 Agent" 는 이 채점 데이터를 입력으로 가정

## 핵심 재정의 (중요)

**이것은 "시간대별 라우팅" 이 아니라 "컨텐츠 성격별 3종 브리핑"** 이다. 시간은 단순 validation 레이어.

| 브리핑 | 컨텐츠 성격 | LLM 해석 비중 |
|---|---|---|
| `/briefing_pre` | 준비 — 전날·거시·뉴스·보유·신규후보 | 높음 (시나리오 생성) |
| `/briefing_now` | 관찰 — 실시간 시장 정보성 데이터 | 낮음 (요약 수준) |
| `/briefing_close` | 회고 + 학습 — 예상 vs 실제 + 해석 + 예측 | 매우 높음 (RAG) |

## 용어

| 용어 | 의미 |
|---|---|
| **Pre 브리핑** | 장 시작 전 준비 — `morning_pre` 파이프라인 |
| **Now 브리핑** | 장중·장후·프리장 실시간 시장 관찰 — `market_briefing` 파이프라인 (신규) |
| **Close 브리핑** | 장 마감 후 종합 해석 — `close_briefing` 파이프라인 (신규, RAG) |
| **Scheduled run** | cron 스케줄 트리거 — `run_id` suffix `#sched-<hex>` |
| **Manual run** | 봇/API 수동 트리거 — `run_id` suffix `#manual-<hex>` |

## 스코프

### 포함 (v1 MVP)
- `pipelines/market_briefing/` 신규 — 한국 시장 실시간 팩터 수집 + 최소 LLM 요약
- `pipelines/close_briefing/` 신규 — 당일 브리핑 종합 + RAG 기반 해석
- 한국 시장 collectors 3종 (indices / sectors / leading_stocks)
- 봇 명령어 3종 (`/briefing_pre`, `/briefing_now`, `/briefing_close`) + `/help` 업데이트
- 시간 validation (API 레벨 구현)
- RAG ingestion 파이프라인 (canon → Chroma)
- 렌더러 2종 (`render_market_briefing`, `render_close_briefing`)

### 제외 (Non-goals in v1)
- 적중률 자동 채점 집계 리포트 (별도 SPEC 예정)
- 과거 N 일 누적 브리핑 비교 조회
- 웹앱 UI — API 만 공개
- Now/Close 브리핑의 과거 run 재조회 (v1 에선 latest only)
- 주간/월간 롤업 브리핑

## 3 파이프라인 상세

### `/briefing_pre` → `morning_pre` (기존 확장)

기존 morning_pre 를 그대로 사용. Validation 로직만 추가.

**Validation**:
- 현재 시각 `< 09:00 KST` → 실시간 새 run 생성 가능 (현 동작 유지)
- 현재 시각 `≥ 09:00 KST` → **당일 09:00 이전 마지막 run 을 재전송**. 신규 생성 금지.
  - 텔레그램 메시지 상단에 `⏰ 장 시작 전 데이터 기준 (HH:MM 생성)` prefix
  - 오늘자 09:00 이전 run 이 없으면 → "오늘 장전 브리핑이 생성되지 않았습니다" 안내

### `/briefing_now` → `market_briefing` (신규)

**수집 데이터**:
- KOSPI / KOSDAQ 지수 현재가 + 등락률 + 거래대금
- 섹터별 등락률 순위 Top 10 (상승 / 하락)
- 주도주 리스트 — 시총 대비 상승률 + 거래대금 상위 교집합 Top 5
- 외국인/기관/개인 수급 (가능하면)

**LLM 해석**:
- 최소 수준 — "오늘 섹터 순환 방향 한 줄 요약" 정도
- 비용 목표: $0.0005 이하 (morning_pre 의 1/3)

**Validation**:
- `< 09:00 KST` → 거부 (`/briefing_pre 를 사용하세요`)
- `09:00~09:20 KST` → 경고 prefix `⚠️ 장 시작 직후라 지표 신뢰도 낮음`
- 그 외 (장중, 장후, 프리장, 새벽) → 항상 실시간 새 run. DB 60초 캐시는 적용 (BRIEFING-ON-DEMAND-001 A 기능)

**스케줄**: 없음 (on-demand only). 사용자가 궁금할 때만 호출.

### `/briefing_close` → `close_briefing` (신규 + RAG)

**Stages**:
1. `collect_kr_market` — market_briefing 과 동일 collector 재사용 (장 마감 시점 스냅샷)
2. `load_today_briefings` (신규) — 오늘자 `briefing_parts` 에서 `morning_pre` + `market_briefing` run 들 모두 로드
3. `analyze` — 종합 프롬프트:
   - 입력: (a) 오늘 장전 예상(시나리오, bias, confidence) (b) 오늘 장중 스냅샷들 (c) 현재 장 마감 팩터 (d) **RAG 컨텍스트** (knowledge/canon 기반)
   - 출력 스키마: `{ prediction_review: {expected, actual, match_score}, market_interpretation: str, next_outlook: {bias, key_factors}, principles_check: {...} }`
4. `persist` — briefing_parts 에 3 파트 저장 (review / interpretation / outlook)
5. `notify` — 텔레그램 3분할

**RAG 설계**:
- `core/knowledge/ingest.py` (신규) — `knowledge/canon/*.md` 를 청크 단위로 Chroma 에 인덱싱
- `core/knowledge/retrieve.py` 는 이미 skeleton 존재. 완성 필요
- analyze stage 가 당일 상황 키워드로 retrieve 호출 → top-k 청크를 프롬프트에 주입
- knowledge 디렉토리가 비어있으면 RAG 없이 동작 (graceful degradation)

**Validation**:
- `< 15:30 KST` → 거부 ("장 마감 후에만 호출 가능")
- scheduled cron: `45 15 * * 1-5` (15:45, 종가 안정화 후)

## Validation 요약표

| 시각 KST | `/briefing_pre` | `/briefing_now` | `/briefing_close` |
|---|---|---|---|
| 00:00~06:59 | 실시간 | 실시간 (새벽 프리장) | 거부 |
| 07:00 cron | scheduled run | — | — |
| 07:00~08:59 | 실시간 | 실시간 | 거부 |
| 09:00~09:19 | 보관본 재전송 | 경고 prefix | 거부 |
| 09:20~15:29 | 보관본 재전송 | 실시간 | 거부 |
| 15:30~15:44 | 보관본 재전송 | 실시간 | 실시간 |
| 15:45 cron | — | — | scheduled run |
| 15:45~23:59 | 보관본 재전송 | 실시간 | 실시간 |

## API 변경

### 신규 엔드포인트 없음

BRIEFING-ON-DEMAND-001 의 `/api/briefings/{pipeline_id}/...` 가 그대로 3개 파이프라인 수용.

### `briefing_run` 확장

`server/api/briefings_on_demand.py::briefing_run` 내부 분기 추가:

```python
if pipeline_id == "morning_pre" and _now_kst().hour >= 9:
    # 09:00 이후는 당일 아침 보관본 재전송
    snapshot = get_last_run_before(pipeline_id, today_9am_kst)
    if snapshot:
        return snapshot.as_cached_response(prefix_note="before_market_open")
    raise 404
if pipeline_id == "market_briefing" and _now_kst().hour < 9:
    raise 400 "use /briefing_pre before 09:00"
if pipeline_id == "close_briefing" and (_now_kst().hour, _now_kst().minute) < (15, 30):
    raise 400 "only after market close"
```

### `parts_store` 확장
- `get_last_run_before(pipeline_id, cutoff_iso)` 신규

### `BriefingResponse` 확장 (호환 유지)
- `note: str | None` 필드 추가 — `"before_market_open"` 같은 태그
- 봇 렌더러가 이 값을 읽어 prefix 생성

## 텔레그램 명령어 사양

| 명령 | 동작 | 처리 경로 |
|---|---|---|
| `/briefing_pre` | morning_pre 브리핑 | `briefing_run("morning_pre", force=True)` (09시 이후엔 내부 분기로 보관본) |
| `/briefing_now` | 실시간 시장 관찰 | `briefing_run("market_briefing", force=True)` |
| `/briefing_close` | 장 마감 해석 | `briefing_run("close_briefing", force=True)` |
| `/help` | 명령어 목록 + 각자 성격 설명 | 정적 텍스트 |
| `/briefing` | **제거 or 안내**: "아래 3개 중 선택하세요" | 텍스트 응답 |
| `/briefing_now` (구) | **제거** — 이전 v1 의 `/briefing_now` (= force morning_pre) 의미 변경됨 |

> 주의: `/briefing_now` 명령어는 v1 에서 "morning_pre force" 였는데 v2 에서 "market_briefing force" 로 **의미가 바뀜**. 이는 v1 을 사용 중이던 사용자에게는 breaking change. 혼자 쓰는 프로젝트라 즉시 전환 허용.

## RAG 설계 상세 (Phase 3)

### `core/knowledge/ingest.py` (신규)

```python
def ingest_canon(canon_dir: Path, chroma_client) -> dict:
    """canon/*.md 를 청크 단위로 Chroma 인덱싱.

    청크 전략:
    - 각 md 파일의 H2 섹션 단위 분할
    - 청크당 max 1000 토큰
    - metadata: {source_file, section_heading, canon_version}
    """
    ...
```

### `core/knowledge/retrieve.py` 확장

기존 skeleton 완성:
- Chroma client 초기화 (singleton)
- `retrieve(query: str, top_k: int = 3) -> list[str]` — 관련 청크 본문 반환
- Chroma 연결 실패 시 `[]` 반환 (graceful degradation)

### analyze stage 의 프롬프트 합성

```
System: [기존 persona.md + compiled.md]
User:
  오늘 장전 예상: {pre_briefing.scenario}
  오늘 장중 스냅샷들: {market_briefing_runs}
  현재 장 마감 팩터: {close_market_factors}
  관련 과거 교훈: {rag_chunks}  ← retrieve(query="오늘 키워드") 결과
  ---
  아래 JSON 스키마로 응답: { prediction_review, market_interpretation, next_outlook, ... }
```

## 판단 로직
<!-- SPEC:INTERVIEW-SLOT role="judgment-logic" -->

- **현재 시각 판정**: `datetime.now(ZoneInfo("Asia/Seoul"))` 기반
- **09:00 컷오프**: 정확히 09:00:00 KST. 09:00:00 은 "장 시작 이후" 로 취급
- **scheduled vs manual 구분**: `run_id` 생성 시 suffix. BRIEFING-ON-DEMAND-001 은 이미 `#manual-<hex>` 사용 중 → 스케줄러의 `_run_pipeline` 은 `#sched-<hex>` 로 변경
- **Close 브리핑의 당일 데이터 조회**: `created_at >= date(today, 00:00:00 KST)` 기준. 자정 지나면 어제 데이터는 "다음날" 의 close 분석 대상 아님

## 엣지 케이스
<!-- SPEC:INTERVIEW-SLOT role="edge-cases" -->

- **장전 보관본 없음**: 주말·공휴일. → 텔레그램: "오늘은 장전 브리핑이 없습니다 (주말/공휴일)"
- **Close 호출인데 오늘 pre·now 가 아예 없음**: RAG + 현재 팩터만으로 제한된 리포트
- **RAG 청크 없음 (canon 비어있음)**: 기본 페르소나만으로 진행. 응답에 `rag_enabled: false` 메타
- **market_briefing 호출 시점이 한국 공휴일**: 지표가 update 안 됨 → 전일 마감값 반환 + 경고 prefix
- **15:30 정각 호출**: close_briefing 은 거부 — 15:30:01 부터 허용 (장 마감 확정)

## 보안 / 크로스 플랫폼

- 기존 규칙 승계 (BRIEFING-ON-DEMAND-001)
- chat_id 화이트리스트 / `.env` 관리 / httpx 로거 WARNING 유지
- Chroma DB 파일 위치: `data/knowledge/chroma/` (gitignore)

## 완료 기준 (v1 MVP)

- [ ] `/briefing_pre` 09:00 이전 실시간 / 09:00 이후 보관본 재전송 동작
- [ ] `/briefing_now` 09:00 이전 거부 / 09:20 이전 경고 / 그 외 실시간
- [ ] `/briefing_close` 15:30 이전 거부 / 15:30 이후 실시간
- [ ] market_briefing 파이프라인 scheduled 없이 on-demand 만 동작
- [ ] close_briefing scheduled cron `45 15 * * 1-5` 트리거
- [ ] RAG ingest 스크립트로 canon → Chroma 인덱싱 성공
- [ ] close_briefing 의 analyze stage 가 RAG 청크 주입 받아 응답 생성
- [ ] canon 비어있어도 close_briefing 정상 동작 (graceful degradation)
- [ ] 봇 /help 에 3 명령어 설명 및 시간 validation 안내
- [ ] 기존 BRIEFING-ON-DEMAND-001 테스트 전부 통과 (회귀 없음)
- [ ] 신규 테스트: `test_market_briefing.py`, `test_close_briefing.py`, `test_briefing_validation.py` 통과

## 구현 진행 상황

| Phase | 상태 | 완료일 | 메모 |
|---|---|---|---|
| Phase 0 — 사전 정리 | ✅ 완료 | 2026-04-23 | `pipeline_prompts_dir()` helper → `pipelines/_base.py`. scheduler·API run_id suffix 둘 다 `secrets.token_hex(3)` 통일. Run ID 형식 규약 → `docs/CONTRACTS.md` |
| Phase 1 — `/briefing_pre` 09:00 validation | ⏳ 진행 중 | — | — |
| Phase 2 — `/briefing_now` (market_briefing 신규) | 미착수 | — | — |
| Phase 3 — `/briefing_close` + RAG | 미착수 | — | — |

---

## v3 로드맵 (별도 SPEC)

- **적중률 자동 채점**: close_briefing 의 `prediction_review.match_score` 누적 → 주간 리포트
- **전일/전주 비교**: `/briefing_close` 응답에 "어제 close 와의 차이" 포함
- **웹앱 UI**: 3 브리핑을 카드 UI 로 표시 + 과거 N 일 scroll
- **다른 팀 파이프라인 파급**: 이 패턴을 매크로팀, 단기테마팀 등에도 적용

## 다른 팀·파이프라인 영향

- **DB 스키마**: 변경 없음. pipeline_id 값 3종으로 확장만
- **BRIEFING-ON-DEMAND-001 API**: pipeline_id 파라미터화되어 있어 자동 수용
- **scheduler**: 신규 manifest.yaml 2개 자동 등록
- **morning_pre**: `analyze.py` 의 프롬프트 경로 하드코딩 리팩터 영향 (Phase 0)

---

**SPEC 작성자 노트**: 이 draft 는 2026-04-23 세션에 작성됐으며, 실제 구현은 별도 세션에서 Phase 0~3 순서로 진행. 각 Phase 시작 전 이 SPEC 의 해당 섹션을 재검토하고 필요 시 조정.
