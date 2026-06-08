"""비중 산정 결정론 코어 — ACCOUNT-MANAGER-001 (RB-MS1).

전략가 권고(strategist-recommendation-v1) → position-sizing-v1.
**두 레버**(인터뷰 2026-06-09 확정):
  레버 1 — 종목당 고정 리스크 R: `수량 = (계좌자본 × R) ÷ (진입가 − stop)`.
           변동성·stop 먼 종목은 비중 자동 축소 → MDD 구조적 통제. 점수는 R 배수 상한 advisory.
  레버 2 — 총 배포 한도: regime/entry_posture 로 변조(강세장 상향·위험장 하향, vix_panic 동결).
**분할**: 과열도(extension_score, 높을수록 저과열) 함수 — 저과열 front-load / 고과열 back-load.
**7계명 게이트**: 비중 한도 초과 = 자동 축소, stop_loss 누락 = 하드 차단(유일).

순수 결정론 (DB·LLM·네트워크 0) — `classify_us_risk` mirror. config 명시 주입 가능(파일 비의존).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
ACCOUNTS_PATH = REPO_ROOT / "config" / "accounts.yaml"

# 보수적 기본값 — 수치는 다일 누적 후 튜닝 SLOT([[feedback_backtest_essence]]).
_DEFAULT_SIZING: dict[str, Any] = {
    "risk_per_trade": {"A": 0.01, "B": 0.015},   # 중장기 1% / 단기 1.5%
    "conviction_threshold": 7.0,                 # 점수 ≥ 이 값 = 고확신 카운트
    "conviction_min_scores": 3,                  # 7계명 5번 — 최소 3개 교차 시만 보너스
    "conviction_r_bonus": 0.5,                   # 고확신 → +0.5R 상한
    "deployment_cap": {                          # 레버 2 — entry_posture → 총 배포 천장
        "aggressive": 0.80,                      # 7계명 1번 천장
        "neutral": 0.60,
        "defensive": 0.45,
    },
    "vix_panic_freeze": True,                    # 극단 게이트 — vix_panic 시 신규 진입 동결
    "commandments": {                            # 7계명 하드 제약
        "max_total_deployment": 0.80,
        "max_single_position": 0.15,
        "max_trading_deployment": 0.20,
    },
    "split_entry": {                             # 분할 — 과열도(extension) 구간 → 차수 비율
        "bands": [
            {"min_ext": 7.0, "ratios": [0.6, 0.3, 0.1]},   # 저과열·좋은 타점 front-load
            {"min_ext": 4.0, "ratios": [0.4, 0.3, 0.3]},   # 중립
            {"min_ext": 0.0, "ratios": [0.2, 0.3, 0.5]},   # 고과열 back-load 소액
        ],
        "neutral_ratios": [0.4, 0.3, 0.3],       # extension 부재(MA 없음) → 중립
    },
}

_DEFAULT_ACCOUNTS: list[dict[str, Any]] = [
    {"account_id": "kr_long", "market": "KR", "track": "A", "horizon": "long",
     "seed_krw": 10_000_000, "label": "국장 중장기"},
    {"account_id": "kr_swing", "market": "KR", "track": "B", "horizon": "swing",
     "seed_krw": 10_000_000, "label": "국장 단기"},
    {"account_id": "us_long", "market": "US", "track": "A", "horizon": "long",
     "seed_krw": 10_000_000, "label": "미장 중장기"},
    {"account_id": "us_swing", "market": "US", "track": "B", "horizon": "swing",
     "seed_krw": 10_000_000, "label": "미장 단기"},
]

_CONFIG_CACHE: dict[str, Any] | None = None


def load_accounts_config() -> dict[str, Any]:
    """config/accounts.yaml 로드 (캐시). 부재·파싱 실패 시 default 병합."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        cfg: dict[str, Any] = {
            "accounts": [dict(a) for a in _DEFAULT_ACCOUNTS],
            "sizing": {k: (dict(v) if isinstance(v, dict) else v) for k, v in _DEFAULT_SIZING.items()},
        }
        if ACCOUNTS_PATH.exists():
            try:
                loaded = yaml.safe_load(ACCOUNTS_PATH.read_text(encoding="utf-8")) or {}
                if loaded.get("accounts"):
                    cfg["accounts"] = loaded["accounts"]
                sizing = loaded.get("sizing") or {}
                for key, default_block in _DEFAULT_SIZING.items():
                    if isinstance(default_block, dict):
                        cfg["sizing"][key] = {**default_block, **(sizing.get(key) or {})}
                    else:
                        cfg["sizing"][key] = sizing.get(key, default_block)
            except Exception as e:  # noqa: BLE001
                log.warning("accounts_config_load_failed", error=str(e))
        else:
            log.warning("accounts_config_missing", path=str(ACCOUNTS_PATH))
        _CONFIG_CACHE = cfg
    return _CONFIG_CACHE


