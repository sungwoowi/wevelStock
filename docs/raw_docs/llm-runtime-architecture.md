# 🧠 LLM 런타임 아키텍처 — 누가 판단하는가?

---

## 1. 문제 인식: 코드와 판단은 다르다

현재 설계에는 두 가지 종류의 작업이 섞여있다.

```
코딩 영역 (전통적 코드가 하는 것)
├── KIS API 호출하여 데이터 수집
├── RSI = 58.3 계산 (pandas-ta)
├── DB에 저장
├── 차트 그리기
└── 이것은 LLM이 필요 없다. 그냥 코드가 한다.

판단 영역 (LLM이 해야 하는 것)
├── "RSI 58이면 중립인가? 과매수 직전인가?"
├── "금리 안정 + VIX 하락 + 수급 양호 = 상승장인가?"
├── "지금이 엘리엇 3파인가 5파인가?"
├── "이 종목의 단기 조정은 매수 기회인가 하락 시작인가?"
└── 이것은 코드로 하드코딩할 수 없다. LLM이 추론해야 한다.
```

**현재 설계의 구멍:**
지금까지 우리는 "시장 상태 판단", "파동 카운팅", "종합 전략 제안" 같은 것을
마치 코드가 자동으로 해주는 것처럼 설계했다.
하지만 실제로는 이 판단을 **런타임 LLM**이 해야 한다.

---

## 2. Claude Code ≠ 런타임 LLM

이 둘은 완전히 다른 역할이다.

```
┌─────────────────────────────────────────────────────┐
│  Claude Code (개발 도구)                               │
│                                                       │
│  역할: 코드를 작성하고, 파일을 만들고, 테스트를 돌린다     │
│  동작 시점: 개발할 때 (당신이 터미널에서 작업할 때)        │
│  비용: Max 5x 구독료 ($100/월)                         │
│  특징: 개발이 끝나면 더 이상 호출되지 않음                 │
│                                                       │
│  비유: 건물을 짓는 건설사                                │
└─────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────┐
│  런타임 LLM (운용 두뇌)                                 │
│                                                       │
│  역할: 수집된 데이터를 읽고, 분석하고, 판단을 내린다       │
│  동작 시점: 매일 아침 배치, 실시간 시그널 감지 시          │
│  비용: API 호출당 과금 (토큰 단위)                       │
│  특징: 시스템이 살아있는 한 계속 호출됨                    │
│                                                       │
│  비유: 건물에 입주한 전문가                               │
└─────────────────────────────────────────────────────┘
```

**Claude Code는 집을 짓는 사람이고, 런타임 LLM은 그 집에서 일하는 전문가다.**
집이 완성되면 건설사는 떠나지만, 전문가는 매일 출근한다.

---

## 3. 런타임 LLM 호출 구조

### 어디서 LLM을 호출하는가?

```python
# teams/macro-analysis/src/market_state_judge.py

import anthropic  # 또는 openai, google.generativeai

def judge_market_state(collected_data: dict) -> dict:
    """
    수집된 매크로 데이터를 LLM에게 보내서 시장 상태를 판단받는다.
    이것은 코드가 아니라 LLM이 하는 추론이다.
    """
    
    # 1단계: 코드가 한 것 (이미 완료)
    # collected_data = {
    #     "us_10y_yield": 4.28,
    #     "dxy": 103.4,
    #     "vix": 15.2,
    #     "kospi_change": "+1.2%",
    #     "fear_greed": 62,
    #     ...
    # }
    
    # 2단계: LLM에게 판단을 요청
    client = anthropic.Anthropic()  # API 키는 .env에서 로드
    
    # 페르소나 + 데이터 + 질문을 조합하여 프롬프트 생성
    persona = load_file("teams/macro-analysis/persona.md")
    knowledge = load_recent_knowledge("knowledge/macro/")
    
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=f"""
{persona}

아래는 당신이 참고할 학습 자료에서 추출한 핵심 원칙입니다:
{knowledge}

당신은 이 원칙에 기반하여 판단합니다.
반드시 JSON 형태로 응답하세요.
""",
        messages=[{
            "role": "user",
            "content": f"""
오늘의 매크로 데이터:
{json.dumps(collected_data, ensure_ascii=False, indent=2)}

위 데이터를 기반으로 시장 상태를 판단하세요.
응답 형식:
{{
  "verdict": "상승장" | "조정장" | "하락장",
  "confidence": 0-100,
  "reasons": ["이유1", "이유2", ...],
  "risks": ["위험요소1", ...],
  "recommendation": "짧은 한줄 요약"
}}
"""
        }]
    )
    
    return json.loads(response.content[0].text)
```

