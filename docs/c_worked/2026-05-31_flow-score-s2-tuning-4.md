---
date: 2026-05-31
topic: SLOT S2 — F-Score 세 축 production 임계 튜닝 (13종 라이브 분포 정합 + theme_authority 정리)
status: completed
plan_file: C:\Users\HOME\.claude\plans\pure-wobbling-hammock.md
---

# 2026-05-31 · SLOT S2 — F-Score 세 축 production 임계 튜닝

## 배경
직전 세션이 종목 레벨 수급(KIS 3주체) collector를 라이브 점등시켜 `build_flow_inputs(ticker=...)`가 실 종목 수급을 흘려보내게 됐다. 그런데 F-Score 세 축의 breakpoint(`config/score_inputs.yaml::flow`)는 placeholder(theme_match는 momentum 곡선 재사용)였다. 13종 라이브 분포를 수집해 실측 정합. **핵심 판단 3건**: (1) 종목 변별력은 데이터 교체만으로 이미 회복(과거 "전종목 4.5" 시장 프록시 문제 해소) — breakpoint는 *구조*가 아니라 *캘리브레이션* 문제. (2) **inflow_speed가 진짜 결함** — 구 floor -50→1점 clamp로 6/13 종목이 1.0에 깔려 저구간 변별 0. (3) recenter는 single-day overfitting → 절대 앵커(raw 0=균형=5점) 보존, 관측 폭에만 맞춰 꼬리 재스케일.

## 한 일
- `scripts/flow_distribution.py` (신규) — 다종목 라이브 분포 진단 도구. 13종 바구니(테마 10종 커버) 순차 fetch(KIS rate-limit 안전, 0.15s 간격) + theme ratio 재계산(FlowInputs 미노출 → `score_theme_match` 식 복제) + 현 config score + 축별 분위수 통계(min/p10/p25/median/p75/p90/max) + JSON 산출. `smoke_executive.py` 패턴 mirror. SLOT S2 재튜닝 재사용.
- `config/score_inputs.yaml` — flow 3축 breakpoints 13종 분포 정합:
  - `inflow_speed`: `[[-50,1],[0,5],[50,8],[150,10]]` → `[[-150,1],[-80,2.5],[-30,4],[0,5],[40,7],[90,9],[170,10]]` (저구간 clamp 압축 해소, 관측 -265~+170)
  - `theme_match`: `[[-1,1],[-0.3,4],[0,5],[0.3,7],[1,9]]` → `[[-1,1],[-0.5,2.5],[-0.2,4],[0,5],[0.2,6],[0.5,8],[1,10]]` (앵커 보존, 꼬리 재스케일)
  - `momentum`: 동형 대칭 곡선으로 + 양극단 1/10 saturate(bimodal 지표)
  - `theme_authority.defense_nuclear`: `[pension, institution]` → `[institution]` (종목 레벨 KIS는 pension/financial_inv=0 死문자 제거 — 점수 무변)
  - `manual_theme`: 아모레퍼시픽(090430→cosmetics)·두산로보틱스(454910→robotics) override (LLM Stage2 None→중립 5.0 변별 손실 정정)

## 검증 결과
- ✅ pytest **714 passed, 회귀 0** (TESTING=1, config-only 변경·테스트는 DI breakpoints라 무영향).
- ✅ 라이브 13종 end-to-end GREEN (KIS rate-limit 경고는 retry 자가회복, [[project_kis_rate_limit_backlog]] 그대로).
- ✅ **변별 회복 실증** (before→after): inflow_speed 저구간 — 삼성전자 1.5→3.5 / SK하이닉스 1.0→2.0 / 현대차 1.0→3.5 / 한화에어로 1.0→2.5 / 삼성바이오 1.0→2.0 (6종 1.0 군집 → 1.0~3.5 변별). theme_match 3.0~9.0→2.5~10.0(LG엔솔 강매집 만점). 아모레/두산로보 None→cosmetics 4.0/robotics 3.0 복구.
- ✅ **hts_avls 시총 단위 정상 확인** — 삼성 1,853조는 sim price 317,000 기준 내부 정합. 직전 세션 단위 버그 의심 **반증**. 중형주(아모레 6.7조·알테오젠 19.8조)도 현실적.

## 의도적으로 안 한 것
- **momentum/theme recenter** — single-day median(-0.24 등)으로 중심 이동 안 함. 외인 전종목 순매도는 이 시점 스냅샷 특성이라 overfitting([[feedback_backtest_essence]]). 절대 앵커만 유지.
- **buy_score·S-Score 배선** — Top 3, 별 세션(scoring.py 정식 가중치 SLOT S7 + SCREEN-RS).

## 기술 부채/미완
- **breakpoint 중간점 정밀도** — 13종 1일 스냅샷 기준 1차 캘리브레이션. 앵커·floor는 robust하나 중간점은 운용 누적 후 재튜닝 필요(config 주석에 명시). flow_distribution.py가 재튜닝 도구.
- **theme_authority가 종목 레벨에선 외인·기관·개인만** — pension/financial_inv 주도 테마는 KRX 5주체 복구 전까지 institution 우회. KRX 복구(Top 2) 시 정밀화.
- `_flow_distribution.json` 진단 산출물 — .gitignore 미등록(커밋 제외).

## 맥락 재진입 힌트
- inflow_speed "결함"의 정체 = 코드 버그 아님. `map_to_axis`의 clamp(`x <= pts[0][0]` → 끝점 고정)로 floor -50 이하가 전부 1.0. 새 KIS 금액축 breakpoint 추가 시 관측 폭부터 분포 확인(flow_distribution.py)하고 floor 정할 것.
- 분류(LLM)⊥채점(결정론) 분리라 KRX 5주체 복구 시 collector fetch만 교체하면 골격 재사용(net_sums 입력만 바뀜).

## 다음에 이어서 할 작업 (우선순위)
1. **KRX 5주체 + market_breadth 복구 (방법 A)** — KRX getJsonData STAT가 로그인 벽+안티봇("LOGOUT")으로 차단. data.krx.co.kr 개별종목 투자자별 거래실적 페이지 **devtools로 실 getJsonData 요청(bld/params/세션) 캡처**(사용자 협조 필요) → `connectors/krx/client.py` 휴면 helper 활성 + market_breadth 동반 복구. 종목 수급 KIS 3주체→KRX 5주체 승급(금융투자·연기금 회복).
2. **buy_score·S-Score 후속 배선** — `collectors/scoring.py` s_score·buy_score 정식 가중치(SLOT S7) + SCREEN-RS-EXTENSION-001(rs 축, prism #289 draft) + run_analyst hook. 5점수 체계(S/T/α/buy/F) 완성.
3. **breakpoint 운용 재튜닝** — 다일·다종목 누적 후 flow_distribution.py로 분포 재수집 → 중간점 정밀화(회고분석가 합의).

## 커밋 상태
- main 직접(솔로). 코드 1 커밋(config + flow_distribution.py) + wrap-up docs 1 커밋, 사용자 요청으로 push 예정.
