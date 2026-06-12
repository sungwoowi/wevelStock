"""미장 매크로 스냅샷 collector — INFRA-US-MACRO-SNAPSHOT-001 (LEFT-BRAIN 마지막 조각).

미국 야간 6 지표(나스닥·S&P·필라델피아 반도체·VIX·달러인덱스·미 10년물·금)를 **일자
스냅샷으로 영속**하고, **risk-on/off 한 신호**로 결정론 분류해 시장관(MarketView)에 흡수한다.

흐름 (market_macro.compute_market_macro DB-first hybrid mirror):
  1. `compute_us_macro()` — `us_macro_snapshot` 의 오늘(KST date) row 존재 시 즉시 반환.
  2. 없으면 `connectors.yfinance.get_indices()` 재사용(데이터는 이미 수집됨 — 신규 어댑터 X)
     → `classify_us_risk()` 결정론 분류 → `us_macro_snapshot` upsert.
  3. `build_market_view` 가 DB-first read 로 흡수 (entry_posture 단계 강등 + vix_panic 게이트 + one_liner 토큰).

핵심 (U1): 데이터 수집은 이미 yfinance 로 된다. 본 모듈 = **영속 + 분류 + 흡수**만.
capability 폴백([[feedback_silent_env_fallback]]): yfinance 미설치/네트워크 실패 → source="unavailable"
+ None 필드, 시장관 막지 않음(graceful).
판단 게이트는 극단(vix_panic)에 한정, 나머지 원시 지표는 LLM 주입([[feedback_score_collapse_advisory]]).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

from core.db import get_db
from core.logging import get_logger

log = get_logger(__name__)

_KST = ZoneInfo("Asia/Seoul")
REPO_ROOT = Path(__file__).resolve().parents[1]
US_MACRO_PATH = REPO_ROOT / "config" / "us_macro.yaml"

# get_indices 결과 키 → USMacroSnapshot 필드 매핑 (connector TRACKED_SYMBOLS 키).
# 야간자산 4종(wti·brent·nq_futures·es_futures)은 INFRA-MARKET-ASSETS-002 에서 추가 —
# gold 와 동일 야간 fetch 경로(connectors.yfinance get_indices). 컬럼만 영속.
_FETCH_NAMES = [
    "nasdaq", "sp500", "philly_semi", "vix", "dxy", "us_10y", "gold",
    "wti", "brent", "nq_futures", "es_futures",
]

RiskSignal = str   # "risk_on" | "neutral" | "risk_off"
Extreme = str      # "none" | "vix_panic"

_RISK_KR: dict[str, str] = {
    "risk_on": "위험선호",
    "neutral": "중립",
    "risk_off": "위험회피",
}

# 야간자산 한글 라벨 (INFRA-MARKET-ASSETS-002) — 텔레그램·웹앱 공통 단일 소스.
# "선물" 명시로 현물 지수(나스닥/S&P 등락률)와 혼동 방지. NQ/ES 는 미국 정규장 외에도
# 24시간 거래되는 지수선물이라 현물 일일 등락률과 기준이 다름(전일 대비). "야간" 단어는
# 순수 야간만의 등락이 아니라서 라벨에서 회피.
OVERNIGHT_ASSET_LABELS_KR: dict[str, str] = {
    "wti": "WTI 원유",
    "brent": "브렌트유",
    "nq_futures": "나스닥100 선물",
    "es_futures": "S&P500 선물",
}

_DEFAULT_CONFIG: dict[str, Any] = {
    "classify": {
        "w_sox": 0.5,            # 반도체 가중 (국장 연동 큼)
        "w_equity": 0.5,         # 나스닥·S&P 평균 가중
        "vix_elevated": 20.0,    # 이상 = 위험 가산
        "vix_panic": 30.0,       # 이상 = extreme=vix_panic (risk_off 강제)
        "vix_elevated_penalty": 1.0,
        "vix_panic_penalty": 3.0,
        "dxy_jump_pct": 0.5,     # 달러인덱스 일간 ≥ +0.5% = 역풍
        "dxy_penalty": 0.5,
        "rate_jump_bp": 10.0,    # 미 10년물 ≥ +10bp = 역풍
        "rate_penalty": 0.5,
        "on_threshold": 0.7,     # signal_score ≥ = risk_on
        "off_threshold": -0.7,   # signal_score ≤ = risk_off
    },
}

_CONFIG_CACHE: dict[str, Any] | None = None


def load_us_macro_config() -> dict[str, Any]:
    """config/us_macro.yaml 로드 (캐시). 부재·파싱 실패 시 default 병합."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        cfg = {k: dict(v) for k, v in _DEFAULT_CONFIG.items()}
        if US_MACRO_PATH.exists():
            try:
                loaded = yaml.safe_load(US_MACRO_PATH.read_text(encoding="utf-8")) or {}
                for key, default_block in _DEFAULT_CONFIG.items():
                    if isinstance(default_block, dict):
                        cfg[key] = {**default_block, **(loaded.get(key) or {})}
                    else:
                        cfg[key] = loaded.get(key, default_block)
            except Exception as e:  # noqa: BLE001
                log.warning("us_macro_config_load_failed", error=str(e))
        else:
            log.warning("us_macro_config_missing", path=str(US_MACRO_PATH))
        _CONFIG_CACHE = cfg
    return _CONFIG_CACHE


