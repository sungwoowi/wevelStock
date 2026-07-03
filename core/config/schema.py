"""Runtime config schema (Pydantic models).

This defines the typed shape of config/defaults.yaml merged with
config/runtime.yaml. Invalid config → previous config is kept + error logged.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DatabaseConfig(BaseModel):
    path: str = "data/db/stock-advisor.sqlite"


class LoggingConfig(BaseModel):
    level: str = "INFO"
    format: Literal["json", "text"] = "json"


class AnthropicLLMConfig(BaseModel):
    model: str = "claude-sonnet-4-5"
    max_tokens: int = 2000
    temperature: float = 0.3
    prompt_caching: bool = True


class ClaudeCodeLLMConfig(BaseModel):
    """Backend that shells out to the `claude` CLI (Claude Code).

    Uses the subscription auth (OAuth) already stored by `claude setup-token`.
    Does not require ANTHROPIC_API_KEY.
    """
    binary: str = "claude"
    timeout_sec: int = 90
    extra_args: list[str] = Field(default_factory=list)


class GeminiLLMConfig(BaseModel):
    """Google Gemini via AI Studio API (google-genai SDK).

    Requires GOOGLE_AI_API_KEY. Free tier available.
    """
    model: str = "gemini-2.5-flash"
    max_tokens: int = 4096
    temperature: float = 0.3


class CrosscheckConfig(BaseModel):
    enabled: bool = False
    targets: list[str] = Field(default_factory=list)


# PRODUCTION-UX-001 — LLM 3계층 정책 (FAST / BALANCED / DEEP, Gemini-Anthropic 1:1 mirror).
# 영역별 tier 매핑: intent_classifier·answer_formatter = FAST (저렴+빠름),
# analyst·strategist = BALANCED (현재 default 유지), 회고분석가 등 무거운 합성 = DEEP.

TierName = Literal["fast", "balanced", "deep"]


class LLMTierModels(BaseModel):
    """단일 tier 의 provider-별 모델 매핑."""

    gemini: str
    anthropic: str


class LLMTiers(BaseModel):
    """3 tier × 2 provider 매트릭스. provider 가 바뀌어도 area→tier 매핑은 그대로."""

    fast: LLMTierModels = Field(
        default_factory=lambda: LLMTierModels(
            gemini="gemini-2.5-flash-lite", anthropic="claude-haiku-4-5"
        )
    )
    balanced: LLMTierModels = Field(
        default_factory=lambda: LLMTierModels(
            gemini="gemini-2.5-flash", anthropic="claude-sonnet-4-5"
        )
    )
    deep: LLMTierModels = Field(
        default_factory=lambda: LLMTierModels(
            gemini="gemini-2.5-pro", anthropic="claude-opus-4-6"
        )
    )


class LLMAreas(BaseModel):
    """영역별 tier 매핑. 신규 영역 = LLM-TIER-MIGRATION-001 후속에서 추가."""

    intent_classifier: TierName = "fast"
    answer_formatter: TierName = "fast"
    analyst: TierName = "balanced"
    strategist: TierName = "balanced"
    anchors_stage2: TierName = "balanced"
    retrospect: TierName = "deep"
    # 기본 = Flash(balanced, 무료 1,500/일). Pro(deep)는 주요 트리거/이벤트만 model override.
    executive_synthesis: TierName = "balanced"


class LLMConfig(BaseModel):
    # "anthropic" = direct Anthropic SDK with ANTHROPIC_API_KEY
    # "claude_code" = subprocess via local `claude` CLI (subscription auth)
    # "gemini" = Google Gemini via GOOGLE_AI_API_KEY (free tier available)
    # "mock" = deterministic fallback (dev/CI)
    provider: Literal["anthropic", "claude_code", "gemini", "mock"] = "anthropic"
    primary: str = "claude-sonnet-4-5"
    mock_if_no_key: bool = True
    anthropic: AnthropicLLMConfig = Field(default_factory=AnthropicLLMConfig)
    claude_code: ClaudeCodeLLMConfig = Field(default_factory=ClaudeCodeLLMConfig)
    gemini: GeminiLLMConfig = Field(default_factory=GeminiLLMConfig)
    crosscheck: CrosscheckConfig = Field(default_factory=CrosscheckConfig)
    tiers: LLMTiers = Field(default_factory=LLMTiers)
    areas: LLMAreas = Field(default_factory=LLMAreas)


class TelegramConfig(BaseModel):
    enabled: bool = True
    fallback_dir: str = "data/notifications"
    formats: dict[str, str] = Field(
        default_factory=lambda: {
            "default": "🔔 *{title}*\n{body}",
        }
    )


class MemoryRetention(BaseModel):
    raw_days: int = 180
    daily_days: int = 365
    weekly_days: int = 730
    monthly_days: int | None = None


class MemoryIdempotency(BaseModel):
    enabled: bool = True
    cache_ttl_days: int = 7


class MemoryConfig(BaseModel):
    enabled: bool = True
    retention: MemoryRetention = Field(default_factory=MemoryRetention)
    context_budget_tokens: int = 4000
    idempotency: MemoryIdempotency = Field(default_factory=MemoryIdempotency)


class KnowledgeEmbedConfig(BaseModel):
    provider: Literal["openai", "local"] = "local"
    model: str = "BAAI/bge-m3"


class KnowledgeRetrievalConfig(BaseModel):
    default_top_k: int = 3
    score_threshold: float = 0.0


class KnowledgeConfig(BaseModel):
    enabled: bool = True
    embedding: KnowledgeEmbedConfig = Field(default_factory=KnowledgeEmbedConfig)
    retrieval: KnowledgeRetrievalConfig = Field(default_factory=KnowledgeRetrievalConfig)


class JobCronConfig(BaseModel):
    cron: str | None = None
    day: str | int | None = None
    hour: int | None = None
    minute: int | None = None


class SchedulerConfig(BaseModel):
    backup: JobCronConfig = Field(default_factory=lambda: JobCronConfig(cron="0 0 * * *"))
    daily_rollup: JobCronConfig = Field(
        default_factory=lambda: JobCronConfig(cron="50 23 * * *")
    )
    weekly_rollup: JobCronConfig = Field(
        default_factory=lambda: JobCronConfig(cron="55 23 * * 0")
    )
    monthly_rollup: JobCronConfig = Field(
        default_factory=lambda: JobCronConfig(day="last", hour=23, minute=58)
    )
    memory_cleanup: JobCronConfig = Field(
        default_factory=lambda: JobCronConfig(day=1, hour=3, minute=0)
    )


class PrincipleThresholds(BaseModel):
    total_weight_pct: float = 80
    single_stock_pct: float = 15
    trading_weight_pct: float = 20
    min_stop_loss_ratio: float = 0.02
    max_stop_loss_ratio: float = 0.20


class PrincipleTeamConfig(BaseModel):
    enabled: bool = True
    thresholds: PrincipleThresholds = Field(default_factory=PrincipleThresholds)
    notify_on: list[str] = Field(default_factory=lambda: ["warning", "violation"])


class DailyBriefingTeamConfig(BaseModel):
    enabled: bool = True
    model_override: str | None = None
    include_teams: list[str] = Field(default_factory=lambda: ["principles"])
    notify_on: list[str] = Field(default_factory=lambda: ["info", "warning", "critical"])


class OrchestratorTeamConfig(BaseModel):
    enabled: bool = True
    max_parallel: int = 4


class TeamsConfig(BaseModel):
    """Known teams with typed config. Unknown teams use the generic dict."""

    principles: PrincipleTeamConfig = Field(default_factory=PrincipleTeamConfig)
    daily_briefing: DailyBriefingTeamConfig = Field(
        default_factory=DailyBriefingTeamConfig
    )
    orchestrator: OrchestratorTeamConfig = Field(default_factory=OrchestratorTeamConfig)
    extra: dict[str, dict] = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class CORSConfig(BaseModel):
    allowed_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000"]
    )


class ServerConfig(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8000
    cors: CORSConfig = Field(default_factory=CORSConfig)


class AlphaConfig(BaseModel):
    """WAVE-ALPHA anchor 산출 정책 (LLM-COST-LEDGER-001 후속, 2026-07-04).

    anchor_llm_enabled=False (기본): anchor A·B·C 선택을 결정론 코드로. 실 Gemini 대비
      성공 픽은 α 소수점까지 동일하고, LLM 의 'C=최근점→current 충돌' 실패를 회피(검증됨).
      universe × 3 timeframe × 매일 도는 LLM anchor 비용을 0 으로.
    True: Stage 2 LLM anchor 를 되살림(되돌리기 가능).
    """

    anchor_llm_enabled: bool = False


class RuntimeConfig(BaseModel):
    """Top-level merged config."""

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    timezone: str = "Asia/Seoul"
    source_mode: Literal["seed", "live"] = "seed"
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    memory: MemoryConfig = Field(default_factory=MemoryConfig)
    knowledge: KnowledgeConfig = Field(default_factory=KnowledgeConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    teams: TeamsConfig = Field(default_factory=TeamsConfig)
    server: ServerConfig = Field(default_factory=ServerConfig)
    alpha: AlphaConfig = Field(default_factory=AlphaConfig)

    model_config = {"populate_by_name": True}
