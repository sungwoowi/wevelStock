# Evolution Log — 하네스 개선 이력 (진화팀)

> "출력을 고치지 말고 하네스를 고쳐라" — evolve-review 실행 기록. 어떤 하네스(SPEC/계약/persona/배선)를 왜 고쳤는지 남긴다.

## 2026-07-05 — Track A "시장을 느끼는 능력" 총체 점검

**트리거**: 사용자 진단 5건 (고변동 장세 미반영·차트 모멘텀 편중·후성 고점 buy·뉴스부 무력·유니버스 착시).

**점검 방법**: Explore 3 에이전트 병렬 — ① 전략가 LLM 입력 전수(퍼소나·compose·auto_signal) ② DB 추천 히스토리(team_outputs 656행·후성 22행·notifications 11건 자동 buy) ③ 뉴스부→매매 체인(수집→분류→digest→소비처).

**판정**: 사용자 주장 4 CONFIRMED + 1 부분 지지. 근본 원인 5축 = 입력 결핍(슬롯 미배선 3곳 + 자동 경로 우회 3인) / 격상 결핍(중심 이벤트 식별 부재) / 게이트 결핍(defensive≠발행 차단, 원칙수호자 우회) / 주도주 결핍(S-Score=차트 근사) / 학습 결핍(채점 0).

**고친 하네스 (문서 — 사용자 결정: 이번 세션 코드 0)**:
- `docs/specs/MARKET-CONTEXT-BRAIN-001-market-context-brain.md` 신설 (roadmap, BRAIN-QUALITY 자식) — 진단 전문 + Tier 0~4 로드맵 + 사용자 결정 3건 + 재사용 영향도.
- `docs/specs/AUTO-SIGNAL-INTEGRITY-001-auto-signal-integrity.md` 신설 (implementation draft) — 정합 결함 4건 수리 명세 + 후성 06-16 재현 수용 기준.
- `docs/specs/BRAIN-QUALITY-001-investment-quality.md` children 에 MARKET-CONTEXT-BRAIN-001 등록.
- `docs/RESUME.md` 현재 위치·세션 판단·Top 3 갱신 (Tier 0 최우선).

**다음 하네스 후보 (구현 세션에서)**: N5 canon 개정(해석된 격상 이벤트 예외 단서) / track_a·track_b manifest `reads_analysts` 에 news_curator 추가 / 전략가 recommendation 계약에 포트폴리오 자세 필드(v1.1, Tier 3).

**교훈**: 코드 슬롯이 존재해도 배선 안 되면 없는 것과 같다(compose news_digest_md·market_view_md). "의도적 우회" 같은 비용 최적화가 안전핀(원칙수호자)까지 걷어내지 않았는지 SPEC 단계에서 명시 점검 필요.