def reload_us_macro_config() -> None:
    """테스트/hot reload — 캐시 클리어."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


# ---------------------------------------------------------------------------
# DataClass — us-macro-snapshot-v1
# ---------------------------------------------------------------------------


@dataclass
class USMacroSnapshot:
    """미장 야간 매크로 스냅샷 — us-macro-snapshot-v1 계약."""

    date: str                          # "2026-06-07" KST
    nasdaq_change_pct: float | None
    sp500_change_pct: float | None
    sox_change_pct: float | None       # 필라델피아 반도체 (^SOX)
    vix: float | None
    vix_change_pct: float | None
    dxy: float | None
    dxy_change_pct: float | None
    us_10y: float | None               # 미 10년물 금리 수준 (%)
    us_10y_change_bp: float | None     # 전일 대비 bp 변화
    gold_change_pct: float | None
    risk_signal: RiskSignal            # "risk_on" | "neutral" | "risk_off"
    signal_score: float
    extreme: Extreme                   # "none" | "vix_panic"
    reasons: list[str] = field(default_factory=list)
    source: str = "computed"           # "db" | "computed" | "stale" | "unavailable"
    # 야간자산 (INFRA-MARKET-ASSETS-002) — 결정론 수집·영속만, 분류 미반영.
    wti_change_pct: float | None = None         # WTI 원유 선물
    brent_change_pct: float | None = None       # 브렌트 원유 선물
    nq_futures_change_pct: float | None = None  # 나스닥100 야간선물
    es_futures_change_pct: float | None = None  # S&P500 야간선물

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Pure helper — classify_us_risk (결정론, 단위 테스트 가능)
# ---------------------------------------------------------------------------


def classify_us_risk(
    *,
    nasdaq_change_pct: float | None,
    sp500_change_pct: float | None,
    sox_change_pct: float | None,
    vix: float | None,
    dxy_change_pct: float | None,
    us_10y_change_bp: float | None,
    config: dict[str, Any] | None = None,
) -> tuple[RiskSignal, float, Extreme, list[str]]:
    """미장 야간 risk-on/off 결정론 분류 (예측 X — **현재 상태 라벨링**).

    합성:
      주식 모멘텀 = w_sox·sox + w_equity·avg(nasdaq, sp500)  (반도체 가중 — 국장 연동 큼)
      − VIX 페널티 (panic → extreme 강제 / elevated → 가산)
      − 달러·금리 역풍 페널티
    → signal_score → bands(on/off threshold) → risk_signal.

    Returns:
        (risk_signal, signal_score, extreme, reasons).
        데이터 전부 결측 → ("neutral", 0.0, "none", [...]) (추정 금지).
    """
    cfg = (config or load_us_macro_config()).get("classify", {})
    w_sox = float(cfg.get("w_sox", 0.5))
    w_eq = float(cfg.get("w_equity", 0.5))
    vix_elevated = float(cfg.get("vix_elevated", 20.0))
    vix_panic = float(cfg.get("vix_panic", 30.0))
    elevated_pen = float(cfg.get("vix_elevated_penalty", 1.0))
    panic_pen = float(cfg.get("vix_panic_penalty", 3.0))
    dxy_jump = float(cfg.get("dxy_jump_pct", 0.5))
    dxy_pen = float(cfg.get("dxy_penalty", 0.5))
    rate_jump = float(cfg.get("rate_jump_bp", 10.0))
    rate_pen = float(cfg.get("rate_penalty", 0.5))
    on_th = float(cfg.get("on_threshold", 0.7))
    off_th = float(cfg.get("off_threshold", -0.7))

    reasons: list[str] = []

    # 주식 모멘텀 (결측 컴포넌트는 가중에서 제외 — 있는 신호만)
    equity_terms: list[tuple[float, float]] = []  # (weight, value)
    eq_pair = [v for v in (nasdaq_change_pct, sp500_change_pct) if v is not None]
    if eq_pair:
        equity_terms.append((w_eq, sum(eq_pair) / len(eq_pair)))
    if sox_change_pct is not None:
        equity_terms.append((w_sox, sox_change_pct))

    have_any = bool(equity_terms) or vix is not None or dxy_change_pct is not None or us_10y_change_bp is not None
    if not have_any:
        return "neutral", 0.0, "none", ["미장 데이터 결측 — 중립(추정 안 함)"]

    if equity_terms:
        wsum = sum(w for w, _ in equity_terms)
        equity_score = sum(w * v for w, v in equity_terms) / wsum if wsum else 0.0
        reasons.append(f"주식 모멘텀 {equity_score:+.2f}% (반도체 가중)")
    else:
        equity_score = 0.0

    score = equity_score

    # VIX
    extreme: Extreme = "none"
    if vix is not None:
        if vix >= vix_panic:
            extreme = "vix_panic"
            score -= panic_pen
            reasons.append(f"VIX {vix:.1f} ≥ 패닉 {vix_panic:.0f} → 위험회피 게이트")
        elif vix >= vix_elevated:
            score -= elevated_pen
            reasons.append(f"VIX {vix:.1f} ≥ 경계 {vix_elevated:.0f} → 위험 가산")

    # 달러·금리 역풍
    if dxy_change_pct is not None and dxy_change_pct >= dxy_jump:
        score -= dxy_pen
        reasons.append(f"달러인덱스 +{dxy_change_pct:.2f}% → 역풍")
    if us_10y_change_bp is not None and us_10y_change_bp >= rate_jump:
        score -= rate_pen
        reasons.append(f"미 10년물 +{us_10y_change_bp:.0f}bp → 역풍")

    score = round(score, 3)

    if extreme == "vix_panic":
        signal = "risk_off"
    elif score >= on_th:
        signal = "risk_on"
    elif score <= off_th:
        signal = "risk_off"
    else:
        signal = "neutral"

    reasons.append(f"종합 signal_score={score} → {_RISK_KR.get(signal, signal)}")
    return signal, score, extreme, reasons


# ---------------------------------------------------------------------------
# fetch → snapshot (get_indices 재사용)
# ---------------------------------------------------------------------------


def _idx(raw: dict[str, Any], name: str, key: str) -> float | None:
    """get_indices 결과에서 한 지표의 한 키 추출 (error/결측 → None)."""
    block = raw.get(name) or {}
    if "error" in block:
        return None
    val = block.get(key)
    try:
        return float(val) if val is not None else None
    except (TypeError, ValueError):
        return None


def _snapshot_from_indices(date_str: str, raw: dict[str, Any]) -> USMacroSnapshot:
    """get_indices 결과 dict → USMacroSnapshot (분류 포함)."""
    nasdaq = _idx(raw, "nasdaq", "change_pct")
    sp500 = _idx(raw, "sp500", "change_pct")
    sox = _idx(raw, "philly_semi", "change_pct")
    vix = _idx(raw, "vix", "price")
    vix_chg = _idx(raw, "vix", "change_pct")
    dxy = _idx(raw, "dxy", "price")
    dxy_chg = _idx(raw, "dxy", "change_pct")
    us10 = _idx(raw, "us_10y", "price")
    us10_chg_raw = _idx(raw, "us_10y", "change")   # 수익률 포인트 변화
    us10_bp = round(us10_chg_raw * 100, 1) if us10_chg_raw is not None else None  # 포인트 → bp
    gold = _idx(raw, "gold", "change_pct")
    # 야간자산 (INFRA-MARKET-ASSETS-002) — 수집·영속만, classify 미반영.
    wti = _idx(raw, "wti", "change_pct")
    brent = _idx(raw, "brent", "change_pct")
    nq_fut = _idx(raw, "nq_futures", "change_pct")
    es_fut = _idx(raw, "es_futures", "change_pct")

    signal, score, extreme, reasons = classify_us_risk(
        nasdaq_change_pct=nasdaq,
        sp500_change_pct=sp500,
        sox_change_pct=sox,
        vix=vix,
        dxy_change_pct=dxy_chg,
        us_10y_change_bp=us10_bp,
    )

    success = sum(1 for v in raw.values() if isinstance(v, dict) and "error" not in v)
    source = "computed" if success else "unavailable"
    if source == "unavailable":
        reasons = ["미장 데이터 fetch 실패 (yfinance 미설치/네트워크) — 중립 폴백"]
        signal, score, extreme = "neutral", 0.0, "none"

    return USMacroSnapshot(
        date=date_str,
        nasdaq_change_pct=nasdaq,
        sp500_change_pct=sp500,
        sox_change_pct=sox,
        vix=vix,
        vix_change_pct=vix_chg,
        dxy=dxy,
        dxy_change_pct=dxy_chg,
        us_10y=us10,
        us_10y_change_bp=us10_bp,
        gold_change_pct=gold,
        risk_signal=signal,
        signal_score=score,
        extreme=extreme,
        reasons=reasons,
        source=source,
        wti_change_pct=wti,
        brent_change_pct=brent,
        nq_futures_change_pct=nq_fut,
        es_futures_change_pct=es_fut,
    )


# ---------------------------------------------------------------------------
# DB layer — us_macro_snapshot
# ---------------------------------------------------------------------------


def _get_today_us_macro(date_str: str) -> USMacroSnapshot | None:
    """오늘 row 가 있으면 USMacroSnapshot 복원, 없으면 None."""
    db = get_db()
    row = db.fetch_one(
        "SELECT * FROM us_macro_snapshot WHERE date = ?",
        (date_str,),
    )
    if row is None:
        return None
    import json as _json

    def _f(key: str) -> float | None:
        v = row[key]
        return float(v) if v is not None else None

    return USMacroSnapshot(
        date=row["date"],
        nasdaq_change_pct=_f("nasdaq_change_pct"),
        sp500_change_pct=_f("sp500_change_pct"),
        sox_change_pct=_f("sox_change_pct"),
        vix=_f("vix"),
        vix_change_pct=_f("vix_change_pct"),
        dxy=_f("dxy"),
        dxy_change_pct=_f("dxy_change_pct"),
        us_10y=_f("us_10y"),
        us_10y_change_bp=_f("us_10y_change_bp"),
        gold_change_pct=_f("gold_change_pct"),
        risk_signal=row["risk_signal"] or "neutral",
        signal_score=float(row["signal_score"]) if row["signal_score"] is not None else 0.0,
        extreme=row["extreme"] or "none",
        reasons=_json.loads(row["reasons_json"]) if row["reasons_json"] else [],
        source="db",
        wti_change_pct=_f("wti_change_pct"),
        brent_change_pct=_f("brent_change_pct"),
        nq_futures_change_pct=_f("nq_futures_change_pct"),
        es_futures_change_pct=_f("es_futures_change_pct"),
    )


def upsert_us_macro(snap: USMacroSnapshot) -> None:
    """us_macro_snapshot ON CONFLICT REPLACE 멱등 upsert (date PK)."""
    import json as _json

    db = get_db()
    with db.connect() as conn:
        conn.execute(
            "INSERT INTO us_macro_snapshot "
            "(date, nasdaq_change_pct, sp500_change_pct, sox_change_pct, "
            " vix, vix_change_pct, dxy, dxy_change_pct, us_10y, us_10y_change_bp, "
            " gold_change_pct, risk_signal, signal_score, extreme, reasons_json, source, "
            " wti_change_pct, brent_change_pct, nq_futures_change_pct, es_futures_change_pct) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(date) DO UPDATE SET "
            " nasdaq_change_pct=excluded.nasdaq_change_pct, "
            " sp500_change_pct=excluded.sp500_change_pct, "
            " sox_change_pct=excluded.sox_change_pct, "
            " vix=excluded.vix, vix_change_pct=excluded.vix_change_pct, "
            " dxy=excluded.dxy, dxy_change_pct=excluded.dxy_change_pct, "
            " us_10y=excluded.us_10y, us_10y_change_bp=excluded.us_10y_change_bp, "
            " gold_change_pct=excluded.gold_change_pct, "
            " risk_signal=excluded.risk_signal, signal_score=excluded.signal_score, "
            " extreme=excluded.extreme, reasons_json=excluded.reasons_json, "
            " source=excluded.source, "
            " wti_change_pct=excluded.wti_change_pct, "
            " brent_change_pct=excluded.brent_change_pct, "
            " nq_futures_change_pct=excluded.nq_futures_change_pct, "
            " es_futures_change_pct=excluded.es_futures_change_pct",
            (
                snap.date,
                snap.nasdaq_change_pct,
                snap.sp500_change_pct,
                snap.sox_change_pct,
                snap.vix,
                snap.vix_change_pct,
                snap.dxy,
                snap.dxy_change_pct,
                snap.us_10y,
                snap.us_10y_change_bp,
                snap.gold_change_pct,
                snap.risk_signal,
                snap.signal_score,
                snap.extreme,
                _json.dumps(snap.reasons, ensure_ascii=False),
                "computed",
                snap.wti_change_pct,
                snap.brent_change_pct,
                snap.nq_futures_change_pct,
                snap.es_futures_change_pct,
            ),
        )


def _today_kst_str() -> str:
    return datetime.now(_KST).strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Async public API
# ---------------------------------------------------------------------------


async def compute_us_macro(*, force_refresh: bool = False) -> USMacroSnapshot:
    """미장 야간 매크로 스냅샷 — DB-first hybrid (market_macro.compute_market_macro mirror).

    Args:
        force_refresh: True 면 DB hit 무시하고 재fetch.

    Returns:
        USMacroSnapshot. yfinance 실패 시도 source="unavailable" 부분 발행(graceful).
    """
    today = _today_kst_str()

    if not force_refresh:
        cached = _get_today_us_macro(today)
        if cached is not None:
            return cached

    try:
        from connectors.yfinance.client import get_indices

        raw = await get_indices(names=_FETCH_NAMES)
    except Exception as e:  # noqa: BLE001 — capability 폴백 (미설치/네트워크)
        log.warning("us_macro_fetch_failed", error=str(e))
        raw = {}

    snap = _snapshot_from_indices(today, raw)

    try:
        upsert_us_macro(snap)
    except Exception as e:  # pragma: no cover
        log.warning("us_macro_upsert_failed", error=str(e))

    return snap


def get_today_us_macro(date_str: str | None = None) -> USMacroSnapshot | None:
    """오늘 us_macro_snapshot row → USMacroSnapshot(source='db'). 없으면 None (계산·fetch 0)."""
    try:
        return _get_today_us_macro(date_str or _today_kst_str())
    except Exception:  # noqa: BLE001 — DB 부재 환경에서도 막지 않음
        return None


async def refresh_us_macro() -> dict[str, Any]:
    """미장 매크로 일간 refresh — cron 진입점 (snapshot_macro 허브 합류).

    Returns:
        {"date", "risk_signal", "signal_score", "extreme", "source"} 또는 {"error": ...}
    """
    try:
        snap = await compute_us_macro(force_refresh=True)
        return {
            "date": snap.date,
            "risk_signal": snap.risk_signal,
            "signal_score": snap.signal_score,
            "extreme": snap.extreme,
            "source": snap.source,
        }
    except Exception as e:  # noqa: BLE001
        log.exception("refresh_us_macro_failed", error=str(e))
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Render / 흡수 helper (MarketView [7] 미장 야간 라인 + 토큰)
# ---------------------------------------------------------------------------


def us_one_liner_token(snap: USMacroSnapshot | None) -> str:
    """one_liner 미장 토큰 — risk_off/risk_on 만 노출, neutral/unavailable 생략(F2 정신)."""
    if snap is None or snap.source == "unavailable":
        return ""
    if snap.extreme == "vix_panic" or snap.risk_signal == "risk_off":
        return " · 미장 위험회피"
    if snap.risk_signal == "risk_on":
        return " · 미장 위험선호"
    return ""


def us_macro_reason(snap: USMacroSnapshot | None) -> str | None:
    """MarketView.reasons 1줄 (시장관 근거 흡수). neutral/unavailable → None."""
    if snap is None or snap.source == "unavailable":
        return None
    if snap.risk_signal == "neutral" and snap.extreme == "none":
        return None
    bits: list[str] = [f"미장 야간 {_RISK_KR.get(snap.risk_signal, snap.risk_signal)}"]
    if snap.sox_change_pct is not None:
        bits.append(f"필반 {snap.sox_change_pct:+.2f}%")
    if snap.vix is not None:
        bits.append(f"VIX {snap.vix:.1f}")
    suffix = " — 진입 자세 강등" if snap.risk_signal == "risk_off" else ""
    return ", ".join(bits) + suffix


def render_us_macro_md(snap: USMacroSnapshot) -> str:
    """`미장 야간` 라인 — MarketView [7] 블록 하위 주입용 (market_state_analyzer 해석)."""
    if snap.source == "unavailable":
        return "**미장 야간**: 데이터 없음 (yfinance 미가용)"

    def _pct(v: float | None) -> str:
        return f"{v:+.2f}%" if v is not None else "—"

    header = (
        f"**미장 야간** ({_RISK_KR.get(snap.risk_signal, snap.risk_signal)}, `{snap.risk_signal}`"
        + (f", ⚠{snap.extreme}" if snap.extreme != "none" else "")
        + "):"
    )
    bits = [f"나스닥 {_pct(snap.nasdaq_change_pct)}", f"필반 {_pct(snap.sox_change_pct)}"]
    if snap.vix is not None:
        bits.append(f"VIX {snap.vix:.1f}")
    if snap.dxy_change_pct is not None:
        bits.append(f"달러 {_pct(snap.dxy_change_pct)}")
    if snap.us_10y_change_bp is not None:
        bits.append(f"미10년물 {snap.us_10y_change_bp:+.0f}bp")
    if snap.gold_change_pct is not None:
        bits.append(f"금 {_pct(snap.gold_change_pct)}")
    line = f"{header} " + " · ".join(bits)

    # 야간자산 별도 줄 — 한글 라벨로 현물 지수와 구분 (값 있는 것만, 전부 결측이면 줄 생략).
    asset_bits: list[str] = []
    for key, label in OVERNIGHT_ASSET_LABELS_KR.items():
        val = getattr(snap, f"{key}_change_pct", None)
        if val is not None:
            asset_bits.append(f"{label} {_pct(val)}")
    if asset_bits:
        line += "\n**야간자산** (전일 대비): " + " · ".join(asset_bits)
    return line


def overnight_assets_payload(snap: USMacroSnapshot) -> list[dict[str, Any]]:
    """야간자산 화면/알림용 payload — 한글 라벨 + 값 (웹앱·텔레그램 공통 소스).

    현물 지수와 혼동 없도록 label_kr 동봉. 미수집(None)도 포함(화면이 '—' 표시).
    """
    return [
        {
            "key": key,
            "label_kr": label,
            "change_pct": getattr(snap, f"{key}_change_pct", None),
        }
        for key, label in OVERNIGHT_ASSET_LABELS_KR.items()
    ]


def us_macro_metadata(snap: USMacroSnapshot) -> dict[str, Any]:
    """run_analyst metadata 노출용 미장 매크로 요약."""
    return {
        "us_macro": {
            "date": snap.date,
            "risk_signal": snap.risk_signal,
            "signal_score": snap.signal_score,
            "extreme": snap.extreme,
            "sox_change_pct": snap.sox_change_pct,
            "vix": snap.vix,
            "source": snap.source,
            "overnight_assets": overnight_assets_payload(snap),
        }
    }
