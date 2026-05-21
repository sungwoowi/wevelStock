---
date: 2026-05-21
topic: INFRA-SNAPSHOT-EXTEND-001 SPEC 5 라운드 면담 신설 (cycle 12 SPEC only)
status: completed
plan_file: C:\Users\HOME\.claude\plans\twinkling-mixing-shell.md
---

# 2026-05-21 · INFRA-SNAPSHOT-EXTEND-001 SPEC 5 라운드 면담 신설 (cycle 12)

## 배경

cycle 11 (2026-05-21 직전 사이클) 자료 0 시드 5 분석가 production 검증에서 **5 분석가 모두 snapshot 데이터 부재로 본격 판정 불가** 드러남 — market_state_analyzer unknown / stock_picker 점수 null / flow_analyzer insufficient_data / trading_journalist 거부 / news_curator 거부. Track Selector 양 트랙도 verdict=wait 종결. **production UX 진입의 직접 차단점**. RESUME Top 1 (옛 production UX) 진입 전 snapshot 보강이 우선 권유. 본 사이클 = `/spec-interview` skill 5 라운드 면담으로 `INFRA-SNAPSHOT-EXTEND-001` SPEC frozen 만 (cycle 5/9 패턴 미러). 코드 변경 0, 구현 풀세트는 다음 사이클 cycle 13.

## 한 일

- `docs/specs/INFRA-SNAPSHOT-EXTEND-001-snapshot-extend.md` 신설 (~290줄) — frontmatter generates 11 + modifies 8 + depends_on 2 (INFRA-CHART-DATA-001 v2 + ANALYST-PERSONAS-001 v2) + contracts 1 (`market-snapshot-md-v1` 정식 명문화). 12 § (목적 / 배경·차단점 / 핵심 정의 / Phase 분리 / 명세 14 sub-§ / non-goals 7 / SLOT 5 / 영향 SPEC 4 / 구현 순서 15 단계 / 본 사이클).
- `C:\Users\HOME\.claude\plans\twinkling-mixing-shell.md` — 본 사이클 plan 파일 작성 (Context + 오늘 할 일 확정 + 9 단계 실행 계획)

### 5 라운드 면담 결단 5건 박음

- **R1 데이터원·상의 장치**: chart_ohlcv (cycle 6) 재사용 = 지수 ticker (KOSPI `0001` / KOSDAQ `1001`) + 14 섹터 ETF 추가 → 시장매크로·섹터 RS 파생 / 수급 60일 = 신규 테이블 `supply_demand_history` + KIS 5주체 EOD fetch / briefing_parts 보조 활용 (intraday 흐름·breadth)
- **R2 신규 필드 6**: A 시장매크로 4 (`kr_index_hierarchy` / `kr_breadth` / `kr_ma_trend` / `distribution_days`) + B 섹터 RS 1 (`sector_rs` 14 섹터) + C 수급 60일 1 (`kr_supply_60d` agreement_score 포함). 종목 단위 (정배열·52주 신고가) chart_ohlcv read 위임 (snapshot 미적재)
- **R3 적재 cron + DB**: 통합 cron 1개 `snapshot_macro_refresh` 평일 18:00 KST + 신규 DB 2 테이블 (`market_macro_snapshot` 일별 + `supply_demand_history` 일별). schema_version 6→7.
- **R4 render + contract**: `[3]` 블록 확장 (기존 8 섹션 + 신규 9·10·11 섹션 누적). `compose.build_pipeline_prompt` 시그니처 변경 X. `market-snapshot-md-v1` 정식 계약 = cycle 1~2 ad-hoc 의 SPEC 그라운딩 = 11 섹션 풀세트
- **R5 본 사이클 범위**: SPEC frozen 만 (cycle 5 INFRA-CHART-DATA-001 ad6ec07 + cycle 9 INFRA-FUNDAMENTAL-DATA-001 1bd1ff8 패턴 미러). 구현 15 단계 = cycle 13 (~2 세션)

## 검증 결과

- ✅ `scripts/validate.py` 0 errors, 1 warnings (teams/registry.yaml 부재 — 본 사이클 무관)
- ✅ SPEC frontmatter 단독 파싱 통과 (generates 11 / modifies 8 / depends_on 2 / contracts 1 dict 형식)
- ✅ 12 § 표준 헤더 INFRA-FUNDAMENTAL-DATA-001 양식 답습 정합

## 의도적으로 안 한 것

- **D 실 매매 데이터 (trading_journalist)** — Layer 4 계좌관리자 의존, `ACCOUNT-MANAGER-001` 가칭 별도 SPEC
- **E 뉴스 자료원 (news_curator)** — `NEWS-SOURCE-001` 가칭 별도 SPEC (Perplexity MCP + 유튜브 + 시간축 라벨링 + 학습부 DB)
- **종목 단위 alignment snapshot 적재** — chart_ohlcv read 위임. `INFRA-SNAPSHOT-TICKER-001` 가칭 후속
- **5 분석가 persona 마이크로 정정** — 인프라 활성화로 분석가 unknown 가드 자연 해제. persona v 정정 = cycle 13 구현 풀세트 시 동시 (chart v3 / fundamental v4 패턴 미러)
- **SLOT 5 (Distribution Day 임계 / sector_rs 공식 / agreement_score 가중 / KRX backend breadth bld / KIS 지수 chart endpoint)** — 본 SPEC 미확정, cycle 13 production 검증 또는 회고분석가 PROPOSAL 시 결단

## 다음에 이어서 할 작업 (우선순위)

1. **`INFRA-SNAPSHOT-EXTEND-001` 구현 풀세트** (~2 세션) — cycle 6/10 패턴 미러. DB migration v7 + collectors 3 신규 + snapshot.py 통합 + cron + render 9~11 섹션 + 25 테스트 케이스 + production smoke (market_state_analyzer / stock_picker / flow_analyzer 본격 판정 시연). cycle 13 진입 = production UX 차단점 해소
2. **`WAVE-ALPHA-001` SPEC 신설** (~1 세션) — α 공식 anchor A/B/C 확정 → stock_analyst verdict=confirmed_* 도달 → MS4 진입 베이스라인. stock_analyst 단독 영향, snapshot extend 와 독립 진행 가능
3. **production UX 본질 구현** (~3 세션) — 자연어 채팅창 + Track Selector 자동 라우팅 + 종합 답변. snapshot extend (Top 1) 후 자연 진입 — snapshot 부재 상태에서 UX 만들면 답변 항상 wait/unknown 무의미

## 맥락 재진입 힌트

- **본 SPEC = cycle 5/9 패턴 1:1 미러**: SPEC frozen → 다음 사이클 구현 풀세트 ~2 세션. cycle 13 의 첫 단계 = DB migration v7 → KIS 지수 chart endpoint 확장 → collectors 3 신규 → snapshot 통합 → cron → render.
- **`market-snapshot-md-v1` 정식 계약 = cycle 1~2 ad-hoc 의 SPEC 그라운딩**: 기존 `compose.build_pipeline_prompt(market_snapshot_md=)` kwarg 시그니처 그대로 유지. v1.0 = 11 섹션 풀세트.
- **briefing_parts 활용 본질**: 본 SPEC 의 정규 cron + DB 외 보조 source. intraday 흐름 (flow_analyzer 자금 유입 속도 0.2 축) + breadth 적재 채널 확장은 후속. EOD 60일 시계열은 `supply_demand_history` 신규 테이블로 명료한 데이터 모델.

## 커밋 상태

- 본 cycle 12 commit + push 진행 (SPEC + wrap-up 묶음, cycle 5 ad6ec07 + cycle 9 1bd1ff8 패턴 정합)
