# RESUME — 작업 재진입 상태판

> 이 파일은 **항상 최신 상태**로 유지됩니다. 세션을 새로 열 때 `/resume` 만 치면 이 파일을 읽고 플랜모드로 브리핑합니다.
>
> 갱신 주기: 의미 있는 작업 완료 후 `/wrap-up` 실행 시 자동 갱신.
> 수동 편집도 자유 — 구조만 지키면 됩니다.

---

## 📍 지금 어디 있나

**현재 위치**: **🧭 ADVISOR-CORE-001 신설 + M1 시장 판세 트랙 라이브 (2026-08-12)**. 사용자가 프로젝트 본질을 재정의 — *"폭등장·폭락장 겪고 간결해졌다. 필요한 건 ①시장분석 ②배분 ③종목 스크리닝·추천. 정량은 결정론, 추론만 LLM"* → **Track A/B 접고 Track C(1콜 2관점) + 시장 판세 트랙(18:00·07:05) 신설** SPEC. M1 을 a(배선)·b(공매도·대주잔고·프로그램)·c(코스닥 섹터 RS)·e(판세 LLM+알림) 구현, **텔레그램 실발송 2회·cron 등록 확인**(1585 passed). M1-d 호가는 *"단타 칠 거 아니면 의미 없다"* 는 사용자 판단으로 **접음**. **사용자 제보 3건이 전부 "모르는 걸 아는 척"** — 신선도(5일 전 지수를 오늘 값으로)·야간선물(누적 등락을 야간 이동으로)·근사 폴백(빈 응답을 0으로) → 셋 다 **"근거 없으면 None"** 으로 통일. 60일 섹터의 구조적 후행은 **다중 시간축**(F2)으로 보완. **다음 = F3 주도 종목 축 → M2 Track C.**

**(직전) 현재 위치**: **📣 일일 요약 알림 종목명 전개 + Track A 90초 타임아웃 진단 (2026-08-11)**. 사용자 지적("매일 오는 알림이 카운트만 와서 뭐가 매수인지 알 수가 없다")에서 출발 → `AUTO-SIGNAL-DIGEST-001` 신설·구현·**텔레그램 실발송 검증**(1460 passed). 버킷 5개(매수/매도·지켜볼·변화없음·**미산출 신설**)로 전개 + 밴드 스킵을 "직전 판단 유지"로 정정 + 사유 내부용어 한국어화. **그 압축이 결함을 가리고 있었다** — 08-10 평가 10건인데 요약 합은 5, 사라진 5건 전부 Track A. 진단 결과 **`claude_code.timeout_sec=90` 에 Track A 가 87.7초로 붙어 있음**(Track B 39.3초), 회귀 시점 = `0a23704`(07-17) provider→claude_code. 두 달간 안 보인 이유 = 관측 구멍 3겹(실패 버킷 부재 + 원장 `success=True` 하드코딩 + 로그 파일 미기록). **다음 = F1 timeout 90→180(즉효) → F3·F4 관측 봉합 → 서버 재시작.**

**(직전) 현재 위치**: **🔭 LLM 판단 구조 전면 감사 + 채팅 임원 기본화(P0) + 5축 깔때기 엔진 청사진 (2026-07-18)**. "채팅=함수자판기" 불만 + 외부 기술분석 자료 6종 + "통폐합 판단하고 싶다"로 시작 → 13-에이전트 감사로 원인 5 확정(①최종 답변=압축기 formatter "결론≤3줄"·flash-lite·800tok·📊 prefix ②**executive persona(통찰 서술 완성형 명세)가 존재하는데 production 미배선** ③상류 코드라벨 강제↔하류 3겹 제거 상쇄 배선 ④wait 단일음 96~100%+채팅 미저장 ⑤canon 27/36 빈 폴더·3부서 0바이트. 반증=브리핑 내러티브 유창→모델 무죄) → **P0 구현: `chat.executive_mode_default=true`**(config hot reload·요청 명시 우선·웹앱 수정 0, **1430 passed**, stale provider 테스트 수리 덤) → 제로베이스 브레인스토밍: **5축(공간·시간·뉴스검색·실행·복기)=초심(원안과 1:1)** 확인 → 프리즘 실측($310/월·결정론 5단계 압축→3종목→13에이전트 심층·자동복기는 홍보문구)으로 **"위원회→소프트 깔때기" 확정**(우리 압축기=대등 이상+백테스트 edge, 빠진 것=탑다운 배선+심층 출구+복기 루프) → **`ENGINE-FUNNEL-REWIRE-001`**(roadmap, NORTH-STAR 자식: 결단 D1~D7+사다리 P0✅~P5) + 사람용 `idea_memo/2026-07-18-five-axis-funnel-engine-refocus.md`. **다음 = 서버 재시작(P0 체감+관측 체크 3건) → P1 지식 반입 spec-interview → P2 채점 루프.** [[project_engine_funnel_blueprint]]

**(직전) 현재 위치**: **🧭 제미나이 비용 진단·감축 3커밋 + "길을 잃음" → 북극성 재초점 (2026-07-12)**. 과금일 ₩16,000 확인 요청 → 비용 원장으로 실측. **연쇄 발견**: ① 요금표 버그(`gemini-2.5-flash` 가 낡은 `0.075/0.30`=구 1.5/2.0-lite 요금 → 실비 3.3배 축소 보고) → GA `0.30/2.50` 정정 + 원장 955행 백필(thinking 토큰 역산 복원, 8일 실비 $1.59→**$9.08≈₩12,500**, 백업 `llm_cost_ledger_bak_20260712`) ② **비용 95%가 전략가 track_a/b**·thinking 토큰이 43%·news_classify 482콜은 ₩212(무시) ③ "왜 많나" = **모든 종목 × 장기A+단기B 무조건 둘 다**(auto_signal.py:731, 2배 증폭). **감축 2레버 적용**(권고당 품질 불변): 12:35 케이던스 제거(4→3) + `band_score_width` 1.0→2.0(재호출 둔감·flapping 완화) + watchlist 일자당 표시 10 상한. **그다음 사용자 "먼가 길을 잃었다"**(거시 반쪽·승급 반쪽·두 트랙 토큰 낭비) → 참조 사이트(stock-analyzer-peach-chi)를 계기로 **방향 재수렴**: *기능은 이미 충분(그 사이트보다 큰 엔진), 폭을 멈추고 [오늘 Top-5 → 가상매매 → 일지] 하나의 깔끔한 루프를 닫고 백테스트로 픽을 증명한다.* **다음 = idea_memo(`2026-07-13-north-star-refocus-*`) 읽고 착수 3택(출력/매매/검증) 결정 → 서버 재시작해 비용 감소 관측.** (전략가 콜은 대폭 늘지 않되 thinking cap·트랙 라우팅은 보류.) [[project_north_star_refocus]]