### 각 팀별 LLM 호출 필요 여부

| 팀 | LLM 필요? | 이유 |
|----|----------|------|
| 매크로 분석 | ✅ 필요 | "이 데이터 조합이 상승장인가?" — 규칙으로 커버 불가 |
| 기술적 분석 | ✅ 필요 | "지금이 몇 파인가?", "이 패턴은 무엇인가?" |
| 수급/종목 관리 | ⚠️ 부분적 | 거래대금 순위는 코드, "이 수급이 의미하는 바"는 LLM |
| 원칙 관리 | ❌ 불필요 | 비중 20% 초과 같은 건 코드로 체크 가능 (규칙 기반) |
| 계좌 관리 | ❌ 불필요 | MDD 계산, 샤프지수는 수학 공식 (코드) |
| 오케스트레이터 | ✅ 필요 | 각 팀 결과를 종합하여 최종 판단 — 핵심 LLM 역할 |

**LLM 호출이 필요한 곳: 매크로팀, 기술적분석팀, 오케스트레이터 (3곳)**
나머지는 전통적 코드로 충분하다.

---

## 4. LLM 선택지와 비용

### 사용 가능한 LLM 모델

| 제공자 | 모델 | 입력 비용 | 출력 비용 | 특징 |
|--------|------|----------|----------|------|
| **Anthropic** | Claude Sonnet 4 | $3/MTok | $15/MTok | 균형잡힌 판단력, 한국어 우수 |
| **Anthropic** | Claude Haiku 4.5 | $0.80/MTok | $4/MTok | 빠르고 저렴, 단순 판단에 적합 |
| **Anthropic** | Claude Opus 4 | $15/MTok | $75/MTok | 최고 추론력, 비쌈 |
| **OpenAI** | GPT-4o | $2.50/MTok | $10/MTok | 범용적, 영어 강점 |
| **OpenAI** | GPT-4o-mini | $0.15/MTok | $0.60/MTok | 매우 저렴, 간단한 판단 |
| **Google** | Gemini 2.5 Pro | $1.25/MTok | $10/MTok | 긴 컨텍스트, 멀티모달 |

### 일일 비용 추정 (매일 아침 배치 기준)

```
1회 판단 호출 당 토큰 추정:
  - system prompt (페르소나 + 학습자료 요약): ~2,000 토큰
  - user prompt (수집 데이터): ~1,000 토큰
  - 응답: ~500 토큰
  - 합계: ~3,500 토큰 / 1회 호출

매일 아침 호출 횟수:
  - 매크로 판단: 1회
  - 기술적 분석 (관심종목 10개): 10회
  - 오케스트레이터 종합: 1회
  - 합계: ~12회 / 일

일일 토큰 사용량: 3,500 × 12 = ~42,000 토큰

일일 비용 (Sonnet 4 기준):
  입력: 36,000 × $3/MTok = $0.108
  출력: 6,000 × $15/MTok = $0.090
  합계: ~$0.20 / 일 (약 ₩280)

월간 비용: ~$6 / 월 (약 ₩8,400)
```

**놀라울 정도로 싸다.** 월 만원도 안 된다.
관심종목이 50개로 늘어도 월 $25 수준.

---

## 5. 멀티 LLM 크로스 검증

### 왜 하나보다 여러 개가 나은가

```
단일 LLM의 문제:
  Claude가 "상승장"이라고 했다.
  → 근데 이게 Claude의 편향은 아닌가?
  → Claude가 특정 패턴을 과대평가하는 건 아닌가?
  → 확인할 방법이 없다.

멀티 LLM 크로스 검증:
  Claude: "상승장 (78%)"
  GPT-4o: "상승장 (72%)"
  Gemini: "조정장 (55%)"
  → 2:1로 상승장이지만, Gemini가 조정장 가능성을 봤다.
  → "상승장이나 조정 리스크 존재" — 더 정교한 판단 가능.
```

