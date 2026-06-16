"""관심종목 리스트 큐레이션 — 잡주 제외(결정론 floor) + 정배열 위계.

raw 거래대금/거래량 상위에서 "매매 가능성 있는" 종목만 남긴다 (LLM 0, 전부 결정론):
  - 거래대금 floor (동전주·초소형 제외) · 등락 ≤20% (상한가/이상치 제외) · 시총 floor (best-effort)
  - **정배열 위계** (현재가>60·120일선, ma20≥ma60) = "월/주봉 죽은 차트(잡주)" 제외 proxy
    — compute_indicators 재사용(이미 로드되는 일봉, 비용 0). 파동(wave_alive)은 SLOT 업그레이드.
리스트별 차등 floor (거래대금=대형 중장기 / 거래량양봉=중소형 모멘텀 허용). 임계 전부 config SLOT.

순수 게이트(passes_quality_floor)는 단위 테스트. I/O 래퍼(curate_groups)는 chart_ohlcv 만 read.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from core.logging import get_logger

log = get_logger(__name__)


@dataclass
class CurationConfig:
    """리스트별 잡주 floor + 정배열 (config/screening.yaml `curation`, 기본값 = 여기). 전부 SLOT."""

    enabled: bool = True
    max_change_pct: float | None = None   # |등락률| 상한(초과 시 제외). None = 상한가 포함(사용자 결정 2026-06-16)
    require_ma_alignment: bool = True     # 정배열 위계 게이트 (죽은 차트 제외)
    # 거래대금 상위 (trade_value) — 대형 중장기.
    tv_min_trade_amount: float = 1.0e10   # 100억
    tv_min_market_cap: float = 5.0e11     # 5000억
    # 거래량 양봉 (volume_bull) — 중소형 모멘텀 허용.
    vb_min_trade_amount: float = 1.0e10   # 100억
    vb_min_market_cap: float = 1.0e11     # 1000억


_BOOL_FIELDS = frozenset({"enabled", "require_ma_alignment"})


def curation_config_from_dict(raw: dict[str, Any] | None) -> CurationConfig:
    """yaml `curation` → CurationConfig (graceful — 미지정/오타입은 default)."""
    cfg = CurationConfig()
    if not isinstance(raw, dict):
        return cfg
    for fname in CurationConfig.__dataclass_fields__:
        if fname not in raw:
            continue
        try:
            setattr(cfg, fname, bool(raw[fname]) if fname in _BOOL_FIELDS else float(raw[fname]))
        except (TypeError, ValueError):
            continue
    return cfg


def _floors(list_type: str, cfg: CurationConfig) -> tuple[float, float]:
    if list_type == "volume_bull":
        return cfg.vb_min_trade_amount, cfg.vb_min_market_cap
    return cfg.tv_min_trade_amount, cfg.tv_min_market_cap


def passes_quality_floor(
    *,
    list_type: str,
    change_pct: float | None,
    trade_amount: float | None,
    market_cap: float | None,
    ma_aligned: bool | None,
    cfg: CurationConfig,
) -> bool:
    """순수 — 잡주 floor + 정배열 통과 여부.

    결측 처리(보수적이되 과필터 회피): market_cap None → 시총 floor skip(best-effort).
    ma_aligned False(죽은 차트) → 제외 / None(미산출) → 통과(universe 는 보통 OHLCV 있음).
    """
    min_amt, min_cap = _floors(list_type, cfg)
    if cfg.max_change_pct is not None and change_pct is not None and abs(change_pct) > cfg.max_change_pct:
        return False  # max_change_pct=None(기본) 이면 상한가도 포함
    if trade_amount is not None and trade_amount < min_amt:
        return False
    if market_cap is not None and market_cap > 0 and market_cap < min_cap:
        return False
    if cfg.require_ma_alignment and ma_aligned is False:
        return False
    return True


def _chart_summary(ohlcv: Any) -> tuple[bool | None, str]:
    """(정배열 여부, 컨셉) — compute_indicators 1회 재사용. 산출 불가 시 (None, 'unknown').

    컨셉 분류(주도주/바닥주 중구난방 해소):
      - base    바닥·소외: 현재가 ≤ 60일선 (중기 추세 아래)
      - pullback 눌림     : 60일선 위 + 현재가 < 20일선 (주도주 단기 조정)
      - leader  주도주    : 추세 위 (현재가 > 20·60일선)
    정배열 = 현재가>60·120일선 ∧ ma20≥ma60 (잡주 floor 용).
    """
    if ohlcv is None or len(ohlcv) == 0:
        return None, "unknown"
    try:
        from collectors.charts import compute_indicators

        ind = compute_indicators(ohlcv)
        close = ind.get("current_close")
        dma = ind.get("daily_ma", {})
        ma20, ma60, ma120 = dma.get("ma20"), dma.get("ma60"), dma.get("ma120")
        if close is None or ma60 is None:
            return None, "unknown"
        aligned = close > ma60
        if ma120 is not None:
            aligned = aligned and close > ma120
        if ma20 is not None:
            aligned = aligned and ma20 >= ma60
        if close <= ma60:
            concept = "base"
        elif ma20 is not None and close < ma20:
            concept = "pullback"
        else:
            concept = "leader"
        return bool(aligned), concept
    except Exception:  # noqa: BLE001
        return None, "unknown"


def _curate_list(
    items: list[dict[str, Any]], list_type: str, cfg: CurationConfig
) -> list[dict[str, Any]]:
    from collectors.charts import load_ohlcv_from_db

    out: list[dict[str, Any]] = []
    for it in items:
        tk = (it.get("ticker") or "").strip()
        if not tk:
            continue
        aligned, concept = _chart_summary(load_ohlcv_from_db(tk, limit=200))
        if passes_quality_floor(
            list_type=list_type,
            change_pct=it.get("change_pct"),
            trade_amount=it.get("trade_amount"),
            market_cap=it.get("market_cap"),  # volume_bull 장중 stock_price 에서 부착(없으면 skip)
            ma_aligned=aligned,
            cfg=cfg,
        ):
            it["concept"] = concept   # 차트 컨셉 분류 부착 → persist 저장
            out.append(it)
    return out


def curate_groups(
    grouped: dict[str, Any], *, list_type: str, cfg: CurationConfig | None = None
) -> dict[str, Any]:
    """{"kospi":[...],"kosdaq":[...]} → 잡주 floor+정배열 통과분만 (persist 전 적용).

    시총은 항목의 market_cap(volume_bull 장중 stock_price 부착) 사용 — 없으면 시총 floor skip(best-effort).
    """
    cfg = cfg or CurationConfig()
    if not cfg.enabled or not isinstance(grouped, dict):
        return grouped
    before = sum(len(grouped.get(g) or []) for g in ("kospi", "kosdaq"))
    out = {g: _curate_list(grouped.get(g) or [], list_type, cfg) for g in ("kospi", "kosdaq")}
    after = sum(len(out[g]) for g in ("kospi", "kosdaq"))
    log.info("universe_curated", list_type=list_type, before=before, after=after)
    return out