def reload_accounts_config() -> None:
    """테스트/hot reload — 캐시 클리어."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


def _sizing_cfg(config: dict[str, Any] | None) -> dict[str, Any]:
    return config if config is not None else load_accounts_config().get("sizing", _DEFAULT_SIZING)


# ---------------------------------------------------------------------------
# DataClasses — position-sizing-v1
# ---------------------------------------------------------------------------


@dataclass
class AccountDef:
    """4계좌 중 하나의 정의 (config/accounts.yaml)."""

    account_id: str
    market: str          # "KR" | "US"
    track: str           # "A" (중장기) | "B" (단기)
    horizon: str         # "long" | "swing"
    seed_krw: float
    label: str


@dataclass
class AccountState:
    """계좌 현 상태 — 비중 산정 입력 (RB-MS2 가상매매가 갱신, MS1 부트스트랩)."""

    account_id: str
    deployed_weight: float = 0.0          # 현 누적 비중 (0~1)
    trading_deployed_weight: float = 0.0  # 트레이딩(단기) 누적 비중 — 7계명 3번 추적
    positions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PositionTranche:
    """분할매수 한 차수."""

    index: int           # 1 | 2 | 3
    ratio: float         # 차수 비중 비율 (split_ratios)
    weight: float        # 계좌 대비 비중 (target_weight × ratio)
    value_krw: float
    shares: float


@dataclass
class PositionSizing:
    """position-sizing-v1 — 계좌별 비중·자금액·분할 산출물."""

    recommendation_id: str
    account_id: str
    account_label: str
    ticker: str
    track: str
    target_weight: float                  # 최종 비중 (0~1, 7계명·레버2 적용 후)
    value_krw: float
    shares: float
    risk_amount_krw: float                # 레버1 — 계좌자본 × R
    raw_shares: float                     # 캡 적용 전 리스크 역산 수량
    risk_fraction: float                  # 적용된 R
    tranches: list[PositionTranche] = field(default_factory=list)
    applied_caps: list[str] = field(default_factory=list)   # 자동 축소 사유
    blocked: bool = False
    block_reason: str = ""
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# 레버 1 — 종목당 고정 리스크 R
# ---------------------------------------------------------------------------


def resolve_risk_fraction(track: str, *, conviction_count: int, config: dict[str, Any] | None = None) -> float:
    """트랙별 기본 R + 고확신(점수 ≥ 임계 N개 교차) 시 보너스 상한.

    7계명 5번(단일 지표 금지): 보너스는 **최소 conviction_min_scores 개** 점수가 교차할 때만.
    """
    cfg = _sizing_cfg(config)
    base = float(cfg.get("risk_per_trade", {}).get(track, 0.01))
    min_scores = int(cfg.get("conviction_min_scores", 3))
    bonus = float(cfg.get("conviction_r_bonus", 0.5))
    if conviction_count >= min_scores:
        return base * (1.0 + bonus)
    return base


# ---------------------------------------------------------------------------
# 레버 2 — 총 배포 한도 (regime/entry_posture 변조)
# ---------------------------------------------------------------------------


def deployment_cap(entry_posture: str, *, extreme: str = "none", config: dict[str, Any] | None = None) -> float:
    """entry_posture → 총 배포 천장. vix_panic 극단 → 신규 진입 동결(0)."""
    cfg = _sizing_cfg(config)
    if extreme == "vix_panic" and bool(cfg.get("vix_panic_freeze", True)):
        return 0.0
    caps = cfg.get("deployment_cap", {})
    return float(caps.get(entry_posture, caps.get("neutral", 0.60)))


# ---------------------------------------------------------------------------
# 분할 — 과열도(extension_score) 함수
# ---------------------------------------------------------------------------


def split_ratios(extension: float | None, *, config: dict[str, Any] | None = None) -> list[float]:
    """과열도 → 차수 비율. extension 높을수록 저과열(front-load), 낮을수록 고과열(back-load).

    extension None(MA 부재) → 중립 비율(추정 금지).
    """
    cfg = _sizing_cfg(config).get("split_entry", _DEFAULT_SIZING["split_entry"])
    if extension is None:
        return list(cfg.get("neutral_ratios", [0.4, 0.3, 0.3]))
    bands = cfg.get("bands", _DEFAULT_SIZING["split_entry"]["bands"])
    for band in sorted(bands, key=lambda b: float(b["min_ext"]), reverse=True):
        if extension >= float(band["min_ext"]):
            return list(band["ratios"])
    return list(bands[-1]["ratios"]) if bands else [0.4, 0.3, 0.3]


# ---------------------------------------------------------------------------
# 통합 — size_position (두 레버 + 분할 + 7계명 게이트)
# ---------------------------------------------------------------------------


def _conviction_count(cited_scores: dict[str, Any], threshold: float) -> int:
    """cited_scores 중 임계 이상인 수치 점수 개수 (None·비수치 제외)."""
    n = 0
    for v in (cited_scores or {}).values():
        if isinstance(v, (int, float)) and float(v) >= threshold:
            n += 1
    return n


def size_position(
    *,
    recommendation: dict[str, Any],
    account: AccountDef,
    state: AccountState,
    entry_posture: str,
    extension: float | None,
    extreme: str = "none",
    config: dict[str, Any] | None = None,
) -> PositionSizing:
    """전략가 권고 → 계좌별 비중·자금액·분할. 두 레버 + 7계명 게이트 결정론.

    Returns:
        PositionSizing. stop_loss 누락·진입가≤손절 → blocked. 한도 초과 → 자동 축소(applied_caps).
    """
    cfg = _sizing_cfg(config)
    cmd = cfg.get("commandments", _DEFAULT_SIZING["commandments"])
    threshold = float(cfg.get("conviction_threshold", 7.0))

    rec_id = str(recommendation.get("recommendation_id", ""))
    ticker = str(recommendation.get("ticker") or _ticker_from_rec_id(rec_id))
    track = str(recommendation.get("track", account.track))
    entry = recommendation.get("entry_price")
    stop = recommendation.get("stop_loss")
    cited = recommendation.get("cited_scores") or {}

    def _blocked(reason: str) -> PositionSizing:
        return PositionSizing(
            recommendation_id=rec_id, account_id=account.account_id, account_label=account.label,
            ticker=ticker, track=track,
            target_weight=0.0, value_krw=0.0, shares=0.0, risk_amount_krw=0.0,
            raw_shares=0.0, risk_fraction=0.0, blocked=True, block_reason=reason,
            reasons=[reason],
        )

    # 7계명 4번 — 손절선 없는 권고는 진입 차단 (유일한 하드 차단)
    if stop is None or entry is None:
        return _blocked("손절선(stop_loss) 누락 — 진입 차단 (7계명 4번 + 리스크 역산 불가)")
    entry_f = float(entry)
    stop_f = float(stop)
    risk_per_share = entry_f - stop_f
    if risk_per_share <= 0:
        return _blocked(f"진입가({entry_f}) ≤ 손절({stop_f}) — 리스크 역산 불가")

    # 레버 1 — 종목당 고정 리스크 R → 리스크 역산 수량
    conv = _conviction_count(cited, threshold)
    r = resolve_risk_fraction(track, conviction_count=conv, config=cfg)
    risk_amount = account.seed_krw * r
    raw_shares = risk_amount / risk_per_share
    raw_value = raw_shares * entry_f
    raw_weight = raw_value / account.seed_krw if account.seed_krw else 0.0

    reasons = [f"리스크 R={r:.3%} (확신 점수 {conv}개 교차) → 주당 리스크 {risk_per_share:.2f}, 역산 {raw_shares:.0f}주"]

    # 캡 후보 — (한도값, 사유). target = min(raw, 후보들). 바인딩된 것만 applied_caps.
    single_cap = float(cmd.get("max_single_position", 0.15))
    dep_cap = deployment_cap(entry_posture, extreme=extreme, config=cfg)
    total_ceiling = min(dep_cap, float(cmd.get("max_total_deployment", 0.80)))
    total_room = max(0.0, total_ceiling - state.deployed_weight)

    candidates: list[tuple[float, str]] = [
        (single_cap, f"단일 종목 {single_cap:.0%} 한도"),
        (total_room, f"총 배포 여력 {total_room:.0%} (천장 {total_ceiling:.0%}·{entry_posture})"),
    ]
    if track == "B":
        trading_cap = float(cmd.get("max_trading_deployment", 0.20))
        trading_room = max(0.0, trading_cap - state.trading_deployed_weight)
        candidates.append((trading_room, f"트레이딩 비중 {trading_cap:.0%} 한도 (여력 {trading_room:.0%})"))

    target_weight = raw_weight
    for cap_val, _ in candidates:
        target_weight = min(target_weight, cap_val)
    target_weight = max(0.0, target_weight)

    applied_caps = [reason for cap_val, reason in candidates if cap_val <= target_weight + 1e-12 and cap_val < raw_weight - 1e-12]

    # vix_panic 동결·여력 0 → 신규 진입 0 = 차단
    if target_weight <= 1e-9:
        block_reason = (
            "vix_panic 동결 — 신규 진입 차단(방어 하드)" if extreme == "vix_panic"
            else "배포 여력 없음 — 신규 진입 0"
        )
        out = _blocked(block_reason)
        out.risk_amount_krw = risk_amount
        out.raw_shares = raw_shares
        out.risk_fraction = r
        out.applied_caps = applied_caps
        out.reasons = reasons + [block_reason]
        return out

    value_krw = target_weight * account.seed_krw
    shares = value_krw / entry_f

    ratios = split_ratios(extension, config=cfg)
    tranches = [
        PositionTranche(
            index=i + 1,
            ratio=ratio,
            weight=target_weight * ratio,
            value_krw=value_krw * ratio,
            shares=(value_krw * ratio) / entry_f,
        )
        for i, ratio in enumerate(ratios)
    ]

    if applied_caps:
        reasons.append("자동 축소: " + " / ".join(applied_caps))
    reasons.append(f"분할 {[round(x, 2) for x in ratios]} (과열도 {extension if extension is not None else '—'})")

    return PositionSizing(
        recommendation_id=rec_id,
        account_id=account.account_id,
        account_label=account.label,
        ticker=ticker,
        track=track,
        target_weight=target_weight,
        value_krw=value_krw,
        shares=shares,
        risk_amount_krw=risk_amount,
        raw_shares=raw_shares,
        risk_fraction=r,
        tranches=tranches,
        applied_caps=applied_caps,
        blocked=False,
        reasons=reasons,
    )


def _ticker_from_rec_id(rec_id: str) -> str:
    """REC-YYYYMMDD-<ticker>-<track> 에서 ticker 추출 (best-effort)."""
    parts = rec_id.split("-")
    return parts[2] if len(parts) >= 4 else ""


# ---------------------------------------------------------------------------
# Render — 사람 친화 markdown (production 친화, 코드 라벨 금지)
# ---------------------------------------------------------------------------


def _won(v: float) -> str:
    """원화 친화 표기 (만/억 단위)."""
    if v >= 100_000_000:
        return f"{v / 100_000_000:.1f}억"
    if v >= 10_000:
        return f"{v / 10_000:.0f}만"
    return f"{v:,.0f}원"


def render_position_sizing_md(sizing: PositionSizing, *, label: str | None = None) -> str:
    """position-sizing-v1 → 사람 친화 markdown (코드 라벨 노출 X, 금액 병기)."""
    acct_label = label or sizing.account_label or sizing.account_id
    if sizing.blocked:
        return (
            f"**{acct_label}** · {sizing.ticker} — ⛔ 진입 차단\n"
            f"- 사유: {sizing.block_reason}"
        )

    pct = f"{sizing.target_weight * 100:.1f}%"
    head = (
        f"**{acct_label}** · {sizing.ticker} (Track {sizing.track}) — "
        f"비중 {pct} (약 {_won(sizing.value_krw)})"
    )
    lines = [head]
    if sizing.tranches:
        tr = " / ".join(
            f"{t.index}차 {_won(t.value_krw)}" for t in sizing.tranches
        )
        lines.append(f"- 분할매수: {tr}")
    if sizing.applied_caps:
        lines.append("- 자동 축소: " + " · ".join(sizing.applied_caps))
    lines.append(
        f"- 근거: 종목당 리스크 {sizing.risk_fraction * 100:.1f}% "
        f"(손절폭 역산 {sizing.raw_shares:.0f}주) → 7계명 한도 적용"
    )
    return "\n".join(lines)