**(직전) 현재 위치**: **🔧 라이브 첫날 하드닝 — 시황 misfire 근본 수리 + 장전 브리핑 실전 관점·가독성·배선 완성 (2026-07-07 심야, 커밋 9)**. M1 배포 첫날 사용자가 텔레그램 실물로 실시간 제보 → 심야 핑퐁. **① 시황 브리핑 3연속 침묵 근본 원인 = 파이프라인 잡만 misfire 유예 1초**(6-15 절전 보강이 loader.py 누락 — 콘솔 로그로 1h 유예 잡 전부 발화 vs 1초 잡 전멸 대비 확정) → grace 1h. **② briefing 콜 thinking_budget=0**(thinking 잠식→506토큰 잘림→시나리오 공백 실증). **③ 장전 브리핑 실전화**: scenario short_term(1~2주)/long_term(1개월+) 구조 필드(스탠스+조건부 대응 강제+재탕/빌미 판별) / **신규 후보 결정론 메뉴**(`render_candidate_menu_md` — 전일 큐레이션×컨셉×funnel, 유명 대형주 회귀 차단) / **보유 의견 배선 구멍**(`account_positions` 정본 안 읽음 → get_holdings 합류, 실보유 3종 HOLD+평가손익 첫 발행) / sector_watch 렌더 복원(🧭 약세·회피). **④ 가독성**: 한국어 헤드라인+링크 임베드(headline_kr)+파급 ❗/‼️+범례 / 종목간 줄바꿈+볼드+문장경계 클립 / 텔레그램 4096 분할+선택적 escape(안전 태그 보존)+DB plain strip / HOLD 🔵. 전체 **1416 passed**·라이브 6회 사용자 실물 검증. **다음 = 아침 전 계층 첫 완주 관측(06:40→07:00→09:30 misfire 검증점→09:35).**

**(직전) 현재 위치**: **📰 NEWS-EVENT-INTERPRETATION-001 spec-interview + M1 구현 — 격상 레인·LLM 해석·장전 cron·전략가 배선 (2026-07-06)**. Tier 1 본진 — /spec-interview 로 결단 5건(D1 격상=mag3+mag2×다중소스3 / D2 저장=digest 컬럼 확장 신규테이블0 / D3 Flash+캐싱+원장 / D4 M1=advisory·게이트는 M2 / D5 장전 06:40 ingest+lookback 폴백) 확정 후 같은 세션 TDD 구현. **사용자 통찰 2건 세션 중 합류**: ① 해석 4축째 = 시장 실반응·파동 정합("뉴스가 원인인가 빌미인가" — 미장 실측+차트 위치 주입) ② 07:00 장전 브리핑과 결 맞춤(06:40 ingest→07:00 브리핑→09:35 회차 시간표). 구현: `detect_elevated_events`(결정론)+`interpret_elevated_events`(4축+nature 3분류+매매함의+재평가조건, 캐시 멱등·일 3건 상한)+ingest 5.5단계+`news_ingest::premarket` cron+**전달 배선 5곳**(digest md 최상단 "⚡ 오늘의 중심 이벤트"·run_strategist 동기/stream 파라미터·자동 권고 as_of·production chat·07:00 브리핑 analyze)+track A/B manifest news_curator 합류(**dead-end 진단 ④ 해소**). **검증 3겹**: 전체 **1395 passed**·validate 0 / **메타발 리플레이**(06-23~27 미라벨링 204건이 백필 lookback 7d 밖 잔존 발견→16d 백필 후 발생→확산(다중소스 레인 발화)→실현 전 구간 재현, `scripts/_replay_news_elevation.py`) / **해석 probe**(07-03 실 Gemini $0.0002)=transient_fear+4축(재탕/괴리/악재순환/빌미)+"관망/눌림목 대기" = **사용자 07-03 실판단과 동일 결**. 발견 = 클러스터 키 분산(한 이벤트가 Samsung/KOSPI/semiconductor 로 쪼개짐, SLOT). **서버 재시작 필요(Tier 0 + M1 합산).** **다음 = 라이브 관측(월 06:40~) → M2(lifecycle+게이트+N5).**

**(직전) 현재 위치**: **🛡 AUTO-SIGNAL-INTEGRITY-001 Tier 0 구현 + 3겹 검증 + 07-03 패닉 역발상 사각 발견 (2026-07-05 2세션)**. 오전 진단 SPEC 을 같은 날 TDD 구현 — 인터뷰 1회로 **차등 게이트 확정**(blanket 기각: defensive 면 buy 후보에 강세섹터+주도주+건강위치+파동 요구, 미충족 wait 강등+원판단 기록, LLM 은 `llm_deviation_reason` 사실근거로만 뒤집기+코드 안전핀). T0 4건 완료: `_apply_defensive_gate`+`derive_wave_alive`(A=주봉/B=일봉) / 배선 3개(sector_rs=supply_chain 실측 재사용·wave=α·entry_posture=DB read) / 7계명 결정론 체크(checkers 4·5·6 재사용, 손절부재=강등) / 뉴스 백필(`backfill_unlabeled_news`+ingest 4.5단계). **검증 3겹**: 전체 1367 passed·validate 0 / 리플레이=과거 buy 8건 전부 차단(`scripts/_replay_defensive_gate.py`) / 라이브 probe(실 Gemini 2콜)=배선 실측·dd6 위험게이트 우선 발동·wait persist. **07-03 SK하이닉스 재구성 = 시스템 모든 층 wait vs 사용자 장초 폭락 매수 적중(+18.6%)** → 패닉 역발상의 설계상 사각 확정, 사용자 통찰을 SPEC 에 박음(Tier 1 해석 질문지 3축 novelty·펀더정합·노이즈반복 / Tier 2 주도주 사이클 게이지 신고가=100 / PANIC-REVERSAL 레인=백테스트 후 활성). 발견 부채 = ext 폭락직후에도 9.5(k_below)·게이트 가시성 UI 부재(GATE-VISIBILITY 후보)·무관 date-rot 테스트 7건 수리. **서버 재시작 필요.** **다음 = NEWS-EVENT-INTERPRETATION-001 spec-interview.**

