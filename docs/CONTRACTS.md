# 🔗 CONTRACTS.md — 팀 간 메시지 및 데이터 계약

> 팀끼리는 **코드를 import 하지 않습니다**. 오직 DB 테이블과 이 문서에 정의된 표준 JSON 메시지로만 소통합니다.

---

## 📜 계약 버전 관리

모든 계약은 `contract_version` 을 갖습니다. 변경 시:
1. 새 버전 추가 (`core/contracts/` 에 v1, v2 공존)
2. 팀별로 점진 마이그레이션
3. 하위 호환성 불가 변경은 **반드시 사전 공지** (CHANGELOG)
4. 3개 버전 이상 쌓이면 구버전 정리 제안 (진화팀)

현재 버전: **v1.0**

---

## 📤 StandardOutput (팀 판단의 표준 형식)

모든 팀은 `agent.run()` 의 결과로 이 구조를 반환하고, DB의 `team_outputs` 테이블에 저장합니다.

### JSON 스키마
```json
{
  "team_id": "principles",
  "run_id": "2026-04-16T09:00:00Z#d3a1",
  "timestamp": "2026-04-16T09:00:00+09:00",
  "target": "global",
  "verdict": "compliant",
  "confidence": 92,
  "reasons": [
    "총 비중 65%로 80% 제한 이내",
    "단일 종목 최대 12%로 15% 이내",
    "모든 포지션에 손절가 설정됨"
  ],
  "data": {
    "total_weight_pct": 65,
    "max_single_stock_pct": 12,
    "trading_weight_pct": 18,
    "violations": []
  },
  "contract_version": "1.0",
  "metadata": {
    "model": "rule-based",
    "canon_version": null,
    "retrieved_chunk_ids": [],
    "input_hash": "sha256:ab12..."
  }
}
```