### 구현 방법: 투표 시스템

```python
# core/orchestrator/multi_llm_judge.py

from enum import Enum
from dataclasses import dataclass

class LLMProvider(Enum):
    CLAUDE_SONNET = "claude-sonnet-4"
    GPT_4O = "gpt-4o"
    GEMINI_PRO = "gemini-2.5-pro"

@dataclass
class LLMVote:
    provider: LLMProvider
    verdict: str        # "상승장", "조정장", "하락장"
    confidence: int     # 0-100
    reasons: list[str]
    cost: float         # 이번 호출 비용

def multi_llm_judge(prompt: str, providers: list[LLMProvider]) -> dict:
    """
    동일한 프롬프트를 여러 LLM에게 보내고, 투표 결과를 종합한다.
    """
    votes: list[LLMVote] = []
    
    for provider in providers:
        vote = call_llm(provider, prompt)  # 각각 API 호출
        votes.append(vote)
    
    # 다수결 + 신뢰도 가중평균
    verdict_counts = Counter(v.verdict for v in votes)
    majority_verdict = verdict_counts.most_common(1)[0][0]
    
    # 반대 의견이 있으면 리스크로 기록
    dissenting = [v for v in votes if v.verdict != majority_verdict]
    
    weighted_confidence = sum(v.confidence for v in votes if v.verdict == majority_verdict)
    weighted_confidence /= len([v for v in votes if v.verdict == majority_verdict])
    
    return {
        "final_verdict": majority_verdict,
        "confidence": round(weighted_confidence),
        "consensus": len(votes) - len(dissenting),  # 몇 대 몇
        "total_votes": len(votes),
        "votes": [
            {
                "provider": v.provider.value,
                "verdict": v.verdict,
                "confidence": v.confidence,
                "reasons": v.reasons
            }
            for v in votes
        ],
        "dissenting_risks": [
            f"{v.provider.value}는 '{v.verdict}'으로 판단. 이유: {v.reasons}"
            for v in dissenting
        ],
        "total_cost": sum(v.cost for v in votes)
    }
```

### 크로스 검증 비용

```
단일 LLM (Sonnet만):     $0.20/일  →  $6/월
듀얼 LLM (Sonnet + GPT): $0.35/일  →  $10.5/월
트리플 LLM (3개 전부):     $0.55/일  →  $16.5/월
```

월 $10~17 차이로 신뢰도가 크게 올라간다면 충분히 가치가 있다.

### 어디에 크로스 검증을 적용할 것인가

| 판단 종류 | 크로스 검증? | 이유 |
|----------|------------|------|
| **시장 상태 판단** | ✅ 트리플 | 하루 1회. 비용 작고 영향력 큼. |
| **종목별 기술 분석** | ⚠️ 듀얼 | 종목 수에 따라 비용 증가. 주요 종목만 듀얼. |
| **오케스트레이터 종합** | ✅ 트리플 | 최종 판단. 가장 중요. |
| **트레이딩 시그널** | ⚠️ 듀얼 | 실제 매매 판단. 신뢰도 중요. |
| **수급 해석** | ❌ 싱글 | 보조 정보. 비용 절감. |

---

## 6. .env에 추가할 API 키

```bash
# === 런타임 LLM API 키 ===
ANTHROPIC_API_KEY=sk-ant-...          # Claude API (필수)
OPENAI_API_KEY=sk-...                  # GPT-4o API (크로스 검증 시)
GOOGLE_AI_API_KEY=AI...                # Gemini API (크로스 검증 시)

# === LLM 설정 ===
LLM_PRIMARY=claude-sonnet-4            # 기본 모델
LLM_SECONDARY=gpt-4o                   # 크로스 검증 모델 (옵셔널)
LLM_TERTIARY=gemini-2.5-pro            # 3차 검증 모델 (옵셔널)
LLM_CROSSCHECK_ENABLED=false           # 크로스 검증 활성화 여부
LLM_CROSSCHECK_TARGETS=market_state,orchestrator  # 어디에 적용할지
```

---

## 7. 페르소나가 LLM 판단에 어떻게 작용하는가

