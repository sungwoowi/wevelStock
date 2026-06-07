# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: **LB-MS2 운영 ramp 마감 ✅ (2026-06-07)**. 시장관 종합(`MARKET-VIEW-SYNTHESIS-001` verified)의 마지막 조각 = **순환매 일일 적재 cron 배선**. `build_market_view`는 답변 시점 첫 호출만 자가적재 → prev 부재로 순환매가 영구 `"—"`였음. 평일 18:05 `run_snapshot_macro_refresh`에 3단계(supply→macro→**market_view**) 합류로 매일 sector_rs+market_view 적재 → ≥2 평일 누적 시 순환매 라이브 활성. 회귀 **904 passed**, LEFT-BRAIN **2/4(50%)** 유지. 직전 = LB-MS2 시장관 종합 본체(6/6).

**본 세션 산출** (LB-MS2 운영 ramp):
- `server/schedulers/jobs/snapshot_macro.py` — `run_snapshot_macro_refresh`에 3단계 `build_market_view("KOSPI", force_refresh=True)` 추가(macro DB-hit 뒤 맨끝, try/except 격리, 반환 dict market_view 키). 별도 job·스케줄러 등록 불필요(18:05 cron 이미 등록).
- `tests/test_snapshot_macro_job.py` 신규 3 (이 job 테스트 0이었음 — 3단계 호출·force_refresh·실패 격리). 904 passed, validate 0 errors.
- 실증: 격리 DB에서 prev 없음 `"—"` → 5일전 스냅샷 누적 후 `"바이오→금융"(strong)`, one_liner `순환 …` 등장.

**이번 세션에 굳힌 판단 (2026-06-07 일일 적재 cron)**:
- **순환매 활성화 = 일일 적재 누적이 전제**: rotation은 본질이 *이동*이라 다일 윈도우(prev) 필요. cron 부재 시 `"—"`가 정상(버그 아님). 적재 위치는 macro refresh **뒤**(build_market_view가 compute_market_macro DB-hit). 별 job 신설보다 기존 18:05 cron 합류가 응집·순차안전.
- **dev cron 미작동이 진짜 ramp 차단점**: 코드상 cron은 정상 등록이나 dev 머신 서버 미상주 시 18:05 미발동 → sector_rs/chart/fundamentals 적재 전부 영향. 다일 누적의 실 전제 = 서버 상주(또는 수동 트리거). 근본 해소가 별 부채.

**직전 세션 판단 (2026-06-06 시장관 종합)**:
- **시장관 종합 = 결정론 함수 + 기존 분석가 해석** (신규 분석가 X): synthesize_market_view가 sector_rs+regime+macro 종합 → market_state_analyzer가 read·해석. 5점수 패턴(결정론 수치→LLM 해석) 동일, 역할 중복 회피.
- **순환매 = 결정론 다일 후보 ⨯ LLM 검증** (둘 다의 실패 회피): 결정론 단독=하루치 오해 / LLM 단독=환각 → **다일 윈도우 후보 + LLM은 생성 X 검증만**(결정론 후보가 앵커). agree/disagree 신뢰도 ±·노출. WAVE-ALPHA anchor 캐싱 mirror라 답변 시점 비용 0.
- **섹터 라벨 = ticker 매칭**: SectorRS.sector는 ETF 브랜드명("TIGER 200 금융")이라 답변엔 ticker→친화명("금융"). 순환매 prev/today 매칭도 ticker(정체성)로 — 라벨·매칭 일관.

**직전 세션 판단 (2026-06-06 거버넌스/답변누수)**:
- **시스템 = 왼쪽 뇌/오른쪽 뇌**: 왼쪽(수집→분석→답변) 먼저 완성 후 오른쪽(비중→채점→복리). **SPEC 2-tier 거버넌스**(roadmap 점검 ↔ implementation 코딩) + **단계 지도는 SPEC status 파생**(`project_status.py`, 손으로 % 금지). 답변 누수 = formatter echo·축 과적합 봉합(F1/F2/F3).

**직전 세션 판단 (2026-06-04 buy_score A축)**:
- **A점수 = 최근 연간 EPS YoY breakpoint 매핑 + 3년 raw 노출**: O'Neil 가속·일관성은 brittle 공식 대신 LLM이 원시 시계열로 판단(advisory). universe 누적은 dev 자기치유 X(cron 서버 의존). 입력 배관 6.5→6.5/7축=한계효용, 본질로 전환.

**직전 세션 판단 (2026-06-04 1세션 persona MA-ride 인용)**:
- **canon 주입 = 분석가별 `canon_categories` 필터**(`core/knowledge/compose.py::load_shared_canon`): stock_picker=`stock_selection/*`, stock_analyst=`stock-analysis/*`. **부서 밖 canon은 cross-ref만, ID 직접 인용 X**.

**직전 세션 판단 (2026-06-02 3세션 extension floor + MA-ride 구현)**:
- **"천장 포화 = k 약함"은 오진**: ma20-아래 종목은 `10-k·(음수)≥10`→무조건 clamp = **k 무관**. lever는 k가 아니라 **ma20-아래 floor**(C). 계측으로 원인 분리(ma20-위 과열 vs ma20-아래) 후 결정 — 직전 진단 맹신 금지.
- **MA-ride 위계 = 사용자 추세추종 framework**: 빠른 이평 탈수록 주도 강함(4일선=초강세=삼성·하이닉스 / 7일선=강세 / 월봉7MA=시대적 장기). "타고 오름"=MA 스택 순서(latest 값만, slope 불필요). 과열도(거리)⊥구조(어느 MA).
- **magnitude는 다일 튜닝**: k_below/deadband(1.0/1.0)·MA-ride 점수 간격은 보수적 기본만 커밋, single-day overfitting 금지([[feedback_backtest_essence]]). universe 백필로 누적 시작 → `--k-below` 스윕으로 확정.

**직전 세션 판단 (2026-06-02 2세션 screening 진단)**:
- **RS 분포 진단 = 풀 한 번 랭킹**(종목 루프 X): RS는 풀 내 백분위라 `rank_candidates(pool, regime)` 한 호출이 단위. 절대 점수 아님 → 풀 크기·구성이 점수에 직접 영향.

**직전 세션 판단 (2026-06-02 Track B 라우팅)**:
- **track별 필수 분석가 = `track_required` config 블록**(하드코딩 X): route가 해당 track 포함 시 필수 발행자 append. 시나리오 축약(Track A 기준)이 떨어뜨린 권위를 track 인지로 복구. **trader는 Track B 전용**(T-Score+6트리거, Track A frame 밖). 813 passed.

**직전 세션 판단 (2026-06-01 4세션 production 시연 + cited_scores 누수)**:
- **production 시연 = production-chat 엔드포인트 구동**(`POST /api/chat/production`, CLI 없음). provider=gemini가 실 배포 경로(claude_code는 이상화 → 누수 은폐).
- **cited_scores 누수 = LLM 재추출 의존**(인프라 아님): 점수는 metadata에 결정론으로 있는데 전략가 LLM이 자유텍스트에서 못 읽음 → `render_prefetched_analyst_outputs` 구조 직접 주입으로 해소. α만 예외.
- **결정론 점수는 본질적으로 느린 지표**(누적 수급·60일 상대강도): 하루짜리 이벤트는 momentum 흔적만, **이벤트 원인·내러티브는 news_curator+market_state_analyzer LLM 영역**(뉴스부 0시드 공백, 백로그).

**직전 세션 판단 (2026-06-01 2세션 S-Score 정밀화)**:
- **supply_chain = theme→섹터 RS 실측**(`classify_theme`→`theme_sector_mapping`→`snapshot.sector_rs` 최강). **alignment 정규화 = 품질 측정**(결측 위계 평가 제외). 새 테마 추가 시 taxonomy+authority+sector_mapping 3곳 정합.

**직전 세션 판단 (2026-06-01 1세션 S-Score 배선)**:
- **새 점수 배선 패턴 = α/flow_inputs mirror 3단**: compute 순수 → build async(graceful) → render_md + run_analyst `_maybe_build_*` hook(manifest `reads_*`) + compose `[6x]` 블록.
- **rs 축 = `stock_rs_score`(풀 percentile) / L 축 = `screening_score`(RS+과열도)** — 둘 다 `rank_candidates` 한 호출. **pytest_safety hook 오탐 재발**(here-string 본문 "pytest" 차단, 우회=단어 회피).

**직전 세션 판단 (2026-05-31 market_breadth)**:
- **KRX `STAT/standard/*`는 Akamai 봇차단 = 영구 불가**(getJsonData STAT 전부 "400 LOGOUT", OTP→download 403, pykrx도 OHLCV만 네이버 우회, devtools 무의미). MAIN bld(선물)만 가능. **market_breadth = KIS `inquire-index-price` `*_issu_cnt`**, **종목 5주체 = KIS 3주체 영구 확정**(실익≈0).

**직전 세션 판단 (2026-05-31 SLOT S2)**:
- **inflow_speed "결함" = floor clamp 압축**(코드 버그 아님): `map_to_axis` `x≤pts[0][0]`→끝점 고정. 새 KIS 금액축 breakpoint는 관측 폭부터(flow_distribution.py) 후 floor 정할 것.
- **breakpoint = 절대 앵커(raw 0=5점) 보존 + 꼬리만 재스케일**: single-day median recenter 금지(overfitting, [[feedback_backtest_essence]]). 분류(LLM)⊥채점(결정론) 분리라 소스 교체 시 net_sums만 바뀜.

**직전 세션 판단 (2026-05-31)**:
- **KIS 순매수 거래대금(`*_ntby_tr_pbmn`)은 이미 백만원 — ÷1e6 금지**. 레퍼런스 = `market_investor_total`. 새 KIS 금액 필드 기준.
- **Gemini-2.5 결정론 JSON 호출 = `thinking_budget=0` 필수** ([[feedback_gemini_thinking_budget_json]]): thinking 토큰이 max_output_tokens 잠식 → JSON 잘림.

**WAVE-ALPHA 14.2 산출물** (commit `7c60944`):

**WAVE-ALPHA 14.2 산출물** (commit `7c60944`):
- **`collectors/anchors.py` 신규** (~600 LOC) = extract_swing_candidates (Stage 1 결정론 rolling local extrema + min_gap 필터) + select_anchors_via_llm (Stage 2 Haiku 4.5 직관 + JSON 유효성 검증) + 3 단 캐싱 (llm_call_cache type='anchor_selection', TTL 30 일, cache_key "ticker|tf|cutoff") + load_manual_anchors (manual_anchors DB SELECT 우선) + E6 fallback (Stage 2 실패 시 결정론 candidate 마지막 3 개, source='deterministic_fallback') + compute_alpha_3tf 진입점 (3 timeframe 풀세트, cutoff_date 백테스팅 친화 canon WX1) + render_alpha_3tf_md ([5] α 3 timeframe 블록) + alpha_3tf_metadata helper
- **`core/knowledge/compose.py`** = build_pipeline_prompt 에 alpha_3tf_md 파라미터 신규 ([5] α block, [4] chart 와 [6] fundamental 사이)
- **`core/inference/run_analyst.py`** = _maybe_build_alpha_3tf_md helper (cycle 13 _snapshot_extend_metadata 패턴 mirror) + run_analyst / run_analyst_stream 양쪽 hook + alpha_meta 4 키 노출

**WAVE-ALPHA 14.3 산출물** (commit `e2ee94b`):
- **persona.md v4 → v5** = § Identity v5 헤더 + 권위 한정 4 종 확장 / § Inputs α 3tf 자동 주입 / § Reasoning Doctrine α 시간 정규화 정식 전면 재작성 (k₁/k₂/α + WA·WF·WL·WE cited + THRESHOLDS/TIMEFRAME_LIMITS + 5단계 label + WF4 외삽 + WE1~WE7) / **§ verdict 매트릭스 신설** (canon WL2, long/swing/중립 11 row + 보수 우선) / **§ holding_period 매핑 신설** (canon WL3, monthly→장기 / weekly→중기 / daily→단기, multi 시 긴 timeframe 우선) / **§ 환각 가드 1중→3중** (가드 1 자료 0 시드 잔여 4 카테고리 / 가드 2 chart_data_md [4] 출처 / **가드 3 anchor 출처 강제 신설** — source ∈ {manual, llm_stage2, deterministic_fallback, unavailable}) + § v5 정정 트레이스
- **manifest.yaml v5** = response_rules WAVE-ALPHA 본문 (한국어 친화 timeframe 명시 + cited fractal_wave 21 명제 ID + 시간 정규화 공식 + verdict 매트릭스 + holding_period 매핑 + 환각 가드 3 + Track A read 정합 확장)
- **anchors.py deterministic_fallback 가드** = `min_gap_days // 2` 이상 trailing candidate 만 채택, `usable < 3` 시 unavailable (smoke 발견 본질 정정)
- **core/db/connection.py** = _ensure_schema 가 _apply_migrations 자동 호출 (v8 llm_call_cache.type ALTER 멱등 — 기존 dev DB 호환). 14.1 빠뜨린 본질 보강
- **테스트 신규 ~74** = test_alpha.py 31 (시간 정규화 시나리오 + interpret_alpha 5 단계 timeframe 차등 + WE2/WE3 + WF4 외삽 + TIMEFRAME_LIMITS) + test_anchors.py 38 (extract_swing 결정론 + select_anchors mock + 캐싱 4 + manual override + compute_alpha_3tf + render/metadata) + test_data_analysts_v2.py +5 (v5 정합)
- **smoke 005930 실증** = α 풀세트 산출 (daily weak 0.44 / **weekly sweet 1.31 ⭐** / monthly overheated 3.86, source=deterministic_fallback). LLM Stage 2 (Gemini) JSON 파싱 결함 → 모두 fallback, SLOT S6 후속 보강 영역. 본 cycle 본질 (가드 강화된 fallback 정합) 검증.

**WAVE-ALPHA SPEC 5 라운드 결단 14 건 (영구 권위, cycle 14 SPEC, 14.1+14.2+14.3 모두 1:1 실행 완료)**:
- **R1 본질 5**: anchor 정의 = 1차 발산 시작 / 정점 / 되돌림 저점 = 2차 발산 시작 (사용자 **고유 파동분석 영역**, 박종훈 X) / 3 timeframe (daily/weekly/monthly) 동시 산출 / anchor 산출 = **2-Stage 하이브리드** (결정론 candidate + LLM Haiku 4.5 직관 + 3 단 캐싱 + manual override) ✅ / **백테스팅 본질** = alpha() cutoff_date 친화 설계 ✅ / 출력 = Layer 2 발행 + webapp 자연어 가이드 부록
- **R2 공식 4**: 시간 정규화 `α = (ln(current/C)/days(C→current)) / (ln(B/A)/days(A→B))` ✅ / 5 단계 label + timeframe 차등 임계 ✅ / 외삽 메타 2 (progress_to_b + duration_ratio) ✅ / 엣지 케이스 7 (E1~E7) + TIMEFRAME_LIMITS ✅
- **R3 canon 2**: 명제 ID = **WA/WF/WL/WE** ✅ / canon 분리 (본 SPEC = 21 명제 ✅, 풀세트 = SLOT S4 후속)
- **R4 persona 3**: verdict 매트릭스 ✅ / holding_period 매핑 ✅ / 환각 가드 3 중 ✅
- **R5 테스트/SLOT/구현 3**: 테스트 ~75 신규 ✅ (정량 UT 69 + 통합 5) / SLOT 6 (S1~S6 후속 SPEC) / 구현 sub-cycle 분할 14.1/14.2/14.3 ✅

