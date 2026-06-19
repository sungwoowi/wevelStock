---
date: 2026-06-20
topic: 백테스트 1차 — Track A 본진 검증 + α 타임프레임 철학 확정 + 결정론 후보층 강화 결정
status: completed
plan_file:
---

# 2026-06-20 · 백테스트 edge 검증 + 알파 철학 + 후보층 강화 결정

## 배경
"작은 작업 말고 시스템의 궁극 발전 목표"를 사장 관점으로 점검 → 결론 = **기계는 다 지었으나
edge를 한 번도 증명 못 함(track record 0)** → 백테스트로 "이게 되는지" 먼저 확인하기로.
chart_ohlcv가 7.5년·167종 깊어 가격기반 신호는 cutoff-clean 백테스트 가능(펀더/뉴스 얕아
풀 buy_score는 불가). 핵심 판단: **결정론 신호는 백테스트로 즉시 검증되나 LLM은 hindsight로
불가 → 측정 가능한 결정론 후보층을 먼저 강화한다.**

## 한 일
### R&D 백테스트 프로브 (scripts/, SPEC 전 탐색 — 기존 _*.py 관례)
- `scripts/_backtest_signal_probe.py` — 모멘텀/추세 1개월 IC·분위 edge (1차).
- `scripts/_backtest_horizon_regime_probe.py` — 지평선(1/3/6/12M)×장세(하락 2022~2024) 스윕.
- `scripts/_backtest_alpha_probe.py` — α(결정론 코어, LLM off) 1M edge.
- `scripts/_backtest_alpha_horizon_regime.py` — α 6M/12M 장세분리 + 패널 저장.
- `scripts/_backtest_newhigh_ma_probe.py` — 신고가·이평정배열·thrust·상대강도 × 보유기간×장세.
- `scripts/_backtest_box_accel_probe.py` — Track B 박스저점(평균회귀) + Track A 가속도(2차함수).
- `scripts/_backtest_trackA_strategy.py` — Track A 실제 포트폴리오(상위20% 보유·교체·비용) vs 시장.
### 문서·철학
- `docs/BACKTEST-FINDINGS-AND-ALPHA-ROADMAP.md` (신규) — 용어사전 전부 풀이 + 발견 종합 + 알고리즘 로직 + **167종 편향 진단** + 알파 시스템 로드맵 7단계 + **결정론 후보층 먼저 강화 아키텍처 결정**.
- `docs/a_wanted/user_want_spec.md` — 최상단에 **α 타임프레임↔트랙 철학** 박음(일봉/360분=Track B 단기스윙·수주~1달 / 주봉/월봉=Track A 추세·3~6달, 신고가 *가속화* 진입, 하락장 박스규율, 이평선 인터뷰 대기, 궁극목표=우상향 복리계좌).
- 메모리 3건: `project_wave_alpha_framework`(타임프레임 매핑+인터뷰 대기)·`project_backtest_edge_findings`(신규)·MEMORY.md 인덱스.

## 검증 결과 (백테스트 — 거래비용 반영, 생존편향 미반영)
- ✅ **Track A 본진 검증**: 이평정배열+상대강도 상위 20% **분기 교체** = 시장(전체 동일가중) 대비 **연복리 +8.7%p, MDD −17.5%(<시장 −22.7%), 하락장 +61.7%(vs +34.6%)**. 6~12개월 지평선·하락장에서 edge 가장 강함.
- ⚠️ **편향 진단**: 167종 = 87% 2018~2019부터 존재(생존편향)·거래대금 상위 출처(선택편향). 절대 수익률은 뻥튀기, **상대 우위(+8.7%p)는 상한선** — 상폐 포함 유니버스로 재검증 필요.
- 🔴 **결정론 α 코어(LLM off)는 모멘텀에 못 미침** — α 가치는 LLM 선택·정밀 파동에 있는데 백테스트 불가.
- 🟡 **Track B 추격형 = 하락장 미작동**(정상), 박스저점만 희미한 IC+ 씨앗. 360분봉 데이터 없어 한계.

## 의도적으로 안 한 것
- LLM 페르소나/프롬프트 손튜닝 — 백테스트로 측정 불가(hindsight)라 ROI 낮음. forward 루프 후로.
- 풀 buy_score(펀더·뉴스) 백테스트 — 과거 데이터 얕아 불가.
- 결정론 가드·조건 구현 — **내일 이평선/차트모양 인터뷰 후** 착수(사용자 요청).

## 다음에 이어서 할 작업 (우선순위)
1. **결정론 후보층 강화 — 이평선/차트모양 인터뷰 먼저** ⭐(내일): 사용자가 월/주/일봉별 중요 이평선 조건 + 차트 모양(이미지 포함) 던짐 → Track A/B 타임프레임 정합 지표 + **confluence 조건(정배열 AND 상대강도 AND 신고가 초기 AND 이평지지)** + 가드(장세·가속초기·유동성·손절) 를 결정론 후보 생성에 구현. 조건마다 백테스트 A/B로 타이트하게. 게이트 아닌 *메뉴*(LLM이 결정).
2. **정직한 백테스트 인프라 (BACKTEST SPEC)**: 상폐 포함 point-in-time 유니버스(생존편향 제거) + 실비용·슬리피지 + 실 KOSPI 벤치마크. +8.7%p가 진짜인지 판별. → 정식 SPEC 격상.
3. **무인 forward "진실의 루프"**: 24/7 가동(OPS) + 매일 벤치마크 대비 정직 채점 + 회고/진화팀이 두뇌 교정. LLM 가치는 이걸로만 측정 가능 → 진짜 track record.

## 커밋 상태
- wrap-up 시점 커밋 예정 (probe 7 + 리포트 + user_want_spec + c_worked/RESUME/SESSIONS). 생성 CSV(data/_*.csv)는 산출물이라 제외.