```
이것이 핵심이다:

persona.md는 LLM의 system prompt에 주입된다.
→ 같은 데이터를 줘도 페르소나에 따라 판단이 달라진다.
→ "파동 이론 전문가"는 파동 관점에서 보고,
   "매크로 이코노미스트"는 금리/유동성 관점에서 본다.
→ 이것이 "각 팀이 다른 관점으로 분석한다"의 실체다.

knowledge/의 학습 자료도 system prompt에 포함된다.
→ 당신이 투입한 파동이론 자료가 LLM의 판단 근거가 된다.
→ 자료를 더 많이 넣을수록 판단이 정교해진다.
→ 이것이 "팀이 학습하여 성장한다"의 실체다.
```

```python
# 런타임 호출 시 프롬프트 조립 과정

def build_team_prompt(team_id: str) -> str:
    """각 팀의 persona + knowledge를 조합하여 system prompt를 만든다"""
    
    persona = read_file(f"teams/{team_id}/persona.md")
    
    # 학습 자료에서 핵심 원칙만 추출 (전체를 넣으면 토큰 낭비)
    knowledge_summary = read_file(f"teams/{team_id}/CLAUDE.md")
    # CLAUDE.md의 "학습된 지식" 섹션에 요약이 있음
    
    system_prompt = f"""
{persona}

## 참고할 학습 자료 요약
{knowledge_summary}

## 응답 규칙
- 반드시 JSON 형태로 응답
- confidence는 0-100 사이
- 최소 3가지 근거를 제시
- 확신이 없으면 confidence를 낮추고 불확실성을 명시
"""
    return system_prompt
```

---

## 8. 아키텍처에 반영할 변경 사항

### 기존 설계에서 바뀌는 것

```
기존 (코드만으로 판단한다고 암묵적으로 가정):
  데이터 수집 → 지표 계산 → 규칙 기반 판단 → 리포트

수정 (LLM이 판단한다는 것을 명시):
  데이터 수집 → 지표 계산 → LLM 판단 호출 → 리포트
  (코드 영역)   (코드 영역)   (LLM 영역)     (코드 영역)
```

### .env.example에 추가

```bash
# === 런타임 LLM ===
ANTHROPIC_API_KEY=sk-ant-your-key      # 필수
OPENAI_API_KEY=sk-your-key             # 옵셔널 (크로스 검증)
GOOGLE_AI_API_KEY=your-key             # 옵셔널 (크로스 검증)
LLM_PRIMARY=claude-sonnet-4
LLM_CROSSCHECK_ENABLED=false
```

### 루트 CLAUDE.md에 추가할 내용

```markdown
## 런타임 LLM 규칙
- 데이터 수집/계산은 코드가 한다. 판단/해석은 LLM API를 호출한다.
- 기본 모델: Claude Sonnet 4 (ANTHROPIC_API_KEY 필요)
- 크로스 검증: LLM_CROSSCHECK_ENABLED=true 시 GPT-4o, Gemini도 호출
- LLM 호출 시 반드시 해당 팀의 persona.md를 system prompt에 포함
- LLM 응답은 반드시 JSON 파싱 후 DB에 저장 (원본 텍스트도 보존)
- LLM 호출 실패 시: 이전 판단을 유지하고 알림. 크래시 금지.
```

### Feature Wave에 추가할 항목

```
Wave 2에 추가:
  F08-b ★필수  LLM 판단 호출 모듈 (core/llm-client)
               Anthropic API 래핑, 프롬프트 조립, JSON 파싱
               예상: 세션 2회

Wave 4에 추가:
  F18-b 옵셔널  멀티 LLM 크로스 검증 모듈
               투표 시스템, 비용 추적, 반대 의견 기록
               예상: 세션 2~3회
```

---

## 9. 요약

```
질문: "누가 판단하는가?"
답: 런타임 LLM이 한다. Claude Code가 아니다.

질문: "비용은?"
답: 단일 LLM 월 ~₩8,000 / 크로스 검증 월 ~₩23,000

질문: "페르소나와 학습 자료는 어떻게 작용하는가?"
답: LLM의 system prompt에 주입된다. 이것이 "전문가처럼 판단"의 실체다.

질문: "크로스 검증하면 더 좋은가?"
답: 그렇다. 시장 상태 판단과 오케스트레이터 종합에 트리플 검증 권장.
    월 1만원 추가로 편향 리스크를 줄일 수 있다.
```