**(직전) 현재 위치**: **🧭 Track A "시장을 느끼는 능력" 총체 진단 + MARKET-CONTEXT-BRAIN-001 roadmap (2026-07-05, 문서만·코드 0)**. 사용자가 6월말~7월초 고변동 장세(메타발 AI capex 논란→반도체 급락 등)에서 추천을 지켜보고 5가지 통찰 제기 → evolve-review 로 코드 배선·프롬프트·DB 히스토리(후성 22행 전수) 검증. **판정: 4개 CONFIRMED + 1개 부분 지지.** ① 뉴스 digest·시장관이 전략가 프롬프트에 **물리적 미주입**(compose 슬롯 있는데 run_strategist 미전달) ② α=순수 차트 가속, 자동 경로는 α·거시·**원칙수호자까지 우회** ③ **후성(093370) buy 3회=최다 추천**, 첫 buy가 3일 +38% 블로우오프 익일→즉시 −12%, 같은 시각 track_b는 "이격도 +37~60% 과열"로 wait(좌우 손 불일치) ④ 메타발 기사 수집됐으나 다수 미라벨링·건수 클러스터에 희석, news_curator는 전략가 어디도 안 읽는 dead-end, regime은 급락 후(07-03)에야 sideways(후행 실증) ⑤ 자동 buy 11건 중 10건 거래대금 유니버스 출신(단 채점 비어 인과 검증 불가=track record 0 재확인). **추가 발견: entry_posture=defensive(06-22~)인데 06-29 buy 5건 발령**(deployment_cap은 사이징만, 신호 게이트 아님) + sector_rs/wave_alive=None으로 bear_override dead path + "현금 확보" 출력 경로 부재 + 뉴스→매매 단절 절반은 N5 canon 의도 설계. **산출**: `MARKET-CONTEXT-BRAIN-001`(roadmap, BRAIN-QUALITY 자식 — Tier0 정합→1 뉴스 이벤트 격상+**해석**→2 주도주 판별→3 포트폴리오 자세 액션+수동주입 인프라(보류)→4 채점 루프) + `AUTO-SIGNAL-INTEGRITY-001`(Tier0 draft — defensive 게이트·7계명 결정론 체크·sector_rs/wave 배선·뉴스 백필, 후성 06-16 재현 테스트 명세) + docs/evolution-log.md 신설. 사용자 결정 3건: 이번=문서만 / 뉴스는 격상 이벤트만 게이트하되 **해석 퀄리티(단기공포 vs 변곡 vs 시계열 매매포인트)가 본질** / 수동 주입 보류(인프라 방향만). **다음 = Tier 0 핫픽스 구현(spec-interview→코드).**

**(직전) 현재 위치**: **💸 LLM 비용 원장 + 결정론 anchor 기본화 — Gemini 지출 폭발 대응 (2026-07-04)**. Gemini 월 지출이 매일 폭발해 사용자가 AI Studio 상한 걸고 서버 며칠 중단 → "다른 벤더 말고 현 구조에서 지출 줄이되 결과물 유지" 요구. **진단: 진짜 청구서가 로컬에 기록 없어(`llm_call_cache`=멱등, 대형 호출 미기록) 추측만 가능 = 가시성 부재가 근본.** 9분석가는 자동경로 아님(채팅 on-demand만), collector LLM(anchor·theme 등)이 종목당 무거움. **anchor α 실증(실 Gemini): LLM 성공 픽 = 결정론과 소수점까지 동일·절반은 실패(C=최근점→current 충돌) → LLM anchor = 기여0 계산기.** 처방 = **① 비용 원장 세워 가시성 → ② 결정론 anchor 기본화.** 구현: `llm_cost_ledger`(모든 호출 1행, 벤더·모델·질의영역·일자축, `call_llm` 중앙 기록 + 9영역 라벨) / `alpha.anchor_llm_enabled=false`(결정론 픽 기본, LLM 토글 보존) / 운영자 화면 `/ops/llm-cost`(막대+일자표) + `GET /api/ops/llm-cost`. **라이브 검증**: anchor 005930·000660 6/6 산출(LLM콜0, LLM 실패하던 4/6도 성공)·production chat 1회=10콜 원장 캡처(분석가6+전략가2+formatter+market_view)·실서버 27콜. "빈 답변"=검증 curl이 top-level `.text`(없음) 읽은 파싱오류, 실제 `formatted.text` 정상. 전체 400+ passed·validate 0·tsc 0. **LLM-COST-LEDGER-001 verified**(OPS-CLOUD 자식), drift 없음. **다음 = 원장 켜고 하루 실측 → fan-out/입력토큰 절감(활용) → 종합 판단 부재 진단.**

**(직전) 현재 위치**: **🔬 백테스트 1차 — Track A 본진 edge 검증 + α 타임프레임 철학 확정 + 결정론 후보층 강화 결정 (2026-06-20)**. "작은 작업 말고 궁극 목표"를 사장 관점으로 점검 → **기계는 다 지었으나 edge 미증명(track record 0)** 진단 → 백테스트로 직접 확인. chart_ohlcv 7.5년·167종으로 가격기반 신호 cutoff-clean 백테스트(펀더·뉴스 얕아 풀 buy_score 불가). **결과: 🟢 Track A 본진 검증** — 이평정배열+상대강도 상위20% **분기 교체**가 시장(전체 동일가중) 대비 **연복리 +8.7%p·MDD −17.5%(<−22.7%)·하락장 +61.7%(vs +34.6%)**, 6~12개월·하락장에서 edge 최강. ⚠️ **편향**: 167종 87% 2018~2019부터 존재(생존편향)·거래대금 상위 출처(선택편향) → 절대수익 뻥튀기, **상대 우위는 상한선**(상폐 포함 유니버스 재검증 필요). 🔴 결정론 α 코어(LLM off)는 모멘텀에 못 미침(α 가치=LLM선택·정밀파동인데 백테스트 불가). 🟡 Track B 추격형 하락장 미작동(정상)·박스저점만 IC+ 씨앗·360분봉 없음. **사용자 철학 확정**(본질문서 박음): α=주도주 선택, 일봉/360분=Track B 단기스윙(수주~1달, 신고가 가속·박스저점), 주봉/월봉=Track A 추세(3~6달, 신고가 *가속화* 진입), 12M=미장 별개, 하락장 박스규율. **아키텍처 결정: 결정론 후보층을 먼저·더 타이트하게 강화**(측정 가능·천장 결정·증명된 엣지) — LLM 다듬기는 forward 루프 후. drift 없음(BRAIN-QUALITY 재료 축적, SPEC status 무변). **다음 = 이평선/차트모양 인터뷰 후 결정론 후보층 강화.**