**미해결 부채**: ~~INFRA-SCORE-INPUTS-001 코드 미구현~~ (✅ 2026-05-31 MVP+S3+S1 theme_match+종목 레벨 수급(KIS 3주체) 라이브+**SLOT S2 flow 3축 임계 13종 분포 튜닝·다종목 변별 실증**, pytest 714. **잔여 = breakpoint 중간점 운용 재튜닝(다일 누적 후) / S3 ATH 근처 목표 measured-move / ~~S-Score 배선~~(✅ 2026-06-01) / ~~buy_score 배선~~(✅ 2026-06-01 — CAN SLIM 7축 collector + classify_market_regime + cross-agent collector 직접 호출, 800. **5점수 S/T/α/buy/F 전부 라이브**) / 잔여 = 임계 production 캘리브레이션(RS R1/R2/R3 + regime + buyscore, 다일 누적 후) + 공백 2축 데이터 확장(~~A 연간 EPS 3년~~ ✅2026-06-04 yfinance income_stmt / N 뉴스부=NEWS-SOURCE-001 SPEC 게이트)**) / ~~KRX 5주체 + market_breadth 복구~~ (✅/❌ 2026-05-31 종결 — KRX STAT 전체가 **Akamai 봇차단**으로 영구 불가 실증(devtools도 무의미). **market_breadth는 KIS `inquire-index-price` `*_issu_cnt`로 복구**(전체 시장 source=kis_index). **종목 5주체는 KIS 3주체로 영구 확정**(실익≈0). KRX 휴면 helper에 Akamai 폐기 주석 박음) / **ANALYST-PERSONAS-001 옵션 b 정정 노트** (T/F-Score 는 advisory+LLM 권위로 정련됨 — persona 1줄 정정 권고, 별 작업) / **pytest_safety hook 오탐 재발** (2026-06-01 — `884a5b4` 수정은 인용 argv만 처리, git here-string `<<'EOF'` 커밋 본문의 "pytest" 단어는 여전히 차단. 우회=메시지 단어 회피. 근본=hook이 heredoc 본문도 strip하도록 보강, 별 작업) / ~~Flash 코드 라벨 잔존 누출~~ (✅ 2026-05-29 결정론 스크러버 `scrub_code_labels` 해소) / ~~cited_scores 누수~~ (✅ 2026-06-01 — 전략가가 분석가 점수를 LLM 자유텍스트 재추출하다 누락 → `render_prefetched_analyst_outputs` 결정론 점수 구조 직접 주입, 808) / ~~**Track B trader 라우팅 누락**~~ (✅ 2026-06-02 — `track_required.track_b=[trader]` config 블록 + `_resolve_analyst_ids_for_scenario` track 인지 append. 실 경로 검증 swing→trader 포함, 813) / **regime run간 흔들림** (같은 종목 strong/moderate 경계 인접, 히스테리시스 점검) / **Pro 발동 라우팅 미확정** (SLOT S7) / **임원 frame_mode 결정론 배선** (advisory 비결정성 하드닝, SLOT S1) / production UX 부분 답변 정직성 / SLOT S4 정확도 정정 (KIS top30 → KRX manual) / 기존 영역 LLM 3계층 마이그레이션 (`LLM-TIER-MIGRATION-001`) / gemini transient 503 root cause (retry/sequential, 별 영역) / **KIS rate limiter 전역화** (`INFRA-KIS-RATELIMIT-001` 후보, 여유 시 — 현 throttle `self._last_call` 인스턴스별 + lock 없는 레이싱이라 snapshot/chart 병렬 fan-out 시 "초당 거래건수 초과" 반복. 토큰은 이미 전역 공유, 호출 간격만 인스턴스별로 남은 빈틈. warning 수준 = retry 1회 + `return_exceptions=True` + DB-first 폴백으로 자가 회복하므로 비차단. 근본 = 프로세스 전역 token-bucket/세마포어. 2026-05-29 진단) / **validate.py cp949 크래시** (여유 시 — Windows 콘솔 cp949 에서 마지막 `✓` 출력 `UnicodeEncodeError`. 검증 자체는 정상, `PYTHONIOENCODING=utf-8` 우회 가능. print 인코딩 가드만 추가하면 됨) / ~~**chart_ohlcv 시드 universe 공백**~~ (✅ 2026-06-02 3세션 — `refresh_all_tickers`가 거래대금 상위 50종 매일 자동 적재(`fetch_universe_tickers`+`_select_refresh_tickers`, fetched_at cap). chart_ohlcv 31→71) / ~~**macro DB 캐시 충실도**~~ (✅ 2026-06-02 3세션 — `distribution_count_25d`/`breadth_source` 컬럼(v9 멱등 ALTER) + round-trip) / ~~**extension_score 천장 포화 = k 약함**~~ (✅/정정 2026-06-02 3세션 — **k 오진**: ma20-아래 100%가 k 무관 10 clamp. C = ma20-아래 거리비례 감점 floor+deadband. magnitude 다일 튜닝 잔여) / **k_below/MA-ride magnitude 다일 튜닝** (2026-06-02 — 보수적 기본(1.0/1.0)만 커밋, universe 누적 후 `--k-below` 스윕 = Top 1) / ~~**persona MA-ride 인용**~~ (✅ 2026-06-04 — stock_picker alignment 축 stale 정정+S-Score Doctrine 해석 지침+Knowledge Categories 갱신, stock_analyst 경량 cross-ref. **canon 주입=부서별 필터 제약**으로 stock_analyst는 ID 직접 인용 X. 106 passed) / ~~**buy_score A축(연간 EPS)**~~ (✅ 2026-06-04 2세션 — yfinance `fetch_annual`(income_stmt Diluted EPS) + `compute_annual_eps_yoy` + A축 배선, 중립 5.0 탈피. 라이브 005930 A 10.0. buy_score 6.5/7축 라이브, 837 passed) / **k_below/MA-ride magnitude 다일 튜닝** (universe 다일 누적 전제 미충족, 매일 장후 refresh 필요) / ~~**sector_rs 일일 적재 cron**~~ (✅ 2026-06-07 — `snapshot_macro` 3단계 `build_market_view` 배선, 904. **잔여 = dev cron 미작동 근본 해소**(서버 미상주 시 18:05 전체 적재 미발동, Top 3 #3) + 순환매 ≥2 평일 라이브 누적 관찰).

**마지막 작업일**: 2026-06-07 (sector_rs/market_view 일일 적재 cron 배선 — LB-MS2 운영 ramp 마감)
**마지막 세션 로그**: [2026-06-07_sector-rs-daily-cron.md](c_worked/2026-06-07_sector-rs-daily-cron.md). 직전 = [2026-06-06_market-view-synthesis-2.md](c_worked/2026-06-06_market-view-synthesis-2.md).
**산출**: `server/schedulers/jobs/snapshot_macro.py` 3단계(supply→macro→`build_market_view("KOSPI")`) + `tests/test_snapshot_macro_job.py` 신규 3. **회귀 904 passed**(+3), validate 0 errors. 순환매 활성화 격리 DB 실증(prev 없음 `"—"` → 누적 후 `"바이오→금융"` strong).
**Git**: 코드 1커밋 push(`c32e358`, feat 브랜치 → main FF) + 이 wrap-up docs 별도 커밋.

---

## 🎯 다음에 할 일 (Top 3) — 왼쪽 뇌 완성(LEFT-BRAIN-COMPLETION-001 roadmap)

우선순위 순. **LB-MS1(답변 누수)·LB-MS2(시장관 종합+일일 적재 cron) 완료 ✅.** 왼쪽 뇌 2/4(50%). `uv run python scripts/project_status.py`로 단계 지도 확인.

### 1. LB-MS3 뉴스부 = NEWS-SOURCE-001 SPEC 착수 (가장 무거움)
- **왜**: 6/5형 "버블 붕괴냐 조정이냐" 내러티브의 핵심 입력 + buy_score N 마지막 축(0시드). **LB-MS2 시장관에 먹일 재료**. 멀티세션 SPEC 프로젝트. LEFT-BRAIN 다음 자식
- **범위**: `/spec-interview` — Perplexity MCP + 유튜브 요약 + 시간축 라벨 + 학습부 DB + UX/UI([[project_news_source_decision]]). news_curator SLOT S2 해소
- **예상 산출**: NEWS-SOURCE-001 SPEC frozen → buy_score 7축 전부 실측

### 2. INFRA-US-MACRO-SNAPSHOT-001 (미장 매크로) — MARKET-VIEW SLOT 흡수
- **왜**: entry_posture에 **미장 야간**(SPX·NDX·VIX·DXY·US10Y) 축 가산 + one_liner "미장 risk_on/off" 토큰. MARKET-VIEW-SYNTHESIS-001이 위치만 확보(`us-macro-hook` SLOT)해 둠. LEFT-BRAIN 자식
- **범위**: `/spec-interview` — yfinance/FRED 미장 매크로 collector + market_view entry_posture 흡수
- **예상 산출**: INFRA-US-MACRO-SNAPSHOT-001 → 진입 자세가 미장까지 반영

### 3. dev cron 미작동 근본 해소 (운영 부채 — LB-MS2 라이브 누적 전제)
- **왜**: 18:05 cron은 코드상 정상 등록이나 dev 머신 서버 미상주 시 미발동 → sector_rs/chart/fundamentals 적재 전부 영향. 순환매·universe 다일 누적의 실 전제. 현재는 수동 ramp 필요
- **범위**: 서버 상주 운영 or 수동 트리거 endpoint(`POST /api/admin/refresh-snapshots` 류) 검토. 작은 작업
- **예상 산출**: 매일 장후 적재가 사람 개입 없이 누적 → 순환매 ≥2일 후 자동 라이브

(보조 백로그: regime run간 흔들림 히스테리시스 점검(2026-06-02 진단, 경계서 멂이라 급하지 않음) / `collectors/market_macro.py` sticky 밴드)

(추가 백로그: **SCREEN-RS-EXTENSION-001** (종목 RS+과열도 스크리닝, prism v2.13.0 #289 차용 — SPEC 작성 완료 draft, **트레이딩부/scoring 구현 때 같이**. scoring.py 순수 함수 3개 + config/screening.yaml + collectors/screening.py. SLOT R1~R3 라이브 튜닝) / **WAVE-ALPHA SLOT S1·S2·S3·S4** (target_prices·watchlist·backtest·canon) / **NEWS-SOURCE-001** SPEC 신설 (news_curator SLOT S2 해소) / **PERSONA-REFUSAL-CITED-RULE-001** SPEC 신설 / news_curator persona 슬림화 / Layer 4 계좌관리자 (M5) / Layer 5 회고분석가 (M4, RETROSPECT-ANALYST-001) / GUIDANCE-ACCURACY-TRACKER-001 / INFRA-US-MACRO-SNAPSHOT-001 (yfinance/FRED) / INFRA-RELIABILITY-VALIDATOR-001 (Layer 2.5/3.5) / scoring.py 정식 가중치 (SLOT S7) / streaming 토글 UI + AbortController / streaming response cache 멱등성 / Memory Compression / Quality Eval / MCP 패턴 차용 / 박종훈 Vol 2/3 OCR / png vision / xlsx sheet 분리 / canon 정수 추출 자동화 (KNOWLEDGE-SYNC-001 Phase 3))

(추가 백로그: **`WAVE-ALPHA-CANON-001`** (SLOT S4 풀세트 canon W5+ 사용자 자가 정리 + 양질도 10 점) / **`WAVE-ALPHA-WATCH-001`** (SLOT S2 월봉 황제주 watchlist + 알림 cron) / **`WAVE-ALPHA-BACKTEST-001`** (SLOT S3 백테스팅 본체, 사용자 본질 직관) / **`NEWS-SOURCE-001`** SPEC 신설 (news_curator SLOT S2 해소 — Perplexity MCP + 유튜브 + 시간축 + 학습부 DB + UX/UI) / **`PERSONA-REFUSAL-CITED-RULE-001`** SPEC 신설 (거부 응답 cited v3.1 룰 9 분석가 표준) / news_curator persona 슬림화 / Layer 4 계좌관리자 (M5) / Layer 5 회고분석가 (M4, `RETROSPECT-ANALYST-001`) / GUIDANCE-ACCURACY-TRACKER-001 구현 / INFRA-US-MACRO-SNAPSHOT-001 (yfinance/FRED) / INFRA-RELIABILITY-VALIDATOR-001 (Layer 2.5/3.5 Haiku 검증, M2) / scoring.py s_score·buy_score 정식 가중치 (SLOT S7) / streaming 토글 UI + AbortController / streaming response cache 멱등성 / Memory Compression SPEC / Quality Eval SPEC / MCP 패턴 차용 / 박종훈 Vol 2/3 OCR / png vision / xlsx sheet 분리 / canon 정수 추출 자동화 (KNOWLEDGE-SYNC-001 Phase 3 PROPOSAL))

---

## 🚀 시연 마일스톤 (시연 가능 단위)

**본질** (회장 핑퐁 [22] 정정): "코드 작성 완료 ≠ 시연 가능" 분리. Top 3 = 작업 단위 (분량·우선순위), 마일스톤 = **시연 도달 단위 (사용자 확인 가능 시점)**. 본 사이클 production 호출 보류 = MS1 차단점 발견 = MS0 신설 필연.

| # | 마일스톤 | 도달 조건 | 추가 비용 (누적) |
|---|----------|----------|----------------|
| **MS0** | production 호출 가능 (분석가·전략가 webapp 호출 작동) | `INFRA-RUNTIME-EFFICIENCY-001` (서버 모드 reuse + RAG 자료 0 시드 자동 OFF + SQLite 임베딩 캐시) | +1.5 세션 |
| **MS1** | Track B 첫 권고 완성형 시연 (cited_scores 풍부성 90%) | MS0 후 `swing:` 호출 = 8 분석가 풀세트 read | +0.5 세션 |
| **MS2** | Track A 첫 권고 완성형 시연 (stock_analyst verdict=`unknown` 자각 검증) | MS1 동시 (`long:` 호출 동시 가능) | +0 |
| **MS3** | stock_analyst 완전 (INFRA-CHART-DATA-001 후 v3 정정) | `INFRA-CHART-DATA-001` SPEC + v3 마이크로 정정 (~0.3 세션) | +1 세션 |
| **MS4** | 실 매매 시연 (권고 → 자금액 변환 → 주문) | Layer 4 계좌관리자 + `GUIDANCE-ACCURACY-TRACKER-001` | +2~3 세션 |
| **MS5** | 자가 진화 사이클 (회고 → PROPOSAL → manifest 갱신) | Layer 5 회고분석가 + 5 KPI 누적 (3~6 개월 운영) | +1 세션 + 운영 시간 |

**현재 위치**: cycle 14.3 (2026-05-23) 후 = **MS0·MS1·MS2·MS3·MS4 베이스라인 완전 도달 ✨**. WAVE-ALPHA 풀세트 활성 = stock_analyst α 3 timeframe (daily/weekly/monthly) 자동 발행 + verdict 매트릭스 (long/swing/중립) + holding_period 매핑 (장기/중기/단기) + 환각 가드 3중 (자료 0 시드 + chart_data_md 출처 + anchor 출처 강제). 005930 실 smoke = weekly sweet 1.31 / monthly overheated 3.86 산출. **MS4 = Layer 4 계좌관리자 + GUIDANCE-ACCURACY-TRACKER-001 본체** 는 별 단계 (시연 후속). 다음 = production UX (Top 1) → MS4 풀세트 → MS5 자가 진화.

---

## 🌱 이 프로젝트의 본질 (매 세션 반드시 참조)

- **[docs/a_wanted/user_want_spec.md](a_wanted/user_want_spec.md)** — **원 요구사항**. 이 프로젝트가 무엇을 위한 것인지 사용자가 직접 서술한 문서. 작업 방향이 본질에서 벗어나지 않도록 매 세션 초반에 반드시 읽고 내재화.

## 📂 활성 설계/계획 문서

- **[SPEC: BRIEFING-TIMEBASED-002](specs/BRIEFING-TIMEBASED-002-timebased-briefings.md)** — draft. 3종 브리핑 + RAG. **다음 세션 Top 1**
- **[SPEC: BRIEFING-ON-DEMAND-001](specs/BRIEFING-ON-DEMAND-001-briefings-on-demand.md)** — implementing. v1 구현 완료 (참조용)
- **[플랜: v1→v2 이행](../../../.claude/plans/nested-booping-dream.md)** — 2026-04-23 세션 최종 플랜
- **[파이프라인 재구성 플랜](b_plan/pipeline-restructure-plan.md)** — Phase 1~4 로드맵
- **[아키텍처 리뷰](b_plan/architecture-review-workflow-restructure.md)** — 하이브리드 6팀 3-Layer 결정

---

## 🧩 마지막 세션이 남긴 맥락 (바로 쓸 수 있도록)

### 완성된 자산
- `pipelines/market_briefing_pre/` (← morning_pre) — 8 stages, 실 LLM 실증 완료. notify stage `skip_notify` 존중
- `pipelines/market_briefing_now/` — 3 stages, KIS 22콜 + KRX 1콜 ~28s, LLM 없는 raw 발송
- `collectors/kr_{indices,sectors,leading_stocks,supply_demand,futures_supply_demand}.py` — 5주체 수급(KIS) + KOSPI200 선물 3주체(KRX)
- `connectors/{kis,krx}/client.py` — KIS 토큰자동·rate limit + KRX `getJsonData.cmd` POST helper
- `core/briefing/render.py` — 5주체 세로 나래비 + `[KOSPI200 선물]` 블록 + 백만원→억/조 helpers
- `server/api/briefings_on_demand.py` 4 엔드포인트 + `server/telegram/` 4 명령
- **5 학습부 폴더 + 5-Layer docs 등재** (M1) — `knowledge/canon/{principles,mechanics,wealth_compounding,stock-analysis,news}/`, `agents/` 위치 합의, STRUCTURE/RUNTIME/CLAUDE 5-Layer 표 정식 등재
- **`core/knowledge/compose.py`** — `load_shared_canon()` rglob 재귀 + README 자동 제외 + `build_pipeline_prompt(rag_dept=...)` 인자 (R3)
- **`knowledge/canon/principles/` 정제본 4 파일** (M2) — `01-philosophy-7-commandments.md` + `02-trading-doctrine.md` + `03-market-regime-rules.md` + `99-operational-safeguards.md`
- **`knowledge/canon/wealth_compounding/` 정제본 2 파일** (R4) — `01-framework-manifesto.md` (통화 3 + 사이클 5 명제, Ray Dalio 5단계 통합) + `02-survival-imperatives.md` (행동 룰 6개, I6 = 사용자 추가 3년 평균가 시그널). canon 자동 주입 char 수 **15,772 → 19,166**
- **`knowledge/reference/principles/` 원본 3** — 7계명·심법·거시 트레이딩 기준
- **`knowledge/reference/wealth_compounding/` 박종훈 24/29** (R2) — lectures 18 + materials 6 + ebooks 1(Vol 1). 541,627 chars (~540K tokens)
- **`scripts/sync_knowledge.py` + `config/knowledge_sources.yaml`** — OneDrive PDF 멱등 추출 sync. slugify(한글 보존) + 디자인 PDF 한글 글자공백 휴리스틱 정규화. `just knowledge-sync <dept>`
- **`core/knowledge/{embed,ingest,retrieve}.py` 5-Layer RAG** (R3) — BGE-m3 한국어 임베딩 wiring (Chroma collection EF 명시), `ingest(dept, *, force=False)` upsert + sha256 file_hash skip 멱등, `retrieve(dept, query, top_k)` lru_cache, `data/chroma/<dept>/`
- **`data/chroma/wealth_compounding/`** — 25 sources / 787 chunks 인덱싱 완료. 검증 4건 정확. 첫 인덱싱 ~55분, 멱등 재실행 17.7s (170배)
- **`scripts/knowledge.py`** — `ingest`/`browse` 단순 CLI + Windows utf-8 reconfigure
- **`docs/specs/INFRA-RAG-001-knowledge-rag.md`** — RAG SPEC + 한국어 임베딩 비교표 + 결정 근거
- **`agents/analysts/wealth_strategist/{persona.md, manifest.yaml}`** (M3) — Layer 2 첫 분석가. R4 canon 톤 그대로 + `reads:[wealth_compounding]` + max_tokens 4000 + temp 0.4
- **`agents/analysts/{market_state_analyzer, stock_picker, trading_journalist, flow_analyzer, news_curator}/{persona.md, manifest.yaml}`** (2026-05-19 cycle 2) — 자료 0 시드 5 분석가 v2. 8 섹션 portable + 한국어 친화 용어 + cited v3.1 + 박종훈 framework 직접 인용 금지 가드. 5 subagent 병렬 dispatch ~5 분.
- **`agents/analysts/{principle_guardian, trader, stock_analyst}/{persona.md, manifest.yaml}`** (2026-05-19 cycle 3, 본 사이클) — 자료 있는 3 분석가 v2 (사실상 principle_guardian 만 자료 있음, trader 사실상 0 시드 + stock_analyst 자료 0 시드 + INFRA 미비 환각 가드 2 중). 명제 ID **C·D·R·OS 21 개 신설** (principle_guardian) + **6 트리거 영문 ID** (trader) + α 미발행 fallback (a)/(b) + 환각 가드 2 중 (stock_analyst). 3 subagent 병렬 dispatch ~10 분 / 6 파일 1,439 줄.
- **`tests/test_seed_analysts_v2.py` (cycle 2) + `tests/test_data_analysts_v2.py` (cycle 3)** — 분석가 페르소나 양식 자동 검증 91 케이스. 8명 boundary 매트릭스 + 권위 키워드 충돌 negation + Track A·B read 정합 (trader 6 트리거 ↔ Track B / stock_analyst α+holding_period ↔ Track A / principle_guardian verdict ↔ Track A·B) 자동화.
- **`core/inference/run_analyst.py`** (M3) — 분석가 단일 호출 핵심 함수. 멀티턴 messages 배열 수용 + `build_pipeline_prompt` + `call_llm` + metadata (system char/RAG chunks/cache tokens/cost/latency/is_mock/upstream_error). CLI/REPL/FastAPI/webapp 4 인터페이스 모두 wrap
- **`scripts/{chat_analyst,ask_analyst}.py` + `just {chat,ask}` 레시피** (M3) — REPL 멀티턴 + 단일 턴 CLI. stdin/stdout utf-8 reconfigure + surrogate normalize + JSONL 자동 저장 (`data/analyst_queries/<id>/<dt>.jsonl`) + 누적 토큰 200K 가시화 + mock/upstream_error 라벨
- **`server/api/analyst_chat.py`** (M3) — `POST /api/analysts/{id}/chat` 멀티턴 endpoint + `GET /api/analysts/{id}` 메타
- **`webapp/src/app/analyst-chat/page.tsx`** (M3) — 멀티턴 채팅 페이지. mock 응답 시 ⚠ 뱃지 + upstream error 빨간 표시
- **`market_briefing_now` 자동 cron** (2026-05-07) — `30 9,12,14 * * 1-5` 평일 정규장 3회 (시초 정리 / 점심 / 마감 1시간 전). `pipeline::market_briefing_now::0` 등록 검증 + 18:37 임시 cron 발동 검증 통과
- **`core/briefing/parts_store.get_recent_runs()`** + **`core/briefing/render.render_pipeline()` dispatcher** + **`GET /api/briefings/{id}/recent?limit=N`** (2026-05-07) — 최근 N runs 의 (run_id, generated_at, parts, rendered 텔레그램 텍스트) 묶음 반환. 텔레그램 봇·webapp 공용 진입점
- **`webapp/src/components/BriefingPartsCard.tsx`** (2026-05-07) — 좌측 run 리스트 (날짜 그룹 + AUTO/BOT 뱃지 + 5초 polling) + 우측 텔레그램 텍스트 (가독성 ↑) + JSON 디버그 토글. 시계열 누적 가시화
- **`webapp/src/components/AlertList.tsx`** (2026-05-07) — "최근 자동 푸시 알림" 라벨 + 부제 (봇 응답은 브리핑 이력에 있음 명시)
- **render.py KRX 정규장 라벨 명시** (2026-05-07) — 국내지수·강세섹터·주도주 3군데 "KRX 정규장 전일 종가 대비" prefix. 키움 HTS 의 NXT 통합 가격과 혼동 회피
- **자산전략가 단계 1 톤 직설화** (2026-05-08) — `persona.md` L32 "명제 ID 인용 필수, 적용은 사용자 맥락 재구성" + L34 인접 명제 추론 허용 + manifest temp 0.4→0.7. cited 형식 + 금기 영역 유지
- **LLM provider fallback chain** (2026-05-08) — `core/llm/client.py` `_dispatch_provider` 가 gemini → claude_code → mock 자동 폴백. `provider` kwarg 지정 시 fallback X (명시 backend 만 시도, 에러 propagate)
- **claude_code Windows·OAuth 안정화** (2026-05-08) — `core/llm/claude_code_backend.py` 가 long system prompt 시 stdin `[SYSTEM]/[USER]` 결합 (cmd.exe 8K argv 우회) + `ANTHROPIC_API_KEY`/`ANTHROPIC_AUTH_TOKEN` env strip (Pro/Max keychain OAuth 강제)
- **Provider 선택 옵션 (CLI/API/webapp)** (2026-05-08) — `--provider` 플래그 (`scripts/{ask,chat}_analyst.py`) + `ChatRequest.provider` API 필드 (`server/api/analyst_chat.py`) + webapp LLM 토글 3개 (`webapp/src/app/analyst-chat/page.tsx`) + `GET /api/config/llm` 동적 라벨 endpoint (`server/api/config.py`). 응답 metadata 에 `provider_requested`/`provider_used` 노출
- **단계 2 시장 스냅샷 자동 주입** (2026-05-08) — `collectors/snapshot.py` 신규 (7 collector 병렬 + 5분 인메모리 캐시 + `asyncio.gather(return_exceptions=True)` partial-failure + cold call stderr 진행 표시 + `MarketSnapshot` dataclass + `render_snapshot_md` 안전 렌더). `compose.build_pipeline_prompt` 의 RAG 직전 [3] 블록 (`market_snapshot_md` kwarg, `cache_control` 없음 — 5분 갱신). `run_analyst` metadata 4키 (`snapshot_age_seconds`/`fetch_seconds`/`cache_hit`/`failures`). 모든 분석가 자동 공유 (옵션 A 풀세트). 5-Layer 분석가 모두 동일 raw 베이스
- **claude_code cost 라벨 frontend 분기 + analyst-chat SSR 가드** (2026-05-08 오후) — `webapp/src/app/analyst-chat/page.tsx` 4 곳 수정. MetadataBar/누적 비용에서 `provider_used==="claude_code"` 시 `cost $0 (subscription)` 표기. `analystMeta` state 를 `undefined | null | object` 3-state 로 확장 → SSR 첫 렌더 빨간 깜빡임 제거
- **시장 스냅샷 DB-first hybrid (옵션 A)** (2026-05-09) — `collectors/snapshot.py` 가 `briefing_parts` DB 의 latest part 우선 + 시간대 인식 임계 (`kr/us_threshold_seconds(now_kst)` cron 발동 시각 기반, 정규장 중 ~3h / 장 마감 후 ~18h / 주말 ~66h) + 부분 fetch (stale 그룹만). `MarketSnapshot` 에 `source_map`/`db_run_ids`/`db_age_seconds` 필드 추가, 4 어댑터 (`_adapt_overnight/kr_indices/supply_sectors/leading_from_part`). `render_snapshot_md` 헤더에 "_데이터 출처: 미국=DB (X시간 전 적재)_" 라인. 인메모리 캐시 TTL 300s → 60s. 분석가 호출 cold fetch ~30s → 0.3s, 5-Layer 단방향 정합 회복
- **LLM token streaming (SSE) — INFRA-LLM-STREAM-001** (2026-05-09) — `core/llm/client.py:call_llm_stream()` async iterator + 4 provider stream (anthropic `messages.stream()` / gemini `aio.models.generate_content_stream` / claude_code CLI `--output-format stream-json --include-partial-messages` / mock 5글자 청크). fallback chain (첫 청크 전 실패만). `core/llm/claude_code_backend.py` 에 `_can_spawn_subprocess()` 사전 체크 — SelectorEventLoop 면 sync subprocess + asyncio.to_thread 의 batch_thread 직행 (warning 0). stdin 송신 background task (Windows pipe deadlock 회피) + subprocess `limit=10MB` (skill md 한 라인 64KB 초과). `core/inference/run_analyst.py:run_analyst_stream()` + `first_token_ms` metadata. `server/api/analyst_chat.py` 에 `POST /api/analysts/{id}/chat/stream` (StreamingResponse). `webapp/src/app/analyst-chat/page.tsx` 가 fetch ReadableStream + SSE 프레임 파싱 + 빈 assistant 메시지 점진 누적 + MetadataBar `(first XXXms)` 라벨
- **pytest 94 passed** (60 → 87 → 94, 신규 `test_market_snapshot.py` 19 + `test_llm_streaming.py` 7)
- SPEC 5종: **BRIEFING-ON-DEMAND-001** + **BRIEFING-TIMEBASED-002** + **INFRA-RAG-001** + **INFRA-LLM-STREAM-001** + **KNOWLEDGE-SYNC-001** (2026-05-10 신설, draft)
- **`docs/AGENT-ARCHITECTURE.md`** (2026-05-10) — hierarchical orchestration + DB read 절충 영구 본질 문서. 두 패턴 비교 10 측면 + 도메인 본질
- **5-Layer 모델 9명 확장** (2026-05-10) — 지식부 9 (market_macro / stock_selection / trading_journal / flow_analysis 신설, mechanics→trading) + 분석가 9 (1:1 매핑). `CLAUDE.md` 5-Layer 표 + 본문 갱신
- **9 지식부 × 36 카테고리 폴더 + `_category.yaml` 36** (2026-05-10 Phase 0) — `knowledge/canon/<dept>/<category>/` 3-tier 구조 완비. 자료 있는 4 dept (principles 3 / trading 6 / stock-analysis 5 / wealth_compounding 6) + 자료 0 시드 4 dept (market_macro 4 / stock_selection 4 / trading_journal 4 / flow_analysis 4). 자료 git mv 50+ + 초안 삭제 3
- **`core/knowledge/adapters/` Phase 1 어댑터 5종** (2026-05-10) — `_base.py` (Adapter Protocol + ExtractedDocument) + `markdown.py` (frontmatter wrap) + `text.py` (UTF-8 read + char_count) + `pdf.py` (sync_knowledge.py 의 extract + 한글 공백 휴리스틱 이관) + `xlsx.py` (openpyxl 단일 body) + `png.py` (`enabled_by_default=False` silent skip). `__init__.py` 의 `ADAPTERS` 레지스트리 + `get_adapter(ext)`. `pyproject.toml` openpyxl>=3.1
- **`core/knowledge/ingest.py` 재작성** (2026-05-10) — `_iter_reference_files(dept)` 어댑터 디스패치 + 카테고리 폴더 직속 탐색 + `_` prefix 모든 path part skip. `_load_category_meta(dept, category)` canon `_category.yaml` ground truth 로드. `_build_metadata` 가 frontmatter + extraction + category 3중 병합. 멱등 backfill = `(file_hash, category)` 동시 비교. chunk metadata 18 keys (category / category_title / category_description / when_to_inject / target_analysts / dept / file_hash / extracted_at / page_count / sheet_count / char_count / source_pdf / ...)
- **`tests/test_adapters.py` + `test_ingest_categories.py`** (2026-05-10) — 신규 17 (pytest 111 = 94 + 17). 어댑터 fixture 는 tmp_path 동적 생성 (xlsx 는 openpyxl write, pdf 는 PdfWriter blank page)
- **`data/chroma/wealth_compounding/` force re-index** (2026-05-10) — 25 sources / 787 chunks / 6 카테고리 분포 (asset_classes 30 / crisis_signals 224 / currency_pricing 150 / debt_rate_cycle 153 / macro_roadmap 38 / monetary_evolution 192). retrieve smoke ("인플레이션 통화 가치") top 3 정확 + category 라벨 노출 + score 0.59~0.64. Phase 0 git mv 로 인한 legacy chunk 동시 청산
- **Phase 2 M1: retrieve/compose 카테고리 화이트리스트** (2026-05-10) — `core/knowledge/retrieve.py` `retrieve(dept, query, *, categories=None, top_k=3)` + ChromaDB `where={"category": {"$in": [...]}}` 조건부 + 빈 리스트 falsy fallback. `core/knowledge/compose.py` `load_shared_canon(canon_categories=None)` 폴더 path prefix 매칭 필터 + `build_pipeline_prompt(..., canon_categories=None)` + RAG 분기에서 `rag_dept` 매칭 카테고리만 추출해 `retrieve(categories=)` 전달 (canon block + RAG block 둘 다 좁아짐). `core/inference/run_analyst.py` `AnalystSpec.canon_categories` 필드 + manifest 로드 + 두 run 함수에 전달. `wealth_strategist` manifest 검증값 `canon_categories: [wealth_compounding/macro_roadmap]` (M3 SPEC 정식 정의 시 6 카테고리 복귀 예정). `tests/test_retrieve_categories.py`(4) + `test_compose_canon_categories.py`(7) 신규 = pytest **122 passed** (111 → +11). 통합 검증: canon 18,726 → 3,935 chars (79% 감소), RAG block macro_roadmap 청크만 회수. 1 commit + push (`7158cd0`)
- **Phase 2 M2: sync run + DB run log + delta 인덱싱** (2026-05-11) — `core/db/schema.sql` 에 `knowledge_index_runs` (sync_id PK / dept / started_at / ended_at / status / files_{added,modified,deleted} / chunks_{upserted,deleted} / proposal_path / release_note_path / error) + `idx_kir_dept_started` 인덱스 + schema_version 4. `core/knowledge/sync.py` 신규 — `sync_dept(dept, *, since_run_id=None)` + `sync_all()`. ingest 의 `_iter_reference_files`/`_build_metadata`/`_chunk_text` 재사용. collection metadata 비교로 `source_id → file_hash` 맵 추출 → delta 분류 (added/modified/deleted) → upsert + hard delete (`where source_id`). modified 는 청크 수 감소 케이스 위해 pre-delete + upsert. `_allocate_sync_id` 분→초→ms PK fallback. CLI = `python -m core.knowledge.sync <dept>` (생략 시 8 dept). `tests/test_knowledge_sync.py`(6) 신규 = pytest **128 passed** (122 → +6). 4-단계 회로 검증 (add 1 / modify 1 / delete 1 / DB 4 row) 정확. 1 commit + push (`0aadf8a`)
- **Phase 2 M3: watchdog 자동 색인 + justfile 정리** (2026-05-11, 같은 날 두 번째 세션) — `core/knowledge/watcher.py` 신규 (watchdog Observer + `_Debouncer` threading.Timer dept 단위 coalesce + `_extract_dept` `_` prefix dept None + `_build_handler` `is_directory` skip / `moved` 시 src+dest 둘 다 처리 + `start_observer`/`stop_observer`/`run_forever` standalone + CLI `--reference-root`/`--debounce`). `core/knowledge/sync.py` 확장 (`sync_dept(force=False)` drop 직전 prev 카운트를 deleted 로 적재 → collection drop → 전체 added 재구축, `recent_runs(limit, dept)` helper, `_format_status_row` 1줄, CLI `--force`/`--status`/`--limit`, `_open_collection(drop_existing=)`). `server/main.py` lifespan startup 에 `start_observer()` 자동 등록 + `sync_all` fire-and-forget reconcile (BGE-m3 cold load 회피) / shutdown 에 reconcile_task cancel + `stop_observer`. `justfile` 정리 — 기존 3 명령 (`knowledge-sync` 구 OneDrive 추출 / `-ingest` / `-reingest`) 제거, 신규 5 명령 (`knowledge-sync` delta / `-rebuild` force / `-status` DB log / `-watch` standalone / `-browse` 유지). 외부→reference 이동은 사용자 manual 결정. `tests/test_knowledge_watcher.py`(7 cases: `_extract_dept` 3 + `_Debouncer` 3 + Observer 통합 1) 신규 = pytest **134 passed** (128 → +7, 회귀 0). 수동 회로 검증 4-단계 (add 1 +1/~0/-0 / modify 1 +0/~1/-0 / delete 1 +0/~0/-1) 적재 정확. server log: `watcher_started` + `knowledge_reconcile_done` 자동 등록 확인. 2 commits + push (`3228eb5` M3 코드 + `c078541` chore: sqlite-db MCP entry 제거).
- **사전 부채 보강: market_snapshot mixed 테스트 시각 freeze** (2026-05-11, 같은 날 세 번째 세션) — `tests/test_market_snapshot.py::test_render_data_source_line_mixed` 에 `_FrozenDateTime(datetime)` 클래스 + `monkeypatch.setattr(snap_mod, "datetime", _FrozenDateTime)`. freeze 시각 = 2026-05-12 (화) KST 20:30 → KR threshold ~6h (kr_age 3일 stale → fetch), US threshold ~13.5h (us_age 12h fresh → DB). pytest **135 passed** (134 → +1, 회귀 0) 베이스라인 회복. 1 commit + push (`a10f651`).
- **ANALYST-PERSONAS-001 SPEC 신설 + 자산전략가 v1→v4 4 회 반복** (2026-05-12, 네 번째 세션) — `docs/specs/ANALYST-PERSONAS-001-nine-analyst-portable-personas.md` 신설. 8-섹션 portable 양식 정식 정의 (Identity / Domain Frame / Inputs / Outputs / Reasoning Doctrine / Knowledge Categories / Anti-patterns / Cross-Agent Boundaries) + 9 분석가 ID·dept·canon_categories 매핑 표 (`principle_guardian` / `trader` / `market_state_analyzer` / `stock_picker` / `stock_analyst` / `wealth_strategist` / `trading_journalist` / `flow_analyzer` / `news_curator`) + identity seed Phase A-B-C 흐름 + SLOT (S5 미 매크로 collector / S6 LLM tool use). `agents/analysts/wealth_strategist/persona.md` 4 회 재작성 (v1 5→8섹션 portable / v2 격자 5요소 강제 / v3 Task trigger 분기 + Inputs 재조정 + Anti-patterns 책 인덱싱 차단 / v4 자연어 default 우선 + negative trigger 명시). `manifest.yaml` canon_categories 6개 정렬 + response_rules 시스템 [5] 블록 강화. CLI 4 호출 검증 통과 (J커브 정의 질문 격자 안 나옴 / 표 요청 질문 격자 나옴). 그러나 **webapp 사용자 호출 "J커브가 뭔지 설명해줘" 에 격자 박힘 → LLM 추종력 한계 노출**. 페르소나 layer 만으로 100% 분기 결정론 불가능 결론. pytest 135 passed 유지.
- **ANALYST-PERSONAS-001 v3.1 cited + 근거 명제 풀이 양식 정정** (2026-05-17) — v3 의 `cited: [<ID>]` 한 줄만 출력에서 v3.1 = 코드 마커 + 자연어 풀이 **이중 grounding** 양식으로 정정. `근거 명제 풀이:` bullet (각 ID 마다 한 줄 자연어 정의) 추가. persona.md 자연어 양식 블록의 풀이 3 줄 `- ` bullet prefix 정정, manifest.yaml `### 인용 규칙 (v3.1)` 블록 정리 (헤더 + `#####` prefix 제거 + YAML literal block 깨뜨리던 코드펜스 ``` column 0 정리 + v3 잔재 중복 2 줄 삭제), SPEC heading `(v3)→(v3.1)` + 격자 5요소 표 `[4] Citation` row v3.1 갱신 + 중복 격자 5요소 표 (lines 148~157) 삭제. ask_analyst 스모크 통과 (`cited: [...]` 한 줄 + bullet 10 개 자동 출력 확인, gemini-2.5-flash, $0.0012, 22s). pytest 135 passed 회귀 0.
- **wevelStock v3.0 메타 페르소나·시스템 아키텍처 재설계 — R&D → 엔지니어링 인수인계 첫 사이클** (2026-05-17) — chat Claude Opus 와 본질 토론 결과물 2 메모 (`idea_memo/2026-05-17-wevelstock-rd-meta-design-by-chat-claude-opus.md` 시스템 아키텍처 + `idea_memo/prism-insight-비교차용2.md` v3.0 이원 트랙 페르소나 디자인) 를 SPEC 3 개 + CLAUDE.md/STRUCTURE.md 표 갱신으로 명문화. 코드 변경 0.
  - `docs/specs/ANALYST-PERSONAS-001-...md` **v1 → v2** — frontmatter version 2 + generates 에 `collectors/scoring.py` 추가 + 새 § 5 개 (**9+3+1+회고N 골격 §** / 16 페르소나 흡수 매핑 표 — 신규 5 명만 ⭐ (#3 Regime / #9 Trigger / #11 Distribution / #12 Trailing / #16 Track Selector), 나머지 11 명 9 분석가 자연 매핑 / **결정론 채점 권위 § (옵션 b 채택)** — 공식 = `collectors/scoring.py` 순수 함수 / canon = 원리·렌즈만 / **한국어 친화 용어 강제 §** — "주도주 점수 8 (S-Score=8)" 패턴, 5 점수 한국어 이름 (주도주/타점/가속계수/매수/수급) / **F-Score (수급 점수) 신설 §** — `flow_analyzer` 발행, 4 축 가중치 (테마-주체 매칭 0.4 + 모멘텀 0.3 + 자금 속도 0.2 + 일치도 0.1) / 5 → 8 섹션 매핑) + SLOT S7 (`scoring.py` 시그니처) · S8 (테마-주체 매핑 dictionary) · S9 (한국어 용어 § 9 분석가 적용 범위) 추가
  - `docs/specs/STRATEGY-TRACK-001-two-track-strategists.md` **신설** — Layer 3 Track A (중장기 수익금 게임, 자본 70-80%·승률 70%+·MDD -8% 보호·월봉 7월선 위계) + Track B (단기 손익비 게임, 자본 20-30%·R/R 1.5:1+·trailing stop·6 트리거 + Distribution kill switch) 정식 분화. **α 가속계수 오버라이드 룰** (1.3-1.5 T max 5 / 1.5-2.0 T max 7 / 2.0+ T min 3, 로그 발산 구간 참여 강제). **Track Selector = manifest `input_routing` 블록** (별도 페르소나 X, 명시 단축어 `long:`/`swing:`/`both:` 우선 → auto.conditions → fallback). **plugin 확장** = `agents/strategists/<new_track>/` 드롭만으로 Track C 가능 (코드 변경 0). `strategist-recommendation-v1` 계약 (권고 ID·진입가·목표가 3단·stop_loss·R/R·cited_scores 인용)
  - `docs/specs/GUIDANCE-ACCURACY-TRACKER-001-five-kpi-tracking.md` **신설** — 적중도 5 KPI (방향 적중률 / 타점 정밀도 A·B·C·D 등급 / R/R 실현율 / 자가 진단 정확도 🔴 라벨 / 트랙 분리 효과) + 트랙별 가중치 차별 (Track A 종합 = 방향 30 + 타점 15 + R/R 15 + 자가진단 15 + 분리 25 / Track B 종합 = 방향 15 + 타점 20 + R/R 35 + 자가진단 15 + 분리 15). `guidance-record-v1` 계약 (권고 ID + 30·60·90 일 가격 추적). `guidance_records` 테이블 schema + 가격 추적 cron (daily 18:00 KST) + `회고` 단축어 양식 + DB ON CONFLICT REPLACE 멱등성
  - `CLAUDE.md` — 5-Layer 표 → **9+3+1+회고N 골격** (Layer 5 회고분석가 N 제한 X, 신규 부서 효율성 판단 = 회고분석가 영역). 전략가 라우팅 § Track A/B 갱신 (단타·중장기 삭제)
  - `docs/STRUCTURE.md` — 9/9/2+/1+/N 표 + 9 학습부 1:1 매핑 (mechanics → trading 외 5 신규 = market_macro·stock_selection·trading_journal·flow_analysis 추가) + Layer 3 트랙 표 + plugin 패턴 회고분석가 추가 + canon 트리 9 학습부 × 36 카테고리 정합 + `agents/` 폴더 설명에 retrospect/N 추가
  - 메모리: `feedback_concise_summary_first.md` 신설 + MEMORY.md 인덱스 1 줄 — 긴 분석 글 끝에 "한눈에 무엇을 하라" 명료 요약 강제
  - 검증: validate.py 0 errors / pytest **135 passed** 회귀 0
- **collectors/scoring.py 5 함수 결정론 채점 + 잠정 풀이 정정** (2026-05-17 Top 2 첫 실체) — 5 함수 시그니처 잠금 (SPEC 권위) + F-Score 4축 가중 합 + α 오버라이드 3 구간 정확 구현 (placeholder = s_score/buy_score 합산 + alpha 본체). `wealth_strategist` 잠정 풀이 4 정정 (M2/C1/I2/C3, canon 원문 frame 1:1 grep). pytest 195 passed
- **Track A persona + manifest + 외부 R&D 리뷰 5 항목 정합 + SPEC 격자 frame 정정** (2026-05-18, commit `ba04313`) — `agents/strategists/track_a/persona.md` 8 섹션 portable (부동산 임대업 비유 + 6 분석가 team_outputs read + strategist-recommendation-v1 권고 양식 + 한국어 친화 용어 + cited 풀이 v3.1) + `manifest.yaml` (reads_analysts 6 + canon_categories 9 dept framework 6개 + input_routing + llm.temperature=0.4 + response_rules). 외부 chat AI Opus 리뷰 5 항목 정합: #2 α 오버라이드 표 가드 (책임 분리) / #3 출력 양식 분기 룰 (권고 YAML trigger + 자연어 응답) / #4 yesterday_verdict_delta 강제 필드 (시점 일관성 자각, 격자 [5] 미러) / #5 input_routing 임계값 운용 슬롯 코멘트 / #6 옵션 A 확정 (holding_period_estimate_days = stock_analyst 발행 위임). SPEC ANALYST-PERSONAS-001 격자 예시 line 207-209/225/228 정정 (C3 → C1 / 통화 가치 → 원화 구조 / Dalio 5 → 4단계)
- **Layer 3 production 사이클 가시화 — core/strategist/ + CLI + FastAPI + webapp Layer 2/3 토글** (2026-05-18, commit `e8fc71f`) — `core/strategist/{__init__.py, run_strategist.py}` Layer 3 호출 엔진 (분석가 점수 주입 패턴 + metadata 신규 키 track/target/analyst_published/missing_count/missing_ids), `scripts/{ask,chat}_strategist.py` CLI + justfile 2 레시피 + `/target <ticker>` 명령, `server/api/strategist_chat.py` 3 endpoint (POST /chat + /chat/stream SSE + GET meta) + `server/main.py` 라우터 등록, `webapp/src/app/analyst-chat/page.tsx` Layer 2/3 토글 + AgentMeta 유니온 + target 필드 + MetadataBar scores X/Y 라벨. `tests/test_run_strategist.py` 11 + `tests/test_strategist_chat.py` 9 신규. pytest **215 passed** (+20, 회귀 0). `.gitignore` 에 strategist_queries 추가
- **production 첫 호출 검증** (2026-05-18, gemini-2.5-flash, $0.0019, 15.2s first 11142ms) — 사용자 webapp Track A 호출 (target='삼성전자'). 분석가 6명 모두 미발행 상태에서 Track A 가 `verdict=wait` + `confidence=10` + `cited_scores` 모두 null + `yesterday_verdict_delta="first run"` + cited 풀이 v3.1 + 한국어 친화 용어 (주도주 점수·가속계수·수급 점수) 정확 발행. **결정론 시그니처 잠금 + Anti-patterns 환각 차단이 production 작동 검증** ✨
- **Track B persona + manifest + track_selector + 테스트 25** (2026-05-19) — `agents/strategists/track_b/{persona.md, manifest.yaml}` 8 섹션 portable (1 파 사이클 카페 운영 비유 + reads_analysts 5 + canon_categories 3 principles/market_regime_rules·trading_doctrine + trading/operational_safeguards + input_routing shortcuts ["swing:", "short:", "trigger:", "both:"] + temperature 0.4 max_tokens 5000 + response_rules). `core/strategist/track_selector.py` (모든 전략가 manifest input_routing 동적 인식 + 단축어 dispatch + both: fast-path + fallback, auto.conditions v1 placeholder). `core/strategist/__init__.py` select_tracks export. `tests/test_track_b_strategist.py` 7 + `tests/test_track_selector.py` 18 신규 = pytest **240 passed** (215 → +25, 회귀 0). production 첫 호출 검증 2회 (CLI claude_code $0.19 OAuth 무료 67.5s + webapp gemini $0.0014 20.6s scores 0/5, 양쪽 환각 차단 + 한국어 친화 용어 + canon 명제 ID 풀어쓰기 작동) ✨
- **자료 0 시드 5 분석가 페르소나 v2 — 5 subagent 병렬 dispatch** (2026-05-19) — `agents/analysts/market_state_analyzer/` (시장 체제 6단계 + DD kill switch, 풍향계 비유, 변곡점 3 케이스 cross-reference trigger) / `agents/analysts/stock_picker/` (S-Score + buy_score G1 양쪽 발행 강제, 두 모자 비유) / `agents/analysts/trading_journalist/` (매매 일지 + post-mortem + prism-insight 차용 PROPOSAL, Layer 5 boundary 분리) / `agents/analysts/flow_analyzer/` (F-Score 4축 가중 합 0.4·0.3·0.2·0.1, 4-tier 비유, "가격은 수급의 부모" 인용) / `agents/analysts/news_curator/` (단기 테마 / 장기 흐름 / 지정학 3 분류, 자료원 SLOT S2 미결정, canon_categories 빈 list). 모두 8 섹션 portable + 한국어 친화 용어 + cited 풀이 v3.1 + 박종훈 framework 직접 인용 금지 가드 일관 박힘. **`superpowers:dispatching-parallel-agents` 첫 적용** = 1 message 5 Agent tool calls, 소요 ~5 분, 총 ~1,800 줄. `tests/test_seed_analysts_v2.py` 38 cases 신규 = pytest **278 passed** (240 → +38, 회귀 0). production 첫 호출 검증 (market_state_analyzer, gemini-flash, 3 시나리오 합산 ~$0.0025): 평상시 자료 0 자각 / 변곡점 trigger 시도 (자료 0 자각 우선) / boundary 침범 시 wealth_strategist 권위 영역 위임 명시 ✨
- **박종훈 framework scope 메모리 정밀화** (2026-05-19, 사용자 2차 발화) — `feedback_park_jonghoon_scope.md` 본문 갱신: "거시적 경제 해석 통찰 = 트레이딩보다 한 차원 상위 frame", "시장 변곡점 발생 시에만 들여다 보는 큰 길잡이", 변곡점 3 케이스 정의 (regime 전환 / DD 4건+ / 사이클 단계 변화) 추가. market_state_analyzer 특수 가드 항목 추가. MEMORY.md 인덱스 1 줄 갱신
- **INFRA-FUNDAMENTAL-DATA-001 SPEC 5 라운드 면담 신설** (2026-05-20 cycle 9 SPEC only) — RESUME Top 2 진입. `/spec-interview` skill ritual 로 5 라운드 면담 결정 5 건 박힘: **R1** yfinance Phase 1 단독 (DART/KIND/hybrid 제외, MVP 1 세션 가능 + 한국·미주 자동 처리 + API 키 불필요, DART 이중 검증은 Phase 2 `INFRA-FUNDAMENTAL-CROSS-VALIDATE-001` 별도 SPEC) / **R2** Default 8 필드 = (1) EPS TTM (2) PE 현재 (3) ROE (4) operating margin (5) debt/equity (6) 분기 매출 4 분기 (7) 분기 영업이익 4 분기 (8) 분기 EPS 4 분기 — F5 (실적 모멘텀 QoQ·YoY) + F2 (펀더멘털 양호도) 양쪽 동시 해소, SLOT 4 (forward EPS·PE·배당수익률·현금흐름) 는 Phase 2 / **R3** DB-first hybrid + cache TTL 24h + APScheduler 주 1회 cron (일요일 18:00 KST), `fundamentals` 테이블 + `core/db/migrations/v6_fundamentals.sql` schema_version 5→6 / **R4** `fundamental_data_md [5]` 블록 신설 (chart [4] 직후 RAG 직전) + stock_analyst manifest `reads_fundamental_data: true` 플래그 + persona v4 3 위치 정정 (§ Reasoning Doctrine F2/F5 정의 row / § Outputs 격자 [1] Quality Grid F5/F2 unknown 강제 해제 / manifest response_rules 가드 2 정리), chart v3 정정 패턴 1:1 미러, MS3 완전 도달 명시 / **R5** 본 사이클 = SPEC frozen 만 (INFRA-CHART-DATA-001 cycle 5 패턴 미러), 구현 15 단계는 다음 사이클 cycle 10 (~2 세션). `docs/specs/INFRA-FUNDAMENTAL-DATA-001-fundamental-data.md` 신설 (~330 줄, frontmatter generates 9 + modifies 8 + depends_on 2 + contracts 1 `fundamental-data-md-v1`). non-goals 7 + SLOT 5 + 영향 SPEC 3 + 구현 순서 15 단계 + 테스트 케이스 5 파일 (~18~20 케이스). 코드 변경 0. validate.py 0 errors. commit 진행 (SPEC + wrap-up 묶음, cycle 5 ad6ec07 패턴).
- **ask_strategist/chat_strategist httpx wrap + operational_safeguards SPEC 정정** (2026-05-20 cycle 7) — RESUME Top 2+3 묶음 commit (회장 핑퐁 [22] 권유 그대로). **Part A** = `scripts/{ask,chat}_strategist.py` in-process `run_strategist` 임포트 제거 → `POST /api/strategists/{id}/chat` httpx wrap (cycle 4 ask_analyst L78-149 패턴 미러). target/provider/messages 필드 + REQUEST_TIMEOUT_SECONDS 180s + WEVELSTOCK_SERVER_URL env. 에러 분기 (ConnectError exit 3 / ReadTimeout exit 4 / 404 exit 2 / 5xx exit 1). `_format_metadata` 의 track/target/scores published/missing 라벨 보존. chat 측은 `/exit /clear /save /target <ticker>` 4 명령 보존. `tests/test_ask_strategist_http.py` 6 케이스 신규 (_MockClient 패턴, test_ask_analyst_http 미러). cycle 3 메모리 압박 위험 잔존 제거 (INFRA-RUNTIME-EFFICIENCY-001 v3 patch). **Part B** = `ANALYST-PERSONAS-001` v2 매핑 표 L347 정정 (trader 행에서 `trading/operational_safeguards` 제거 + principle_guardian 행에 추가, canon 파일 위치 그대로 유지 — canon_categories 키 형식 `<dept>/<category>` 가 dept 정보 박는 구조라 파일 이동 불필요, frontmatter `analyst: principle_guardian` 와 정합 회복) + trader persona+manifest 5 위치 정리 (canon_categories 6→5, cycle 3 임시 위임 명시 잔재 청산) + principle_guardian persona+manifest 보강 (canon_categories 3→4, 자료원 4 § "manifest 에 추가 X" → "정식 포함" 갱신) + `tests/test_data_analysts_v2.py` 회귀 갱신 (`EXPECTED_CANON_CATEGORIES` + `test_trader_operational_safeguards_delegation` 삭제 + `test_principle_guardian_owns_operational_safeguards` 신규 3-way 검증). pytest 379 → **385 passed** (+6 신규, 회귀 0). validate.py 0 errors. mock smoke (`ask_strategist track_a "Track A 본질" --target 005930 --provider mock`): httpx 호출 + metadata 정합 + JSONL 저장 OK. commit `78d8246`.
- **Production smoke 검증 + KIS 토큰 공유 + webapp 분할/select + 종목명 매핑** (2026-05-20 cycle 6.5) — cycle 6 INFRA-CHART-DATA-001 구현 풀세트의 production 검증 단계. 4 본질 보강: (1) `KISClient` class-level `_shared_token` + `asyncio.Lock` (lazy init) = 같은 KIS_APP_KEY 모든 인스턴스 토큰 reuse, "1분당 1회" 발급 한도 충돌 해소 / (2) `server/api/analyst_chat.py` `ChatRequest.target_ticker` kwarg + chat/stream 양쪽 전달 / (3) `webapp/src/components/ChatPane.tsx` 신규 (~370 줄, props: kind/agents/showTickerField + MetadataBar 에 chart_source 컬러+ohlcv 봉수+failures tooltip) + `webapp/src/app/analyst-chat/page.tsx` 단일 → 좌(분석가) 우(전략가) 분할 (lg:grid-cols-2) + 9 분석가 + 2 전략가 하드코드 select box + stock_analyst 선택 시만 ticker 조건부 노출 / (4) `core/inference/run_analyst.py` `resolve_ticker(raw)` 헬퍼 + `KR_NAME_TO_TICKER` 35종 (KOSPI 상위 25 + KOSDAQ 상위 10) + `_normalize_name` 공백·대소문자 정규화 + 미매핑 시 `chart_failures=['ticker_resolve_failed:<입력>']` + `render_chart_data_md(name=display_name)` 한글명 헤더 노출 / UI placeholder "예: 005930 또는 삼성전자" + 라벨 "종목" + 빈 값 시 amber `⚠ 입력 필요` 경고. pytest 376 → **379 passed** (+3 신규 resolve_ticker, 회귀 0). webapp typecheck 0 errors. **mock provider production smoke**: "삼성전자" → 005930 매핑 + chart_source=db (1825봉) + system_prompt_chars 31,474 ✅ / "알수없는종목명" → ticker_resolve_failed + system_prompt_chars 29,482 (chart 미주입) ✅. **별도 발견** = `provider="claude_code"` silent HTTP 500 (body 빈 message, mock/gemini 정상) → Top 1 백로그. commit `27d788c`.
- **INFRA-CHART-DATA-001 구현 풀세트 + stock_analyst v3 마이크로 정정** (2026-05-20 cycle 6 풀세트, 야간 자율 실행) — `collectors/charts.py` 신규 (~470 줄, KIS get_daily_chart 페이징 fetch + on-demand snapshot 7 필드 + Default 6 지표 pandas rolling/ewm 직접 계산 + DB-first hybrid + 60s 인메모리 TTL + 3-tier fallback + refresh_all_tickers CLI) + `core/db/migrations/v5_chart_ohlcv.sql` + `schema.sql` schema_version 5 + `connectors/kis/client.py` 2 메서드 (`get_daily_chart` FHKST03010100 페이징 25회 가드 + `get_current_price` stock_price wrap) + `compose.build_pipeline_prompt(chart_data_md=)` kwarg + `[4]` 블록 (snapshot 직후 RAG 직전) + `core/inference/run_analyst.py` `AnalystSpec.reads_chart_data` + `_maybe_build_chart_data_md` 헬퍼 + run_analyst/run_analyst_stream 양쪽 `target_ticker` kwarg + 7 chart metadata 키 + `stock_analyst` persona+manifest v3 정정 3 위치 (환각 가드 2 해제, chart_data_md [4] 출처 명시 강제, verdict=unknown 강제 → inconclusive 로 변경, F1/F4 = chart 주입 시 활성) + `server/schedulers/jobs/charts.py` + `register_infra_jobs` 평일 18:00 KST 고정 cron + `justfile` refresh-charts/fetch-chart 2 레시피. pytest 341 → 376 passed (+35 신규, 회귀 0). 자율 결정 3 = pandas-ta 미사용 (직접 계산) + target_ticker = manifest reads_chart_data + run_analyst kwarg + async + 임계 분리 (_FRESH_MAX_HOURS=26 / _STALE_MAX_HOURS=168). 부수 정정 = INFRA-RUNTIME-EFFICIENCY-001 frontmatter (generates: [] + contracts 키 제거). MS3 부분 도달.
- **`INFRA-CHART-DATA-001` SPEC 신설** (2026-05-20 cycle 5 SPEC only) — `docs/specs/INFRA-CHART-DATA-001-chart-data.md` 340 줄. 5 라운드 면담 결단 누적: R1 공용 인프라 (`collectors/charts.py`, 5 분석가 잠재 소비자) + Phase 1 텍스트 / Phase 2 vision 분리 / R2 KIS daily 5년 1825봉·수정주가·8컬럼 / snapshot 7필드 / pandas-ta Default 6 (월봉 7·20MA + 주봉 10·20·60MA + 일봉 4·7·20·60·120MA + MACD 12-26-9 + 거래량 20일이평 spike + 52주 고저) + SLOT 2 (RSI·볼린저, WAVE-ALPHA-001 후) / `chart_data_md` kwarg `[4]` 블록 (market_snapshot_md 미러) / `chart_ohlcv` 테이블 + lru_cache + 60s TTL / R3 기존 `connectors/kis/client.py` 재사용 (`get_daily_chart` + `get_current_price` 추가) + APScheduler `0 18 * * 1-5` cron + `just refresh-charts` 백업 + 3-tier fallback (5 영업일 stale + 부분 발행 + last cache) / R4 6 묶음 ~33 케이스 + TESTING=1 mock 강제 / R5 15 단계 구현 순서 + SLOT 7 (`<!-- SPEC:INTERVIEW-SLOT -->` 마커, α anchor·RSI/볼린저·watchlist·yfinance·호가창·F5 분기실적·Phase 2 vision) + schema_version 4→5 + 4 SPEC 영향. frontmatter generates 8 + modifies 9 + depends_on 2 + contracts 1 dict (`chart-data-md-v1`) 단독 파싱 통과. **회장 결단 = SPEC frozen 만** (구현은 다음 사이클 1 세션). **부수 발견**: `INFRA-RUNTIME-EFFICIENCY-001` v2 frontmatter 2 validation 에러 (`generates=None`, `contracts.0=str`) — 다음 사이클 Top 2 (`ask_strategist` httpx wrap) 동일 commit 정정 의제
- **WAVE-ALPHA 14.0 + 14.1 풀세트** (2026-05-22 cycle 14 impl, 같은 날 세 번째 세션, commits `98cbf32` + `a536428`) — **14.0 SLOT S4 KIS fallback** = `collectors/market_macro.py` 의 `_fetch_breadth_kis_fallback(market)` 신규 (KIS volume_rank top30 의 change_pct 분포 → advancing/declining 카운트), `MarketMacro.breadth_source` 메타데이터 ("krx" / "kis_volrank_top30" / "unavailable") = 분석가 한계 노출. **14.1 풀세트** = (1) **canon 21 명제** `knowledge/canon/stock-analysis/fractal_wave/01-anchor-and-alpha-formula.md` 신규 (WA1~WA5 anchor 정의 + WF1~WF4 시간 정규화 공식 + WL1~WL4 label·verdict·holding_period + WE1~WE7 엣지 + WX1 framework 본질), `_category.yaml target_analysts=[stock_analyst]` 활성 (2) **DB v8** = `manual_anchors` 테이블 신규 + `llm_call_cache.type` 컬럼 추가, `schema.sql` 통합 + `migrations/v8_wave_alpha.sql` reference (3) **`collectors/scoring.py` alpha() 정식** = 시그니처 `(Anchor=tuple[date,float]×4)`, 시간 정규화 `α=k₂/k₁`, 신규 `interpret_alpha` 5단계 timeframe 차등 + `progress_to_b` + `duration_ratio` + `THRESHOLDS` + `TIMEFRAME_LIMITS` + 가드 (WE2 k1_flat → None / WE3 trend_broken / 시간 역행 raise) (4) **테스트** = `TestAlpha` 13 케이스 새 시그니처 재작성, `test_snapshot_extend_db` v7 hardcoded 정정. pytest 468 passed (467 → +1, 회귀 0). 14.2 anchors.py + α 3 timeframe 통합 / 14.3 persona v3→v4 + 테스트 풀세트 + smoke 별 세션.
- **Track A·B 본질 재정의** (2026-05-19, 외부 R&D 피드백 + 사용자 본질 의도 정합) — 기간 기준 → 전략 본질 기준. **Track A = "추세 추적 + 분할 운용"** (월봉 7월선 위계 유지·F1 이탈 시까지 보유·연 5-15회 회전·MDD -8%·결과적 보유 3 개월~수년·**타점 맞으면 큰 진입 / 애매하면 역피라미드 분할** 저점 50%·중간 30%·상단 20% 저점 비중 크게 평단 머리 무겁지 않게). **Track B = "프랙탈 1 파 사이클"** (저점~고점 1 파 회수가 최대 목표·실적·장기 무관·R/R 1.5+ 백업 가드·결과적 보유 일~수주·1 파 완성 시 trailing stop 잔여 확장·1 파 완성 후 추세 더 가는 종목 Track A 자연 인계). display_name 본질 표기 (Track A 추세 추적 전략가 / Track B 프랙탈 1 파 전략가). SPEC § 분석가 페르소나 작성 가드 (G1 stock_picker S-Score + buy_score 양쪽 발행 강제 / G2 trader 6 트리거 영문 ID 고정 + Track B 명단 변경 시 동시 수정) + § 의사결정 SLOT (S8 자본 단위 분모 통일 — Layer 4 계좌관리자 작성 시 동시 갱신 강제). Track A persona + manifest + Track B persona + manifest + STRATEGY-TRACK-001 SPEC + 테스트 키워드 일관 박힘 (persona ↔ SPEC ↔ test 균열 회피)

### 미완 또는 의도적 공백
- **`team_outputs` DB 적재 인프라 부재** — Track A·B + 9 분석가 호출 결과를 DB 적재하는 호출처 0 (run_strategist/run_analyst 는 LLM 호출까지만, persist_output 호출은 wrap 측). GUIDANCE-ACCURACY-TRACKER-001 SPEC 후속
- ~~**provider="claude_code" silent HTTP 500**~~ — **cycle 8 해소** (2026-05-20). NotImplementedError (SelectorEventLoop) + 빈 메시지 fallback 부재 본질 = (1) backend 메시지 보강 4 위치 (2) `call_claude_code` 도 `_can_spawn_subprocess()` 사전 체크 + sync 직행 (3) client.py 1회 retry (4) endpoint detail fallback. production smoke 통과 ✨ (`claude_code` 14.9s 응답 + cited [C1] + $0.1404).
- **F5·F2 unknown 잔존 (stock_analyst v3)** — cycle 6 chart 풀세트로 α·F1·F4 활성화했으나 F5 (실적 모멘텀) + F2 (펀더멘털 양호도) 만 unknown 잔존 = MS3 완전 도달 차단. cycle 9 SPEC frozen 완료, cycle 10 구현 풀세트 (~2 세션) 후 해소 예정.
- **SPEC frontmatter ↔ canon frontmatter 일관성 자동 검증 부재** (cycle 7 발견) — `scripts/validate.py` 가 SPEC canon_categories 매핑 ↔ canon 파일 frontmatter `analyst:` 키 일관성을 검증하지 않음. cycle 3 의 operational_safeguards 부채 (4 사이클 잔존) 같은 미스 재발 위험. 별도 작은 SPEC 백로그.
- **종목명 매핑 35종 외 + alias/약칭** — 시총 상위 35만 하드코드. "삼전" / "네카오" 같은 일상 어휘 미지원. KRX 종목 마스터 자동 sync 는 `INFRA-TICKER-RESOLVER-001` 후속 SPEC.
- **stock_analyst CLI `--target` 플래그** — `scripts/ask_analyst.py` 가 현재 `target_ticker` kwarg 를 받지 않음. run_analyst 는 받지만 CLI wrap 미진행. webapp 으로 검증 가능하므로 우선순위 낮음.
- **F5 (분기 실적)** = `INFRA-FUNDAMENTAL-DATA-001` 후속. MS3 완전 도달 차단점.
- **트레이딩 관점 분석가 framework 추후 정의** (백로그) — 박종훈 framework 와 분리된 트레이딩 일반 framework. 회고분석가 PROPOSAL 영역 또는 별도 SPEC. Top 1+2+3 안정 운용 후 진입 검토
- **자본 단위 분모 SLOT (S8) 미통일** — Track A persona § 분할 매수 룰 "50% 또는 한도의 70%" 두 분모 모호 (의도 비중 / 단일 종목 한도 / 계좌 전체). Layer 4 계좌관리자 페르소나 작성 시 자본 단위 합의 후 persona + SPEC 동시 갱신 강제 (이중 박음으로 SLOT 인지)
- **selector.py BOTH_SHORTCUT fast-path 처리 vs manifest opt-in 양식** — SPEC L218-225 의 외부 input_routing_both 권위와 manifest 양식 (track_a/b 모두 "both:" 박힘) 양립. fast-path 제거는 별도 SPEC 후속 (사용자 피드백 #2 "구현 별도 SPEC" 명시)
- **양 트랙 통합 production 검증 미진행** — `both: 삼성전자` 호출 시 양 트랙 동시 권고 + Track B 1 파 완성 시나리오에서 Track A 자연 인계 메커니즘 (응답 본문 명시) 검증 미진행. Top 3 (자료 0 시드 5명 작성 후)
- **`principles` dept 명제 ID 정식 정의 미완** — production 첫 호출 시 cited_propositions 가 `principles.operational_safeguards` 형식 (dept.category 경로) 로 fallback. principle_guardian 페르소나 작성 시 P1~P7 같은 정식 ID 확정 백로그
- **종목명 → ticker 자동 매핑 미작성** — webapp target 필드에 사용자가 "삼성전자" (한글) 입력 시 그대로 넘어감. `feedback_webapp_production_ux.md` 의 intent extractor 백로그
- **webapp production UX 미구현** — 현재 Layer 토글 + agent_id + target 노출 = R&D 검증용 임시. production = 하나의 LLM 채팅창, 백단 0 노출 (자연어 → 자동 라우팅). `feedback_webapp_production_ux.md` 박힘, 9 분석가 + Track Selector 안정화 후 별도 사이클
- **`collectors/scoring.py` 일부 공식 placeholder** — s_score (3축 균등 평균) / buy_score (CAN SLIM 7축 균등 평균) / alpha 본체 (`ln(C/B)/ln(B/A)`) 는 placeholder. 정식 공식 = 분석가 manifest 작성 시 (s/buy 가중치) + WAVE-ALPHA-001 SPEC (alpha 본체) 에서 확정. F-Score / α 오버라이드만 SPEC 명시 공식 정확 구현
- **나머지 8 분석가 페르소나 작성 (v2 양식)** — 자료 있는 3 (`principle_guardian` / `trader` / `stock_analyst`) + 자료 0 시드 5 (`market_state_analyzer` / `stock_picker` / `trading_journalist` / `flow_analyzer` / `news_curator`). v2 양식 = 8 섹션 portable + 한국어 친화 용어 강제 § + 결정론 채점 발행 매핑 (S/T/α/buy_score/F-Score). Track A·B 안정화 후 진입
- **`SLOT S8` 미정의** — F-Score 의 테마 분류·권위 주체 매핑 dictionary (`config/runtime.yaml` 의 `flow_analysis.theme_authority`). 운용 데이터 누적 후 회고분석가 PROPOSAL 영역
- **`SLOT S9` 미결정** — 9 분석가 응답 양식 한국어 용어 § 적용 = manifest 별 박기 vs compose 공유 블록 추출. 자료 있는 4 명 작성 후 결정
- **compose 분기 인프라 (격자 trigger 동적 주입)** — 페르소나 layer 만으로 LLM 분기 결정론 불가능 결론은 유지. 본질 해결 = `core/knowledge/compose.build_pipeline_prompt` keyword trigger 분기. v2 양식 (Outputs Task trigger 분기) 으로 일부 완화되었으나 LLM 추종력 한계 잔존. 9 분석가 페르소나 작성 시 재평가
- **미국 매크로 collector 부재** — 자산전략가 frame 의 핵심 입력 (미 10년물·달러인덱스·VIX·미 부채 잔액) 이 `collectors/snapshot.py` 에 미적재. v3 페르소나가 "snapshot 없음, framework 밖" 으로 솔직히 답하긴 하나 grounding 인프라 자체가 빈 상태. 새 SPEC 후보 `INFRA-US-MACRO-SNAPSHOT-001`
- **차트 데이터 인프라 구현 0 (SPEC frozen)** — `INFRA-CHART-DATA-001` SPEC 신설 완료 (2026-05-20 cycle 5, 340 줄). 코드·테스트 진입 0. stock_analyst 환각 가드 2 (INFRA 미구현 → `verdict=unknown` 강제) 아직 활성, α·F1·F4·목표가 3 단 발행 차단. 다음 사이클 Top 1 구현 풀세트 후 MS3 부분 도달 (F5 분기 실적만 잔존 → `INFRA-FUNDAMENTAL-DATA-001` 후속).
- **36 카테고리 `_category.yaml` 의 `target_analysts` 채우기** — 현재 100% 비어있음. ANALYST-PERSONAS-001 SPEC 의 매핑 표가 ground truth. 자료 있는 4 dept 페르소나 완성 후 채움
- **KNOWLEDGE-SYNC-001 Phase 2~5 구현** — Phase 1 ✅ / Phase 2 M1 ✅ (retrieve 카테고리 필터 + compose canon_categories) / Phase 2 M2 ✅ (DB knowledge_index_runs + sync.py delta 인덱싱) / Phase 2 M3 ✅ (watchdog 60s debounce + justfile 5 명령 정리 + server lifespan 자동 등록) — **Phase 2 풀세트 = 프로토타입 1차 동작점** / Phase 3 canon 승격 PROPOSAL + release note LLM 자동 생성 (M3 분석가 분화 SPEC 후) / Phase 4 트리거 + 스킬 (`/knowledge-sync`, `/knowledge-review`) / Phase 5 풀 사이클 검증
- **다른 dept 재인덱싱** (principles / trading / stock-analysis 등) — Phase 2 sync 로 자동화 또는 수동 force re-index. stock-analysis 는 5형식 자료 풍부해 어댑터 검증 풍부 (백로그)
- **이미지 PDF OCR 미실행** — 박종훈 Vol 2/3 4 파일 + `9.프렉탈 구조 응용 - 실전분석2-2.pdf` 30페이지 0 chars. `ocrmypdf` + tesseract 백로그
- **png 어댑터 vision 활성화** — 비용 가시화 후 `enabled_by_default=True` flag + Anthropic vision API + extraction cache (`data/chroma/<dept>/_extraction_cache/<file_hash>.txt`). 현재 silent skip
- **xlsx 어댑터 sheet 별 분리 인덱싱** — 현재 단일 body (sheet header + tab-delimited). SPEC 528행 SLOT, 실제 자료 (4.로그차트_advanced/ xlsx) 보고 결정
- **streaming 토글 UI + AbortController** — webapp 의 streaming on/off 토글 + 응답 도중 cancel 버튼. default ON 유지하되 회귀 옵션 + 사용자가 응답 길어질 때 중단 가능. ~1.5h
- **streaming response cache (멱등성)** — `call_llm` 의 cache_lookup 패턴 streaming 용 미적용. text_delta 들을 모아 metadata 와 함께 저장하는 패턴 신규. 후속 백로그
- **claude_code 첫 토큰 ~12s 한계** — subprocess 부팅 + OAuth keychain handshake. CLI 자체 한계라 streaming 도입에도 단축 X. Anthropic SDK 직접 호출 (`provider="anthropic"`, ~2s) 가 답이지만 Pro/Max 무료 혜택 포기. 운영 합리적 타협으로 batch_thread fallback 채택
- **provider default = gemini 토글** — 5분 작업, 사용자가 매번 토글로 충분이라 미반영
- **Layer 3 종합 판단부 (단타·스윙·중장기 전략가 3종)** — CLAUDE.md L100-105 에 이미 설계 (M4 마일스톤). 단타전략가 (종목분석가+뉴스큐레이터) / 스윙전략가 (종목분석가+자산전략가+매매코치) / 중장기전략가 (자산전략가+종목분석가+원칙수호자). 분석가 5명 분화 후 자연 진입
- **NXT 통합 시세 도입** — KIS API 가 명시 미지원 (`_AL`/`_NX` suffix 빈 응답, GitHub repo 0건). 키움은 suffix 패턴 지원하나 KIS 와 다름. KRX backend + 키움 OpenAPI 등 다중 source 결합 SPEC 필요 — 별도 백로그
- **daily_briefing legacy 잔재** (`core/registry.py`, `core/config/schema.py`, `config/defaults.yaml` 의 daily_briefing 섹션) — webapp 측 `BriefingCard` 는 2026-05-07 제거됨. server/config 측은 의존성 그래프 큰 cleanup 세션 백로그
- **analyst-chat SSR 깜빡임** — 첫 렌더 시 "분석가 메타 로드 실패" 빨간 텍스트. hydrate 후 fetch 가 채우는 정상 동작이지만 UX 백로그
- **KRX backend 정규장 종가 일치 검증** — KIS 일봉 vs KRX 공식 종가 100% 일치 추가 보강. 1분 작업, 보강 백로그
- **나머지 4명 분석가 분화** (원칙수호자·매매코치·종목분석가·뉴스큐레이터) — Top 1 패턴 안정 후 동일 패턴 복사 (Top 2)
- **JSONL 매월 폴더 분리 + 90일 retention cron** — 5K 파일 임계점 도달 전 도입 (분석가 5명 분화 직전, Top 3 와 묶음)
- **자동 컴팩트 (50+ turn 대화 압축)** — 1 conversation 50 turn 넘으면 요약 호출로 messages 압축. 백로그
- **텔레그램 `/ask` 명령 wrap** — `core/inference/run_analyst()` 에 텔레그램 핸들러 1개 wrap 만 추가하면 모바일 사용 가능. 1명 검증 후
- **배치 자동 트리거 (T2) + team_outputs DB 저장** — 시장 컨텍스트 자동 주입 + 일정 주기 분석가 호출 → DB 누적. user_want_spec 의 자동 흐름. 후속 단계
- **`KnowledgeChunk.team_id` 필드** 가 dept 값을 담음 (legacy 호환). 별도 cleanup 세션에서 `dept_id` 로 rename
- **`compose.py`의 legacy `build_system_prompt` / `load_canon` / `load_persona`** — `get_team` 의존, 호출처 0. cleanup 세션에서 삭제
- **chat REPL stdin pipe 자동화** — PowerShell here-string 한국어 인코딩 깨짐. 사용자 콘솔 직접 입력은 OK (stdin reconfigure 적용됨). 자동 검증 필요 시 별도 스크립트로 우회
- **박종훈 Vol 2/3 OCR 미실행** (4 파일 0 chars, 이미지 PDF) — `ocrmypdf` + tesseract 도입 백로그
- **자료 0 dept 5종** (market_macro / stock_selection / trading_journal / flow_analysis / news + trading 의 일부 카테고리) — Phase 0 시드 카테고리만, 자료 0. 페르소나만으로 추론 시작 (M3 SPEC 의 자료 0 시드 5명)
- **전략가 3 / 계좌관리자 / 출력 채널 확장** — M4~M6, 한참 후
- **선물 수급 3주체 → 5주체 확장** — KRX MDCSTAT bld 캡쳐, 백로그
- **Phase 3 `market_briefing_close`** — 5-Layer M3 완료 후 자연 진입
- **dead code 청산** (`market_investor_summary`/`foreign_institution_top`/`core/registry.py`/`rollup.py`) — 회귀 리스크 큰 별도 세션
- **KOSPI200 선물 정확 가격** — 지수(2001) 대체. 선물옵션 API 별도
- **`docs/KNOWLEDGE-WORKFLOW.md` 5케이스 가이드** — 자료 추가 흐름차트 미작성

### 꼭 알아둘 판단

**이번 세션에 굳힌 판단 (2026-05-23 PRODUCTION-UX-001 SPEC 5라운드 면담 + 본문 작성)**
- **`/spec-interview` skill ritual 5 회 누적 ✨ → 영구 ritual 확고화**: cycle 5 (chart) / cycle 9 (fundamental) / cycle 12 (snapshot-extend) / cycle 14 (wave-alpha) / 본 cycle (production-ux) 모두 동일 패턴 = ~0.5~1 세션 SPEC + ~1~3 세션 구현 분할 + AskUserQuestion 5 라운드 옵션 (추천 first) + 결단 N 건 영구 권위 + frontmatter status. 본 cycle 은 skill 자체 호출이 ARGUMENTS 처리 이슈로 중단되어 **채팅형 직접 면담으로 진행** = skill 변형 가능. 미래 모든 인프라/제품 SPEC 신설 시 default 진입점.
- **사용자 본질 명료화 패턴**: 모호한 옵션 답변 ("이게 무슨 말?" / "캐싱이 뭐 캐싱?") 받으면 **쉬운 풀이 + 표 + 본질 frame** 제시 → 같은 옵션 재선택으로 결단 확정. R2-Q2/Q3 양쪽 활용. 사용자 시간 부담 최소 + 결단 확실성 강화. **본 패턴 = `feedback_concise_summary_first.md` 정신의 인터뷰 적용**. 미래 모든 면담에서 사용자 모호 답변 시 같은 frame.
- **캐싱 대상 frame 정립 (사용자 통찰)** = "시대 흐름 vs 시황 vs 표현 분류" 3 범주. Intent cache = 표현 매핑만 (시황·시대 X) → 30일 TTL 안전. 미래 cache TTL 결정 시 동일 frame 적용 가능 (분석가 답변·시세는 매번 실시간, RAG 청크는 reference 변경 시까지, 표현 분류는 30일).
- **SPEC frontmatter status enum 부채** = `frozen` 은 validate.py 위반 (`draft / approved / implementing / implemented / verified` 만 valid). WAVE-ALPHA-001 / SNAPSHOT-EXTEND-001 / CHART-DATA-001 / FUNDAMENTAL-DATA-001 / RUNTIME-EFFICIENCY-001 등 cycle 5~14 의 frozen SPEC 모두 일괄 정정 필요 = 작은 cleanup 백로그. 본 SPEC 은 `approved` 사용.

**직전 세션 판단 (2026-05-23 production UX 머티턴 조사 + LLM 3계층 정책 신설)**
- **머티턴 인터뷰 모드 ritual 검증** = 큰 SPEC 진입 전 본질 확인 ritual. 조사 (Explore 3) + 비교 (Plan agent 1) + 합의 (AskUserQuestion 점진 N 회) 패턴. 코드 0 세션의 가치 = 다음 세션 SPEC 인터뷰 즉시 진입 가능 + 7 결정 freeze 항목 사전 도출 = 면담 5 라운드 시간 단축. 미래 인프라/제품 SPEC 신설 시 큰 결정 5+ 항목 있으면 동일 ritual.
- **LLM 모델 3계층 정책 = 전 시스템 표준**: FAST=Flash-lite/Haiku 4.5 (Intent·JSON·자연어 변환) / BALANCED=Flash/Sonnet 4.6 (분석가·전략가 본문) / DEEP=Pro/Opus 4.7 (회고·메타). config `llm.tiers` + `llm.areas` 외부 설정 (코드 영역 → tier 라벨 → provider/model 분기). 미래 cycle 14 anchors.py + 분석가 9 + 전략가 + 회고분석가 M4 모두 동일 매핑 분리 마이그레이션. 비용/품질 trade-off 모델 교체 즉시 검증.
- **적용 범위 D 점진 패턴** = 신규 영역 즉시 + 기존 영역 후속 SPEC microcycle. 회귀 검증 분리로 광범위 회귀 위험 최소화. anchors.py 38 케이스 + 분석가 9 페르소나 smoke + 전략가 통합 동시 검증 회피. `LLM-TIER-MIGRATION-001` 후속 SPEC 영역별 1 PR 단위.

**직전 세션 판단 (2026-05-22 cycle 14.0 + 14.1 — WAVE-ALPHA 구현)**
- **sub-cycle 분할 ritual 5 회 누적 ✨ → 영구 ritual 격상**: cycle 5 (chart impl) / cycle 9 (fundamental spec) / cycle 12 (snapshot extend spec) / cycle 14 (wave-alpha spec) / 본 cycle (wave-alpha impl 14.0+14.1) 모두 "SPEC frozen → 작은 commit 분할" 동일 패턴. SPEC frozen 단독 commit + sub-cycle 별 commit (canon → DB → 핵심 함수 → anchors → persona → 테스트) = 큰 commit 위험 분산 + 검증 가능 단위. 미래 모든 인프라 SPEC 구현 시 default 진입점.
- **scoring.alpha() breaking change 영향 최소화 패턴**: 새 시그니처 `(float×4)` → `(Anchor=tuple[date,float]×4)` 교체 시 호출처 = `tests/test_scoring.py` 만 (코드). 다른 호출처 (persona.md / manifest.yaml / SPEC) = 문서 인용만, breaking X. 14.1 안에서 즉시 test 정정 + persona/manifest 는 14.3 별 세션. **자율 결정**: backward-compat hack (alpha_legacy rename / float|tuple overload) 회피, CLAUDE.md "no backwards-compatibility hacks" 정합.

**직전 세션 판단 (2026-05-22 cycle 14 — WAVE-ALPHA-001 SPEC 5 라운드 면담)**
- **`/spec-interview` skill ritual 4 회 누적 검증 ✨ → 영구 ritual 확고화**: cycle 5 (INFRA-CHART-DATA-001) / cycle 9 (INFRA-FUNDAMENTAL-DATA-001) / cycle 12 (INFRA-SNAPSHOT-EXTEND-001) / cycle 14 (WAVE-ALPHA-001) 모두 동일 패턴 = ~0.5 세션 SPEC + ~1~2 세션 구현 분할 + AskUserQuestion 5 라운드 옵션 (Recommended first) + 결단 N 건 영구 권위 + frontmatter status: frozen. **4 회 누적 = 미래 모든 인프라 SPEC 신설 시 default 진입점**. SPEC 작성 자체가 사용자 시간 부담 최소 + 결단 명문화 + 큰 commit 위험 분산.
- **사용자 고유 framework 영역 = canon 자가 정리 본질 (외부 권위 임의 인용 금지)**: 라운드 1 Q1-a 에서 사용자가 "프랙탈 + 로그 함수 해석은 본인의 고유 파동분석 영역" 으로 정정 (박종훈 강의 X). canon `knowledge/canon/<dept>/<custom-framework>/` 채움은 **사용자 자가 정리만**, 외부 자료 (강의·책) 의 임의 매핑 금지. 풀세트 자료는 후속 SPEC 분리 (`WAVE-ALPHA-CANON-001` 가칭). 명제 ID 체계 = **WA/WF/WL/WE 영역별 prefix** (principle_guardian C·D·R·OS 21 명제 패턴 정합). 미래 다른 사용자 고유 framework SPEC 작성 시 동일 패턴.
- **백테스팅 친화 설계 = 새 인프라 SPEC 의 핵심 자질로 격상**: 라운드 1 Q1-d 사용자 본질 발견 = "미래 성과 보기 전에 과거 백테스팅이 본 SPEC 질문 다 해소". 본 SPEC alpha() 함수가 **cutoff_date 인자 + 결정론 + 캐싱** = 과거 시점 시뮬레이션 가능 = 사용자 framework 진화 + 시스템 발전 핵심 동력. 백테스팅 본체는 SLOT S3 분리 (`WAVE-ALPHA-BACKTEST-001` 가칭). 미래 모든 분석가 결정론 함수 (scoring.py / 가중치 등) 설계 시 cutoff_date 친화 default.

**직전 세션 판단 (2026-05-21 cycle 12 — INFRA-SNAPSHOT-EXTEND-001 SPEC 5 라운드 면담)**
- **contract 정식 명문화 = ad-hoc 의 SPEC 그라운딩 패턴**: `market-snapshot-md-v1` 의 본 SPEC 정의 = cycle 1~2 의 ad-hoc 구현 (`render_snapshot_md` 8 섹션) 의 SPEC 그라운딩. 새 SPEC 작성 시 기존 ad-hoc 자산이 있다면 `v1.0 = 현재 풀세트 + 신규 섹션 누적` 형식 권유. `compose.build_pipeline_prompt` 시그니처 변경 X 가 자연 (chart v2 / fundamental v2 와 같은 [N] 블록 신규 추가 패턴 대비, snapshot 은 기존 [3] 블록 확장만).
- **briefing_parts 활용 본질 = read-only 보조 source 정합**: 본 SPEC 의 정규 DB (`supply_demand_history` 등) + briefing_parts 시계열 차분 = intraday 흐름 보조 (flow_analyzer 자금 유입 속도 0.2 축). retention 90일 한계로 영구 시계열은 별도 DB 가 본질. 단 정규 cron 외 보조 source 로 활용 가능 = 미래 인프라 SPEC 설계 시 "정규 DB + briefing_parts 차분" 이중 활용 패턴 정립.

**직전 세션 판단 (2026-05-19 자료 0 시드 5 분석가 v2 — 5 subagent 병렬 dispatch 첫 적용)**
- **`superpowers:dispatching-parallel-agents` 패턴 검증 ✨**: 5 subagent 동시 dispatch (1 message 안에 5 Agent tool calls), 각 subagent = `general-purpose` type + 본인 분석가 분량 prompt (~2-3 KB) 받아 2 파일 직접 write. 소요 ~5 분, 총 ~1,800 줄. 충돌 0 (각자 다른 디렉토리). **`feedback_persona_agent_speedup.md` 의 "12+ 세션 → ~4.5 세션 (3배 단축)" 패턴 검증 통과** — 본 세션 = 5명 1 사이클 = 이전 1명 6-12 시간 페이스 대비 ~60배 단축. 다음 사이클 (자료 있는 3명 + canon grep) 도 동일 패턴 적용 가능 (canon grep 충돌 X — 각자 다른 dept).
- **박종훈 framework scope 정밀화 = 변곡점 3 케이스 정의 영구화**: 사용자 2차 발화 ("거시적 경제 해석 통찰 = 트레이딩보다 한 차원 상위 frame, 시장 변곡점 시에만 들여다 보는 큰 길잡이") 가 메모리 본문 박힘. **변곡점 3 케이스 정의** (regime 전환 / Distribution Day 4건+ kill switch / 사이클 단계 변화 시그널) = market_state_analyzer cross-reference 발동 trigger 표준. 미래 트레이딩 관점 분석가 (stock_analyst·trader·flow_analyzer 등) 작성 시 동일 가드 일관 적용.
- **분화 boundary 본질 = production 첫 호출 호출 3 (boundary 침범 케이스) 의 골든 모먼트**: market_state_analyzer 가 "2026년 코스피 PER 평균" 같이 본인 frame 밖 질문 시 거부 + wealth_strategist 권위 영역 위임 명시 ✨. persona Cross-Agent Boundaries 표가 LLM 응답에 그대로 작동 = 한 호출 ~$0.0008 로 분화 boundary 본질 검증. 미래 분석가 작성 후 동일 시나리오 (frame 밖 질문) 검증 권유.

**직전 세션 판단 (2026-05-19 Track B + selector + 본질 재정의 + 박종훈 framework scope)**
- **외부 R&D 피드백 vs 사용자 본질 의도 충돌 발견 패턴**: 외부 chat AI Opus 의 "1주 미만 미지원" 피드백을 채택했다가 사용자 직접 발화 ("1주 미만도 소화 / buy_score 높은데 1주 이상 비효율") 와 충돌 발견 → revert + 본질 재정의 사이클로 격상. **외부 피드백은 검증 대상, 사용자 본질 의도가 절대 권위**. 다음 외부 R&D 사이클에서도 사용자 직설 정합 우선 검토.
- **본질 재정의 = 기간 기준 → 전략 본질 기준 = 사용자 발화에서 frame 추출**: 사용자 직설 통찰 ("기간보다 본질이 중요") 을 SPEC + persona + manifest 일관 박힘. Track A = "추세 추적 + 분할 운용" (타점 맞으면 큰 진입, 애매하면 역피라미드 분할) / Track B = "프랙탈 1 파 사이클" (저점~고점 1 파 회수, 실적·장기 무관) + 추세 인계 메커니즘 (Track B 1 파 완성 후 Track A 인계). display_name 도 본질 표기로 갱신 — 기간 어휘 잔재 (LLM 자기 식별 시 옛 frame 회귀 위험) 해소.
- **박종훈 framework scope = 트레이딩 관점 분석가 작성 시 핵심 가드**: 박종훈 framework (M·C·I·SP·W 명제 + Dalio 5단계) = 장기 자문 통찰 영역. 트레이딩 의사결정 직접 인용하면 "지금 부채 J커브 가속이라 매매 보류" 같은 보수 응답 → 트레이딩 마비. wealth_strategist (Track A read) 의 거시 frame 격자 영역만 인용 OK. Track A·B 등 트레이딩 페르소나 본문 framework 직접 인용 금지. canon `wealth_compounding/macro_roadmap` + `crisis_signals` = wealth_strategist 전용. 트레이딩 관점 분석가 (stock_analyst·stock_picker·news_curator·market_state_analyzer·trader·flow_analyzer) framework 추후 정의. `feedback_park_jonghoon_scope.md` 박힘.
- **persona ↔ SPEC ↔ test 이중·삼중 박음 = 균열 회피 패턴**: display_name 갱신 / 자본 단위 SLOT (S8) / 분석가 페르소나 작성 가드 (G1·G2) 모두 persona + manifest + SPEC + test 동시 갱신. 단일 박음 시 다음 세션 작성자 (R&D 또는 Claude Code) 가 옛 frame 회귀 위험. 본 패턴은 미래 분석가 페르소나 작성 시 동일 적용 (SPEC + 페르소나 + 테스트 키워드 동시 갱신).

**직전 세션 판단 (2026-05-18 Track A persona + 외부 리뷰 5 + Layer 3 production 사이클 가시화)**
- **production 사이클 가시화의 마지막 한 조각 = 양식·환각 차단 양립 검증의 골든 모먼트**: 분석가 미발행 상태가 LLM 환각 시험 최적. Anti-patterns ("분석가 점수 추정 금지") + cited 풀이 v3.1 양식 강제 + 결정론 시그니처 잠금 (scoring.py) 이 production 에서 모두 작동 = LLM 이 가짜 점수 박지 않고 정직하게 wait 발행. 첫 호출 1 회 검증 비용 ~$0.002 로 모든 양식 정합 동시 검증. 다른 시스템에서 흔한 "환각으로 그럴싸한 가격 박기" 위험 회피
- **`run_strategist.py` = `run_analyst.py` 1:1 차용 + 분석가 점수 주입 추가의 자연 확장**: 분석가 측 검증된 패턴 (manifest load + snapshot + compose + LLM 호출 + metadata) 그대로 + `gather_analyst_scores(target)` + `_insert_analyst_scores_block` (RAG 직전, not cached) 2 신규 함수만. compose 인터페이스 변경 X. 향후 base class 추출 가능하나 webapp/CLAUDE.md 의 "버려질 코드 과도한 추상화 금지" 정합으로 현재는 명료성 우선
- **외부 R&D (chat AI Opus) ↔ Claude Code 인수인계 = 마이크로 정정 사이클로 안정**: 본 세션 = 첫 풀 사이클 후 5 항목 추가 리뷰 받음. 모두 본질적 (책임 분리 / 양식 분기 / 시점 일관성 / 운용 슬롯 / 발행 책임) 이라 채택. 정합 작업 = plan 파일 통째 새로 쓰기 → ExitPlanMode → 명시적 Edit. 답변 시 "1:1 차용" 같은 모호한 용어는 사용자 의문 가능 → 짧게 정의 + 회사 비유 후 작업
- **webapp production UX 의 본질 확인 = 메모리 영구화**: 사용자 비전 = 하나의 LLM 채팅창, 백단 (Layer / agent_id / target / track) 0 노출. 자연어 → 자동 라우팅 (intent + 종목명 매핑 + Track Selector) → 종합 답변만. 현재 R&D 검증용 임시 노출 = 백단 인프라 안정화 후 별도 사이클. `feedback_webapp_production_ux.md` 박힘
- **페르소나·agent 작업 속도 전략 5 가지 = 메모리 영구화**: 본질 설계 80% (자동화 불가) + 양식·검증 20% (큰 단축 가능). 5 전략 = 자료 0 시드 5명 병렬 dispatch / 자료 있는 3명 병렬 / template 추출 / canon grep 자동 검증 / R&D 비동기 핑퐁 / 마이크로 정정 자체 검증. 12+ 세션 페이스 → ~4.5 세션 (3배 단축) 예상. `feedback_persona_agent_speedup.md` 박힘. **다음 세션 Top 1 (Track B + selector + 자료 0 시드 5명) 부터 `superpowers:dispatching-parallel-agents` 스킬 적용 — 1 세션 안에 6 명 (Track B + 5 분석가) 완성 목표**

**직전 세션 판단 (2026-05-17 scoring + 잠정 풀이 정정 — Top 2 첫 실체)**
- **잠정 풀이 정정 = canon 원문 1:1 grep 패턴 정립**: persona/manifest 예시 박은 cited 풀이는 LLM 추종력으로 응답에 그대로 나간다 (검증된 행동). 박힌 풀이가 canon frame 과 충돌하면 사용자가 답을 받아도 박종훈 강의 frame 매칭 안 됨. 패턴 = canon 원문 1:1 grep 후 정정. 이번 4 정정 (M2/C1/I2/C3) + 2 유지 (C5/I6). 향후 8 분석가 페르소나 작성 시 동일 패턴 적용
- **결정론 채점 시그니처 잠금 = 다음 세션 토대**: scoring.py 5 함수 호출처 0 (분석가 미 import). production 사이클 변화 0 — 사이클 가시화는 본 사이클 (2026-05-18) 에서 완성. 시그니처 = SPEC 권위 그대로. 시그니처 변경 시 페르소나 동기 의무
- **공식 vs 시그니처 분리 = placeholder 안전 안착**: F-Score + α 오버라이드만 정확 구현. s_score/buy_score 합산 + alpha 본체는 placeholder. 정식 공식 = 분석가 manifest 작성 시 또는 WAVE-ALPHA-001 SPEC 진입 시

**직전 세션 판단 (2026-05-17 v3.0 메타 재설계 — R&D 인수인계)**
- **9+3+1+회고N 골격 = 절대 흐름**: 분석가 9 → 전략가 N (Track A/B + plugin) → 계좌관리자 N (계좌 수 가변) → 회고분석가 N (제한 X). **회고분석가 N 제한 두면 창의성 죽인다** (사용자 명시). 신규 부서 효율성·정의·위계·검증 레이어는 회고분석가의 영역 자체. 9·3·1 만 본질 골격이고 나머지는 가변.
- **Track A + Track B 2 트랙만 (단타·중장기 빼고)**: 장기 투자 = 믿음 영역 + 지수 투자로 대체. 단타 = Track B 의 변형으로 흡수. **A/B 판단이 시급**. 향후 trackplugin 확장 = `agents/strategists/<new_track>/` 드롭만으로 (코드 변경 0). **본질 게임이 다름** — Track A = 🏢 부동산 임대업 수익금 게임 (자본 70-80%·승률 70%+·MDD 보호) / Track B = ☕ 카페 운영 손익비 게임 (자본 20-30%·R/R 1.5:1+·trailing). 같은 KPI 가중치 적용 X.
- **결정론 채점 = 코드 stage + canon 명제 ID 분리 (옵션 b)**: 채점 공식 (S/T/α/buy_score/F-Score) 은 `collectors/scoring.py` 순수 함수 — 재현성 100%·단위 테스트·LLM 외. canon md 는 frame **원리·렌즈** 만 (시대 불변). 박종훈 framework 명제 ID (M2·C3·W1·SP1 등) = LLM 권위 grounding. 분석가 응답에서 `주도주 점수 8 (S-Score=8, cited: [W1])` 같이 한국어 + 코드 라벨 + 명제 ID 삼중 병기.
- **canon vs persona vs reference 역할 분리**: canon = 모든 LLM 호출 system prompt **자동 주입** (`load_shared_canon()` rglob) = "회사 공통 매뉴얼" / persona = 분석가별 정체성·톤·금기 (해당 호출 때만) = "역할 정의서" / reference = Chroma RAG 인덱싱 원본 (LLM 직접 안 봄, 사용자 질문 관련 chunk retrieve 만) = "도서관 책장".
- **한국어 친화 용어 강제 양식**: LLM 응답에 `S-Score 8` 단독 출력 ❌. `타점 점수가 7` (코드 라벨 부재) ❌. **반드시 둘 다 병기**. 5 지표 한국어 = 주도주 점수 (S) · 타점 점수 (T) · 가속계수 (α) · 매수 점수 (buy_score) · 수급 점수 (F). 시스템 모르는 사람도 이해 가능해야.
- **F-Score (수급 점수) 신설 = `flow_analyzer` 발행물**: 단순 외인 매수/매도 합계 X — 종목·테마별 5 주체 가중치 차별 + 모멘텀 + 자금 속도 + 일치도. 4 축 가중 합 (테마-주체 매칭 0.4 + 60일 모멘텀 0.3 + 시총 정규화 자금 속도 0.2 + 5 주체 부호 일치 0.1). boundary: 발행 = `flow_analyzer` / read = `trader` · 전략가. 사용자 통찰: "가격이 수급의 부모, 종목·테마별 수급 성격 다 다름".
- **α 가속계수 오버라이드 = 발산 구간 참여 강제**: 로그 함수 발산 구간 (α 1.3~1.7) = 가장 큰 수익 자리 (사용자 W 계좌 실측). 일봉 이격도로 차단하면 발산 참여 불가. **α = "참여 여부" / 일봉 이격 = "비중 크기"** 분리. α 1.5+ 강발산 시 T-Score 이격 항목 max 7 강제. `collectors.scoring.t_score(divergence, macd, volume, rr, alpha)` 함수 내부 적용.
- **R&D (챗AI Opus) / 엔지니어링 (Claude Code) 도구 분리 패턴**: 페르소나 본질 설계·룰 토론·사용자 핑퐁은 chat Claude.ai Project 의 Opus 가 강함 (긴 대화·깊은 추론). Claude Code 는 .md 받아 코드 변환·SPEC generates·테스트·통합. **Git = 영구 메모리** (R&D ↔ 엔지니어링 인수인계 매체). 이번 세션이 첫 인수인계 사이클 = 챗AI 결과물 2 메모 → SPEC 3 + docs 패치.
- **16 페르소나는 참고용**: 9+3 안에 11 명 자연 매핑, 신규 5 명만 ⭐ (#3 Regime / #9 Trigger / #11 Distribution / #12 Trailing / #16 Track Selector — 모두 결정론·룰 중심). 별도 페르소나 폴더 X. v3.0 설계서 = 페르소나 정밀도·역할 흡수, wevelStock 5-Layer 골격은 유지.

**직전 세션 판단 (2026-05-17 v3.1 cited + 근거 명제 풀이 양식 정정)**
- **v3.1 cited 양식 = 코드 마커 + 자연어 풀이 이중 grounding**: `cited: [<ID>]` 한 줄 + `근거 명제 풀이:` bullet (각 ID 한 줄 자연어 정의). persona/manifest/SPEC 동일 양식 강제. 양식 자동 출력은 LLM 추종력으로 작동 확인. 단 풀이 정합성은 별개 — 박은 잠정 풀이 vs LLM RAG retrieve frame 충돌 가능 (M2 잠정 "통화량 팽창 침식" vs RAG "고령화·반도체 의존 30년" 완전 다른 frame 발견).
- **YAML literal block 코드펜스 트랩**: `response_rules: |` 블록 안에 markdown 코드펜스 ``` 가 column 0 에 있으면 YAML literal block 종료 → 뒤 라인이 YAML 키로 파싱. **예시 블록은 indent 2 spaces 강제 plain text** (코드펜스 자체 회피).

**직전 세션 판단 (2026-05-12 ANALYST-PERSONAS-001 + v1→v4 + Architectural pivot)**
- **분석가 1명 단일 호출 = 답 빈약, "숲부터 보고 나무 깎기"**: 사용자 응답은 Layer 3 통합 전략가가 분석가 9 명 결과 + snapshot + RAG 종합. production 호출 = Layer 3 / 배치 자동 = Layer 2 분석가 cron → team_outputs DB 누적. 9 분석가 페르소나 7-10 세션 작성 동안 production 0 의 lean 안티패턴 회피.
- **페르소나 layer 만으로 LLM 분기 결정론 불가능**: persona 안 격자 양식 텍스트 존재 시 LLM (gemini-2.5-flash) 끌림 무한. v1→v4 4 회 패치 후 CLI OK 인데 webapp 격자 박힘. **본질 해결 = 격자 양식을 persona 분리 + server compose keyword trigger 동적 주입** (compose 분기 인프라, 9 분석가 페르소나 작성 중 재평가).
- **`load_analyst_spec` 캐시 없음**: 매 호출 디스크 fresh read. persona/manifest 변경 = server 재시작 불필요, 다음 호출부터 즉시 반영. `llm_call_cache` 는 input_hash 기반 — 같은 query = cache hit (페르소나 검증 시 다른 질문 필요).

**기초·불변 원칙**
- **파이프라인 구조 = "시간대별 독립 폴더"**, 공통 수집은 `collectors/` 로만 공유, 파이프라인 간 코드 import 금지
- **수동 관심(`watch_positions`) vs AI 시뮬(`sim_positions` + `sim_trades`) 스키마 분리**
- **텔레그램 3분할 렌더링**, 연속성 문제 없음
- **`docs/a_wanted/user_want_spec.md` 매 세션 초반 필수 읽기**. "뇌 이식 + 자동 수집 + 연속 판단" 이 본질
- **`force` = "cache/snapshot 우회 + 새 실행"**: default False, `market_briefing_now` 09:00 fallback 도 force=true 면 우회
- **데이터 무결성 우선**: KIS API 의 응답 정렬·필드 의미는 항상 의심하고 직접 검증
- **시장 전체 vs 종목 단위 KIS 투자자 API 구분**: `inquire-investor-time-by-market` (FHPTJ04030000, 시장 전체 5주체) 만 시장 합계 신뢰
- **KIS OpenAPI 미제공 데이터는 KRX backend** (`data.krx.co.kr/comm/bldAttendant/getJsonData.cmd` POST + Referer/UA, `bld` 파라미터)
- **수급 표시 5주체 세로 나래비**: 개인→외인→기관→금융투자→연기금. 약자 X. 선물도 `[KOSPI200 선물]` 통일
- **`market_briefing_now` 는 LLM 없이 raw 발송** (장중 빈번 호출, 비용·지연 회피)
- **briefing_parts retention = 시계열 누적 + 90일 cleanup cron** (별도 작은 SPEC 백로그)
- **정확한 용어**: VIX≠공포탐욕(CNN FGI), 투신(투자신탁)≠금융투자(증권사 자기매매), 영문 약어는 괄호 한국어 병기
- **서버 `--reload` 비신뢰**: 수정 시마다 수동 재시작

---

## 🔑 재진입 치트시트

```bash
# 환경
.venv/Scripts/python.exe -m pytest pipelines/morning_pre/tests/ -v

# 파이프라인 조회
.venv/Scripts/python.exe -c "from pipelines._registry import list_all_pipelines; print([p.id for p in list_all_pipelines()])"

# 서버 부팅 확인
.venv/Scripts/python.exe -c "from server.main import app; print(len(app.routes))"

# 수동 실행 (서버 떠 있을 때)
curl -X POST http://localhost:8000/api/pipelines/morning_pre/run
```

---

## 🧠 세션 재진입 절차

### 케이스 A — 이전 세션 **그대로** 이어가기 (컨텍스트 보존)

```bash
cd C:\Users\HOME\claude\wevelStock
claude -r        # 세션 목록에서 선택
# 또는
claude -c        # 가장 최근 세션 자동 재개
```

- 내용 파악이 안 되면 에디터에서 [docs/SESSIONS.md](SESSIONS.md) 표를 먼저 확인
- 대화 이력이 그대로 복원되므로 `/resume` 추가로 칠 필요 없음

### 케이스 B — 새 세션에서 **맥락만** 이어받기

```bash
cd C:\Users\HOME\claude\wevelStock
claude
# 프롬프트 뜨면:
/resume
```

1. Claude가 `a_wanted/user_want_spec.md` + 이 파일 + 최신 c_worked 를 읽고 **플랜모드 진입**
2. "지난 세션에 X 했고, 다음 후보는 A/B/C 입니다. 오늘 뭐 하실래요?" 인터뷰
3. 답변 반영 → 플랜 확정 → ExitPlanMode → 구현
4. 마무리할 때 `/wrap-up` — c_worked + SESSIONS.md + 이 파일 자동 갱신

### 판단 기준
- 같은 주제 계속 파고들기 → **케이스 A**
- 다른 주제로 전환 / 오래 쉬었음 → **케이스 B**