### 필드 설명
| 필드 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `team_id` | str | ✅ | `teams/<id>/manifest.yaml` 의 id |
| `run_id` | str | ✅ | 실행 식별자. 오케스트레이터가 부여 (timestamp#short-hash) |
| `timestamp` | ISO-8601 with TZ | ✅ | 판단 생성 시각 |
| `target` | str | ✅ | 판단 대상. `"global"` 또는 티커 코드 |
| `verdict` | str | ✅ | 팀별 고유 판단값 (팀이 자유롭게 정의) |
| `confidence` | int (0-100) | ✅ | 신뢰도 |
| `reasons` | List[str] | ✅ | 최소 1개 이상. 규칙 기반 팀은 3개 권장. |
| `data` | dict | ✅ | 팀별 고유 데이터 (자유 스키마) |
| `contract_version` | str | ✅ | "1.0" |
| `metadata` | dict | ✅ | 모델·지식 버전·input_hash 등 재현성 정보 |

### Pydantic 모델
`core/contracts/team_output.py` 에 정의. 모든 팀은 이 모델을 반환해야 합니다.

---

## 💾 DB 테이블 계약

### `team_outputs` — 팀 판단 저장소
```sql
CREATE TABLE team_outputs (
    run_id TEXT NOT NULL,
    team_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    target TEXT NOT NULL,
    verdict TEXT NOT NULL,
    confidence INTEGER NOT NULL,
    reasons_json TEXT NOT NULL,
    data_json TEXT NOT NULL,
    contract_version TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now')),
    PRIMARY KEY (run_id, team_id, target)
);

CREATE INDEX idx_team_outputs_team_time ON team_outputs (team_id, timestamp);
CREATE INDEX idx_team_outputs_target ON team_outputs (target, timestamp);
```

**규칙**: `ON CONFLICT REPLACE` 로 INSERT (멱등성).

### `team_memory` — 팀 맥락 메모리
Memory Layer 참조. `docs/RUNTIME.md` 의 메모리 섹션에 스키마 명시.

### `memory_rollup` — 일/주/월 요약
Memory Layer 참조.

### `llm_call_cache` — LLM 호출 캐시
Memory Layer 참조.

### `portfolio_log` (추후) — 계좌 이력
### `watchlist` (추후) — 관심 종목

---

## 🎯 Verdict 분류 (팀별 권장)

각 팀은 자기만의 `verdict` 값을 정의하되, **오케스트레이터가 이해할 수 있도록 CLAUDE.md 에 명시**합니다.

| 팀 | 권장 Verdict |
|---|---|
| `principles` | `compliant` \| `warning` \| `violation` |
| `daily-briefing` | `positive` \| `neutral` \| `caution` \| `alert` |
| `macro-analysis` (추후) | `상승장` \| `조정장` \| `하락장` |
| `technical-analysis` (추후) | `상승` \| `횡보` \| `하락` |
| `supply-demand` (추후) | `유입` \| `중립` \| `이탈` |

오케스트레이터는 팀의 manifest 또는 스키마 선언을 기반으로 verdict를 해석합니다.

---

## 🔁 오케스트레이터 실행 계약

오케스트레이터(`teams/orchestrator/src/agent.py`)가 팀들을 호출할 때:

### 입력
```python
@dataclass
class OrchestratorInput:
    run_id: str
    scenario: str | None     # e.g. "over-allocation" for demo
    source_mode: Literal["seed", "live"]
    force_rebuild: bool = False
    teams_filter: list[str] | None = None   # None = 모든 활성 팀
```

### 처리
1. `teams/registry.yaml` 에서 활성 팀 목록 로드
2. `manifest.yaml` 의 `depends_on` 을 반영한 실행 순서 계산 (토폴로지 정렬)
3. 같은 레벨의 팀들은 `asyncio.gather` 로 병렬 실행
4. 결과를 `team_outputs` 테이블에 저장
5. 각 팀이 알림 조건을 만족하면 `core/notification` 경유 발송

### 출력
```python
@dataclass
class OrchestratorResult:
    run_id: str
    started_at: str
    completed_at: str
    team_results: dict[str, StandardOutput]
    errors: dict[str, str]       # team_id -> error message (팀이 실패해도 전체는 진행)
```

**규칙**: 개별 팀이 실패해도 다른 팀은 계속 진행. `errors` 에 기록 + 알림.

---

## 🧠 Memory 계약 (요약)

상세는 `docs/RUNTIME.md` 의 Memory Layer 섹션.

### 멱등성 키
```
input_hash = sha256(
    canonical_json(input_data) +
    canonical_json(context_snapshot) +
    model_id +
    contract_version +
    canon_version
)
```

### 조회 API (`core.memory.loader`)
```python
async def load_context(
    team_id: str,
    target: str,
    token_budget: int = 4000,
) -> MemoryContext:
    """최근 14일 원본 + 12주 롤업 + 6개월 월간 롤업을 토큰 예산 내에서 추려 반환."""
```

### 저장 API
```python
async def persist_judgment(output: StandardOutput) -> None:
    """team_memory 에 저장. input_hash 중복이면 기존 레코드 반환."""
```

---

## 📚 Knowledge 계약 (요약)

상세는 `docs/RUNTIME.md` 의 Knowledge Layer 섹션.

### Canon 주입 API (`core.knowledge.compose`)
```python
async def build_system_prompt(
    team_id: str,
    query_for_rag: str | None = None,
) -> SystemPromptBundle:
    """
    persona + canon + (선택) RAG retrieved chunks 를 조합.
    Anthropic Prompt Caching breakpoint 포함.
    """
```

### RAG 검색 API
```python
async def retrieve(team_id: str, query: str, top_k: int = 3) -> list[KnowledgeChunk]:
    """Chroma 에서 유사 청크 검색. 출처/태그 포함."""
```

---

## 🚨 알림 계약

알림은 `core/notification/` 을 통해서만 발송. 팀은 직접 Telegram API를 호출하지 않음.

### Python API
```python
from core.notification import notify

await notify(
    team_id="principles",
    level="warning",          # info | warning | critical
    title="비중 초과 경고",
    body="총 투자비중이 82%로 제한(80%)을 초과했습니다.",
    related_target="global",
    related_run_id="...",
)
```

### 전송 경로
1. `config/runtime.yaml` 의 `telegram.enabled: true` 면 Telegram 발송
2. 미설정 또는 발송 실패 시 `data/notifications/<YYYY-MM-DD>.jsonl` 에 기록
3. webapp 이 `/api/notifications/recent` 로 조회

### 메시지 포맷 (config 기반)
`config/runtime.yaml.telegram.formats.<team_id>` 에 템플릿 정의:
```yaml
telegram:
  formats:
    principles: "⚠️ {title}\n{body}\n🎯 대상: {related_target}"
    daily-briefing: "📊 {title}\n\n{body}"
```

---

## 🔐 MCP 도구 계약

MCP 서버가 제공하는 도구는 표준 명명 규칙을 따릅니다:

| 패턴 | 예시 |
|---|---|
| `get_<resource>` | `get_daily_chart`, `get_fred_series` |
| `list_<resource>s` | `list_watchlist`, `list_investors` |
| `post_<action>` | `post_order` (안전장치 필수!), `post_notification` |

모든 MCP 도구는 mcp-servers/<id>/CLAUDE.md 에 도구 목록과 계약을 명시해야 합니다.

---

## 🧪 계약 테스트

각 팀의 `tests/test_agent.py` 는 **계약 테스트**를 반드시 포함:

```python
import pytest
from core.contracts.team_output import StandardOutput
from teams.principles.src.agent import Agent

@pytest.mark.asyncio
async def test_agent_returns_standard_output():
    agent = Agent()
    result = await agent.run({"scenario": "normal"})
    # 타입 검증 (Pydantic이 자동)
    assert isinstance(result, StandardOutput)
    assert result.team_id == "principles"
    assert result.contract_version == "1.0"
    assert 0 <= result.confidence <= 100
    assert len(result.reasons) >= 1
```

`just validate` 가 모든 팀에 이 테스트의 존재를 검증합니다.