**(직전) 현재 위치**: **🏷 노출·알림 단의 종목코드 전부 종목명으로 (2026-06-19)**. 사용자가 텔레그램 알림·가상매매 계좌 화면에서 "005935 3차 — 20.8만 도달 시 자동 체결"처럼 **종목코드가 그대로 노출**되는 걸 발견. systematic-debugging 으로 근본 원인 추적 = 종목명 리졸버(`get_stock_name`+`KR_TICKER_TO_NAME`)가 일부 경로에만 배선되고 누락 경로는 코드 폴백(005935도 사실 매핑에 존재=삼성전자우, 리졸버만 안 거침). **해결 = 중앙 진입점 `resolve_stock_name(ticker, hint)` 1개 신설**(hint→멤버십 DB→정적 매핑→최후 코드) 후 모든 노출·알림 단이 통과하게 배선. **고친 곳**: 텔레그램 매매 알림(`이름(코드)`→이름만)·브리핑 보유/관심(`이름 (코드)`→이름만)·`/계좌` 보유 목록 / 가상매매 보유중·매수대기·이익실현·매매일지·회차헤더(`display_name` 주입)·채팅 디버그 칩. **둔 곳**: 분석가 sub-task 프롬프트·시황 md·전략가 지시문(LLM 입력 컨텍스트라 코드 병기가 정확도에 유리). 전체 **1344 passed**(신규 테스트 7건, 회귀 0)·webapp tsc 0. SPEC status 변동 없음(PAPER-DESK-UX·watchlist 후속 품질 픽스)·drift 없음. **다음 = 매핑 밖 폴백 강화 / 데스크 actionable 정리 / 종목 상세+채팅 prefill.**

**(직전) 현재 위치**: **🗂 관심종목 종목관리 페이지(트랙×단계 funnel) + 큐레이션 + 트레이드플랜 2단계 — 대형 세션 (2026-06-16 2세션)**. 트레이드플랜 2단계(매수대기)로 시작 → 데스크 "지켜보는 권고" 점검 중 사용자 **"무의미한 universe 덤프"** 진단 → **체계적 종목 관리** 재설계로 확장. **핵심 IA(사용자 정정)**: 거래대금/거래량 상위 = *후보 바스킷(소스)*, 주축은 **장기/단기 트랙 × 단계(관심→매수대기→진입)**, 종목별 매매 시계열 시나리오. **신규 테이블 1개**(`universe_membership` — list_type·name·rank·trade_amount·volume·concept, PK 4-col, 마이그 v17~v19)로 두 리스트·종목명·일자·컨셉·거래량 흡수(가드 #11). **구현**: 트레이드플랜 2단계(`enrich_conditional_entry`·`derive_funnel_stage`) · 데스크 리뉴얼+dedup키 버그+`_from_mapping` round-trip 누수 수정+종목명 정리 · `collectors/volume_bull.py`(거래량 양봉, 하이브리드 신선도) · `collectors/universe_curation.py`(잡주 floor 리스트별 차등·**상한가 포함**·정배열·**컨셉 분류** 주도주/눌림/바닥) · `core/watchlist_view.py`(트랙×단계+**관심 공용 컨셉별**+바스킷 날짜그룹·정렬(거래대금 desc, KIS rank 시장로컬 버그 수정)·교집합 is_dual) · `/api/watchlist/funnel` · `/watchlist` 페이지. **전체 1341 passed**(신규 ~50, 회귀 0)·validate 0·build tsc 0. **라이브**: 매수대기 단계 환각 0, 거래량양봉 26→큐레이션 16, 거래대금 50→32, 컨셉(주도주20/눌림3/바닥2)·교집합·정렬 확인. drift 없음. **dev 재시작 필요**(.next CSS 404로 "깨짐"—코드 무결). **다음 = 종목 상세+채팅 prefill / 데스크 섹션 actionable만 / 데이터 충실화.**

**(직전) 현재 위치**: **🧩 트레이드 플랜 다단 가격대 메뉴(B-MS1) 구현·라이브 + 다층 진입 단계 funnel 설계 (2026-06-16)**. /resume → TRADE-PLAN 1단계 착수 직전 사용자가 철학 재점검("결정론에 하나하나 박는 게 의미 있나? 끝없는데") → **B→C 애자일 합본 합의**: 결정론은 *객관 가격대 계산기*(후보 메뉴)일 뿐, 선택·조합은 LLM, 끝없는 "선택 룰"은 안 만듦, 소수 절대 가드레일(오닐 −7%·종가)만 결정론 강제. **B-MS1 구현(TDD)**: `core/signal/trade_plan_menu.py`(순수 — 다단 손절/지지/저항/목표 후보 + 분할매수·매도 사다리 + clamp/menu_bound 가드레일 + dedup·stale 제외) → `run_strategist(trade_plan_menu_md=)` 주입 → 파서 `data.trade_plan` 가산 → funnel 배선·`data.trade_plan_menu` 영속·`_apply_trade_plan_guardrails`. persona 다단 지시 + config `trade_plan`. **전체 1275 passed**(+22). **라이브(실 Gemini 000660)**: LLM이 메뉴 소비 → stop=메뉴 −7% floor 정확·종가기준, 환각 0(가드레일 있는 C 작동), verdict=hold(약수급). 라이브가 메뉴 버그 2개(stale 808K·동일가 중복) 잡아 즉시 수정. buy 미관측=오늘 분산 방어장(코드 아닌 시황). **+ 다층 진입 단계 설계**: 사용자 통찰("관심→매수대기→buy 라벨된 단계로 추출되면 더 빨리 인정받는다")을 SPEC에 박음 — 상태 모델 확장(관심·매수대기 앞단), legible funnel 섹션(단계=파생 라벨·새 판단 아님), 로드맵 재배열(2단계=매수대기 *단계* 격상·승격사유·라벨). drift 없음. **다음 = 2단계 매수대기 단계(conditional_entry+승격사유+라벨).**

**(직전) 현재 위치**: **🧩 트레이드 플랜 생애주기 설계 SPEC + 결정론/판단 분업 원칙 확정 (2026-06-15 6세션)**. "관망 조건부 진입가" 논의가 사용자 통찰로 **트레이드 플랜 생애주기**(목표·손절·분할매수·분할매도·대기진입가를 시계열로 진화 + 목표 동적 수정 + 알림)로 확장. 사용자 반복 질문 "결정론으로 다 맞출 수 있나?" → **핵심 원칙 확정: 결정론 = 후보 메뉴·신호 *계산기* / 판단(LLM·룰) = 선택·임계·수정. 결정론은 절대 결정자 아님 → '다 맞춰야 하나'=영원히 아니오.**(손절도 단일 공식 아님). `docs/specs/TRADE-PLAN-LIFECYCLE-001` 신규(설계 전용·코드 0): 비전+원칙+**prism 리포트 차용**(다단 지지/저항·목표=마일스톤 regime 조건부·매도 AND·종가기준 −7%·트리거 승률·보유 지속 조건)+**5단계 로드맵**(①손절+분할매수 레벨 ②대기 진입가 ③목표+분할매도 ④시계열 진화 ⑤알림). BRAIN-QUALITY 자식 0/2, BRAIN-ALPHA-FLEXIBILITY 조건부진입 SLOT 이관. drift 없음. **다음 = 1단계(손절+분할매수 결정론 레벨)부터.**

**(직전) 현재 위치**: **🧠 두뇌 알파 유연성 — 라이브 검증 + 복합 위험 게이트 신설 (2026-06-15 5세션)**. M1+M2+M3a 를 실 Gemini 로 검증하다 "여전히 전부 wait"의 **진범 연쇄**를 발견·정정. ① 진범 = regime 이 아니라 **분산일 kill-switch(시장전체 blanket, dd≥4)** → **복합 위험 게이트**로 교체(`alpha_posture`): 당일 급락(change_pct≤−2.5)·breadth 붕괴(≤0.2)·VIX 패닉·지속 분산(dd≥6) 중 하나라도 → blanket 방어 / **완만한 분산(dd5)은 통과**. 폭락 회피(사용자 우려)+알파 유연 동시. ② **Fix① stale 텍스트**(`_market_state_md` "≥4" 제거→게이트 위임). ③ **Fix② 구조 누수**(배치 우회 분석가를 "의도적 우회" entry 로 주입 — persona text 로는 LLM 이 "미발행→wait" 안전핀 회귀, **코드로 해결**). **라이브 실증(실 Gemini)**: 000660 **buy**(탈피)·005930 **사실근거 wait**("외인 60일 순매도 −27.88조·약수급" 로그)·위험게이트 14 buy(상승일). = 가드레일 있는 C 작동. 전체 **1253 passed**. **미완 = 관망 조건부 진입가(숫자, 다음 세션 논의)·M3b(sector_rs·wave→약세장 bear_override)·보유종목 관리.**

**(직전) 현재 위치**: **🧠 두뇌 알파 유연성 — M2 persona doctrine 전환 + M3a funnel 결정론 배선 (2026-06-15 4세션)**. M1(결정론 후보)을 라이브 경로에 연결. **M2**: `track_a`·`track_b` persona.md 의 regime 범주 게이트 폐기 → **AlphaPosture 후보 소비자**(후보 기본 채택, 뒤집으려면 `data: llm_deviation_reason:` 사실 근거 필수, blanket 보수 강등 금지 anti-pattern). **Track B kill-switch(분산일≥4) 보존**(deviation 불가). **M3a**: `auto_signal.py` Scorecard 에 rs/ext 필드 + screen 행에서 주입(LLM 0) → `posture_inputs_from_scorecard`→`derive_alpha_posture`→`render_alpha_posture_md` 를 `run_strategist(alpha_posture_md=)` 로 주입 + `rec.data["alpha_posture"]` 영속(설명가능성). 신규 테이블·파서 변경 0. **TDD 92 신규 GREEN·전체 1247 passed·회귀 0.** 결정론상 strong_bull+점수통과+과열아님→buy 후보 보장(단위 증명). **남은 것 = 라이브 검증(실 Gemini)·M3b(sector_rs·wave LLM 입력→약세장 bear_override)·M4/M5.** 현재 sector_rs·wave=None 이라 bullish/neutral 차등만 동작.

**(직전) 현재 위치**: **🧠 두뇌 알파 유연성 — BRAIN-ALPHA-FLEXIBILITY-001 SPEC + M1 결정론 차등 변조 (2026-06-15 3세션)**. /resume → BRAIN-QUALITY 첫 자식 착수. 오늘 라이브가 **regime=strong_bull 인데 권고 32건 전부 wait** = regime 이 verdict 를 3단 억압(persona 범주 게이트 + kill-switch + confidence 가중)인 걸 코드로 확인 → 핵심 = **regime 을 binary blanket 게이트에서 baseline 으로 강등**, 섹터RS·주도주·파동·과열도가 종목별 override. **면담 5라운드 결단 4건**: ①섹터·종목 차등 변조(blanket gate 폐기) ②**가드레일 있는 C**(결정론이 verdict 후보+조건부 진입가 발행→LLM 은 "반박할 사실 있나?" 검증자, 후보 강등엔 사실근거 로그 필수, 웹 더블체크 buy 후보만) ③MVP=4 스레드 전부 ④국장+미장 동시. **M1 구현(TDD)**: `core/signal/alpha_posture.py` 순수 함수(I/O·LLM 0) — 🟢약세장+강세섹터+주도주+파동+눌림목=buy(bear_override) / 🔴강세장 과열=buy→wait(chase_demote) / 🛡분산일≥4=kill-switch 보존 / 모든 분기 selection_reason. config 섹션 + `load_posture_config()` 로더. **17/17 테스트 GREEN, 전체 1239 passed**(실패 3=test_market_snapshot 환경성, grep 으로 M1 무관 입증). M2(persona)~M6(라이브)는 다음 세션. AUTO-SIGNAL 자율 cron 첫 발화=내일 18:05.

**(직전) 현재 위치**: **🛡 텔레그램 절전 사고 대응 + cron 미스파이어 내성 (2026-06-15 2세션)**. /resume 중 사용자가 "오늘 오전 텔레그램 알림 실패"(`[Errno 11001] getaddrinfo failed`) 제보 → 디버깅. **근본 = 코드 무결, 노트북 덮개 절전(sleep)으로 망/DNS 단절**(증거: `run_auto_signal_job ... missed by 0:33:18` = 스케줄러 33분 멈춤 + 어제 푸시 0건). 라이브 `getMe` OK·서버 폴링 자동 복구 확인. 알림 손실 0(`_send_telegram` 예외→파일/DB 폴백, 텔레그램 push만 누락). **놓친 오전 잡 재실행**(사용자 선택 B): 시황 강제 갱신(3파트 tg=True) → `run_auto_signal_job("intraday1")`(persist 32·전부 wait·**regime=strong_bull**). **재발 방지 패치**: 스케줄러가 `job_defaults` 없이 생성돼 기본 grace=1초라 절전 1초도 영구 스킵 → 장중 3 cadence + postclose(18:05 daily_refresh)에 `misfire_grace_time=3600`·`coalesce`·`max_instances=1`(절전서 깨면 1h 내 놓친 회차 자동 따라잡음). 전체 **1225 passed**(+1). 사용자 서버 재시작 = 라이브 반영. 인터럽트성 사고대응이라 **Top 3(두뇌 알파 유연성) 변동 없음**. 라이브 strong_bull인데 32건 전부 wait = BRAIN-QUALITY 필요성 재확인.

**(직전) 현재 위치**: **🤖 자동 권고 생성(AUTO-SIGNAL-GENERATION-001) M1~M6 구현 + 라이브 검증 (2026-06-15)**. /resume 중 두뇌 구조 점검(코드·DB 실측: **분석가=라벨 아닌 5필드·결정론 점수는 LLM 우회 보존 / 전략가 3줄=Flash 압축**) → "두뇌 못 믿는 이유 = 얕아서 아니라 **track record 0**(권고 전부 채팅 산물·wait·Track A 0건)" 확인 → **자동 권고 생성 착수**. funnel = watchlist(거래대금 상위50 ∪ 보유 ∪ 관심, 국장) → **결정론 컷**(rank_candidates) → **밴드 게이트**(regime·점수버킷·kill-switch 지문 동일 시 스킵) → **전략가 직접 호출·분석가 LLM 우회**(점수=코드·분석가=해설자 발견 적용) → persist(source/cadence/track) → **🟢 매수·🔵 일일요약 알림** → [18:05 데스크 체결]. cron 4 cadence(장중 09:35/12:35/14:35 + 18:05) + **병렬화(동시성 3, asyncio·저사양 보수)** + 재시도(503/no_yaml). **M5 라이브 1회(실 Gemini): watchlist 50→컷 20→persist 34건(src=auto·Track A·B)·🔵 텔레그램 발송 성공, 전부 wait(방어장·regime=None)**. 전체 **1224 passed**(회귀 0). AUTO-SIGNAL implementing(자율 cron 첫 발화=내일 18:05, 장중은 서버 상주 필요). **다음 = 두뇌 알파 유연성(regime 극보수 탈피·관망의 체계적 매매계획·선정기준에 파동/주도주/섹터·설명가능성) 심층 인터뷰 = BRAIN-QUALITY 본격 착수.**

**(직전) 현재 위치**: **📐 Phase 2 실전화 4기둥 roadmap 박음 + 자동 권고 생성 공백 진단 (2026-06-14 2세션)**. 5탭 완성 후 사용자 "전체 얼마나 완성?" 점검 → 두 축 평가(지어진 정도 ~85% / 검증된 정도 ~65%) → 사용자가 **남은 일을 4기둥(두뇌·몸통·진화·설비)으로 분류**. 사용자 질문 **"몸통은 도는데 왜 매수/관망 리포트·알림 0?"** 을 코드·DB 팩트 진단 → **자동 권고 생성 잡 부재**(권고는 `production_chat` 채팅 트리거만, 스케줄 잡은 브리핑만, 데스크는 소비만 / 실측 권고 4건 전부 wait·체결 0·매매알림 0) = **두뇌↔몸통 빠진 연결**. 4기둥을 `PROJECT-NORTH-STAR-001` 자식 roadmap SPEC 5개로 박음(`BRAIN-QUALITY`·`BODY-AUTOMATION`·`EVOLUTION`·`OPS-CLOUD` + `AUTO-SIGNAL-GENERATION-001` draft 팩트 SPEC) → 단계 지도 **NORTH-STAR 1/2→1/6(정직)**. RESUME Top 3 = Phase 2 프레임. **사용자 우선순위 고민 중, 다음 세션 결정.** 권장 순서 = 몸통 자율화(자동 권고)→진화→두뇌 퀄리티 동반→설비.

**(직전) 현재 위치**: **💬 채팅·뉴스·알림 본체 = 5탭 전부 활성 (2026-06-14)**. PAPER-DESK-UX 화면 마감 — placeholder 3탭을 정본 `T8fhu`(채팅)·`L45yjk`(뉴스)·`OWnxc`(알림) 픽셀 구현. **백엔드 = 뉴스 라우터 1개만 신규**(`server/api/news.py` `/digest`·`/items`, 기존 build_news_digest·get_news_items·get_news_digest 조립, 신규 테이블 0·가드 #11). 채팅 SSE(`/api/chat/production/stream`)·알림 API는 완비라 백엔드 변경 0. **채팅 = R&D production-chat 비의존 자체 구현(production-clean)**: `useChatStream` 훅(SSE 소비 — formatted 종합답변+근거만, 디버그 크롬 0) + 말풍선 + 시장 한줄 카드 + 입력바. **뉴스** = 톤 배지+단기/장기 2단(top_themes by time_axis)+수집 뉴스 리스트. **알림** = 필터 칩+날짜 그룹(type→🔴위험/🟢매매/🔵시장)+진입 시 mark-read(종 배지 클리어). AppShell 5탭 active. tsc 0·**1153 passed**(+3)·라우트 200. RIGHT-BRAIN 무변(PAPER-DESK-UX implementing — 5탭 화면 완성, 미산출 지표·다크 대조·verified 게이트 잔여). 다음 = 데스크 미산출 지표 / 다크 정밀 대조 / verified 게이트.

**(직전) 현재 위치**: **🎨 라이트 팔레트 정본 정밀 + 가독성 보정 (2026-06-13 5세션)**. PAPER-DESK-UX 화면 3/3 후 `webapp/src/app/globals.css` 라이트 토큰(다크 파생값)을 정본 `.pen` 실측으로 교정(border `#dddddd`·상승 `#dc2626`·heading `#222222`·info `#2563eb`·amber-bg `#fff7ed` 등 ~9개) → **사용자 피드백 "회색 너무 연해 안 띔"** → 정본보다 대비 한 단계 ↑(border `#cfd1d5`·타일 `#eef0f2`·보조텍스트 `#595d63`·faint `#82868e`) + **앱 배경 옅은 회색 `#f7f8fa` + 흰 카드**(밀집 대시보드식 — 에어비앤비 그림자식 기각). 다크 토큰 변경 0(실측 유지). 단일 파일·시맨틱 토큰이라 전 화면 전파(컴포넌트 하드코딩 hex 0). tsc 0·라우트 200·**사용자 육안 승인**. RIGHT-BRAIN 무변(PAPER-DESK-UX implementing). 다음 = 채팅·뉴스·알림 본체 / 데스크 미산출 지표 / 다크 정밀 대조.

**(직전) 현재 위치**: **🖥 PAPER-DESK-UX-001 — `/desk` + `/desk/[id]` 본체 = RB-MS5 화면 3/3 완성 (2026-06-13 4세션)**. 데스크 본체(가상매매)+계좌 상세 2화면을 정본 `g1EUS`·`P88ZI` 픽셀 읽어 구현 → 시황(1/3)에 이어 **3화면 전부**. **백엔드 3 추가(전부 기존 테이블 read, 신규 테이블 0 — 가드 #11)**: ① `kpi.py` account_id 필터(계좌별 KPI) ② `desk_view.py`(신규) 회차내역(filled+pending 사다리)·매수대기·청산 → `/holdings` enrich ③ `desk.py`(신규) `/desk/feed`(활성권고+매매일지). **프론트**: `format.ts`(MarketBoard 포맷 추출+손익 `pnlClass`/`wonKR`)·profit/loss 토큰·recharts 자산곡선(2시리즈+목표/시드선+기간토글)·`DeskBoard`·`AccountDetail`(보유 테이블+회차 펼치기·매수대기·이익실현). **색상=의미색**(수익 초록/손실 빨강, 시황 한국식과 분리). 정본 못 채우는 5칸=사용자 결정 "기존테이블 노출까지"(지수오버레이·샤프·손익비ratio는 graceful 제외). tsc 0·**1150 passed**(+5)·라우트 200(/desk·/desk/[id]). RIGHT-BRAIN PAPER-DESK-UX 화면 MVP 3/3(implementing 유지 — 채팅/뉴스/알림 placeholder). 다음 = 5탭 placeholder 채우기 + 라이트 팔레트 정밀.

**(직전) 현재 위치**: **🖥 PAPER-DESK-UX-001 구현 — 시황 화면 + 시점 히스토리 LNB (RB-MS5, 2026-06-13 3세션)**. 오른쪽 뇌 화면 차단점 착수 — SPEC draft→implementing + Next.js 스캐폴딩(next-themes·recharts·**FractalSignal 팔레트**(.pen 다크 실측)·5탭 AppShell·테마 토글) + **시황(홈) 화면**(🇰🇷국내지수·참고지표 12+2타일(야간선물 2종)·등락 breadth+비례막대·거래대금 상위·강세 섹터·수급, **한국식 색상**) + **시점 히스토리 LNB**(브리핑 런=시점, run_id별 point-in-time 재조립). 신규 백엔드 = `server/api/market.py`(`/snapshot`+`/history`, DB-first·LLM 0·라이브 어댑터 재사용). R&D→`/dev/*`(production-chat은 dev서버 락으로 보류). tsc 0·전체 **1145 passed**·라우트 200. RIGHT-BRAIN 1/6 verified(PAPER-DESK-UX implementing↑). 다음 = `/desk` 본체.

**(직전) 현재 위치**: **🔗 두 overnight fetch 경로 통합 — 중복 fetch 부채 상환 (2026-06-13 2세션)**. 야간자산 yfinance fetch 로직이 두 벌(`us_markets._fetch_sync`+`OVERNIGHT_SYMBOLS` / `connectors.yfinance._fetch_sync`+`TRACKED_SYMBOLS`)이던 걸 **connectors/yfinance 단일 소스로 수렴** — `us_markets.fetch_overnight()`은 `get_indices` 위임 래퍼로 축소(`sox`↔`philly_semi` rename, `usdkrw` TRACKED_SYMBOLS 추가). **소비처 수정 0**, 전체 1145 passed, 라이브 위임 검증(12키 error 0). 재사용 가드 #11 정합. RIGHT-BRAIN 1/6 무변. 다음 = PAPER-DESK-UX 구현.

**(직전) 현재 위치**: **🌙 INFRA-MARKET-ASSETS-002 구현(draft→implementing) + KOSPI200 야간선물 실선물 + 간밤시황 정정/추가 (2026-06-13)**. 데이터 백본 풀세트 — ① 야간자산 4종(WTI·브렌트·NQ·ES) us_macro 컬럼(v16) + 한글 라벨 ② 알림 영속(notification_type·is_read + mark-read + unread_count) ③ **KOSPI200 야간선물 = 백로그 반전**: "KIS 한계로 불가" 결론을 야간 실측으로 뒤집음 — **KIS 연결선물 `101000`(최근월물 자동) 실계좌 작동, +5.16% 라이브**. 텔레그램 간밤시황 EWY 대용(+11.48% 이상치)→KIS 실선물 교체 + NQ/ES·브렌트 노출. 1145 passed, 텔레그램 실발송 2회.

**(직전) 현재 위치**: **🛡 INFRA-MARKET-ASSETS-002 SPEC 신설(린 정정) + 재사용 가드 신설 (2026-06-12)**. PAPER-DESK-UX 예약 후속 SPEC(자산군 수집 + 알림 영속)을 `/spec-interview` 로 작성 → 사용자 "무분별 신규 확장 아니냐" 제동 → **신규 테이블 과잉을 확장 전용으로 정정**(`us_macro_snapshot` 이 gold·wti 이미 보유, `generates: []`). 미스 재발 방지로 **개발-타임 재사용 가드 3종** 신설: `docs/DATA-MAP.md`(30테이블 도메인 지도) + CLAUDE.md 절대원칙 #11 + spec-interview 재사용 영향도 게이트. 코드 0, 항상 켜짐.

**(직전) 현재 위치**: **📐 PAPER-DESK-UX-001 SPEC 신설 (RB-MS5, draft) + 디자인 .pen 리네임 (2026-06-12)**. 오른쪽 뇌 화면 차단점 해소 SPEC 골격 작성 — **무게중심=프론트 빌드**(데스크 API 대부분 기존, 신규 백엔드는 시황 집계 read 1개). MVP=시황+가상매매+계좌상세 3화면 / Recharts / next-themes / R&D→`/dev/*` / 시황="거의 풀". **정정 2건**: `uiux-sample-draft.pen`=IA 드래프트(시각 정본 아님), 정본=`design-darkmode-spec.pen`/`design-lightmode-spec.pen` 쌍.

**(직전) 현재 위치**: **🎨 CTA 액센트 결정 = 테마별 듀얼 액센트 확정 (2026-06-12)**. "통일 안 함" — 라이트 핑크(Rausch #FF385C) / 다크 에메랄드 강조(핑크 로고 + CTA #10B981). 디자인 `.pen` 변경 0.

**(직전) 현재 위치**: **🔧 KIS 토큰 만료 버그 수정 + chart_refresh 배치 복구 (2026-06-12)**. 인프라 버그 수정 — 디자인·오른쪽 뇌 SPEC 진행도 무변.

**(직전) 현재 위치**: **✋ FractalSignal 네이밍 확정 + 다크/라이트 테마 쌍 완성 (2026-06-11 4세션)**. `design-darkmode-spec.pen`(다크) / `design-lightmode-spec.pen`(라이트) = **테마 쌍** (후보 비교 아님 — 토글 수동+시스템). 양쪽 공통: FractalSignal 로고+프랙탈 파동 마크 · "가상매매" 용어 · 기간 5단 토글 · 지수 라인 차트(코스피·나스닥) · 등락 종목 수 UI(KIS 기수집 확인) · 테마 토글 14곳 · 모바일 2×. 다음 = PAPER-DESK-UX-001 SPEC → Next.js 구현(shadcn/ui 4.x+Tailwind v4 `5526fdb`). ✅ CTA 액센트 = 테마별 듀얼 액센트 확정(통일 안 함, 변경 0 — 라이트 핑크 로고+Rausch CTA / 다크 핑크 로고+에메랄드 CTA, 2026-06-12). `webapp/uiux-sample-draft.pen` 에 PC 7화면 + 모바일 6화면 라이브 핑퐁으로 확정: **탭 5축 = 시황(홈)·데스크·채팅·뉴스·알림 / 가이드 = 헤더 ❔ / 브리핑 탭 폐지 → 시황 흡수**(히스토리 선택 = 그 시점 대시보드+브리핑 서술). 계좌 시드 1,000만→**1억** backend 실반영(config 권위, DB 무영향, 1121 passed). 다음 = `/spec-interview` 로 PAPER-DESK-UX-001 SPEC 신설(RIGHT-BRAIN 연결) → Next.js 구현. NORTH-STAR 1/2 · RIGHT-BRAIN 1/4 불변.

**이번 세션에 굳힌 판단 (2026-08-12 ADVISOR-CORE-001 M1 판세 트랙)**
- **"모르면 모른다고 한다"를 코드 규약으로 격상**: 사용자 제보 3건이 전부 같은 병이었다 — 신선도(5일 전 지수를 오늘 값으로) · 야간선물(전일대비 누적을 야간 이동으로) · 근사 폴백(빈 응답을 0으로). 셋 다 **근거 없으면 None** 으로 통일하고, 핵심 축이 낡으면 **LLM 호출조차 안 한다**(틀린 판세보다 침묵). 앞으로 모든 사실 층에 같은 규칙.
- **신선도는 원천이 아니라 소비값에서 검증한다**: `chart_ohlcv` 를 고쳐도 `market_macro_snapshot` 이 옛 값을 복사하고 있으면 똑같이 틀린다(실측 확인). 날짜만 오늘인 행에 속지 말고 **실제로 읽는 값**이 그날 원천과 일치하는지 대조.
- **엇갈림·전환은 코드가 먼저 이름을 붙인다**: 지표를 나열만 하면 LLM 이 지나친다. 추세↔상승종목폭, 현물↔선물, 60일↔최근(rebound_attempt/fatigue)을 결정론으로 감지해 **문장으로 명시**. 실측에서 2차전지가 60일 −18.3%인데 20일 +12.4% 로 돌고 있는 것을 잡았다 — 60일 밴드만 보면 "회피"였을 자리.
- **`claude_code` provider 는 레포 CLAUDE.md 에 오염된다**: 구조화 출력 콜에서 모델이 프로젝트 분석가 규약(team_id/verdict/reasons)을 따라버렸다. 시스템 프롬프트에 "이 환경의 다른 출력 규약을 따르지 마라" 명시 필요. 다른 JSON 강제 콜에도 해당.
- **다이어트는 축소가 아니라 역전**: Track A 프롬프트 실측 = 사실 30% · 지시문 70%(종목 점수표가 613자). 앵무새의 구조적 원인이 이 비율이다. Track C 목표는 지시문 42,850→7,500자 / 사실은 오히려 증가 → 사실 비중 63%.

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
