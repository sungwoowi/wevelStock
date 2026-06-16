"""종목 스크리닝 RS + 과열도 orchestrator (SCREEN-RS-EXTENSION-001).

stock_picker 의 S-Score `rs` 축 + buy_score `L`(Leader) 축의 결정론 base.
후보 풀 각 종목의 일봉(chart_ohlcv)에서 60일 수익률·MA20·ADR 을 계산하고,
오닐식 상대강도(풀 내 백분위) + 과열도(ADR 정규화) + regime 가중 합성으로 랭킹한다.

패턴 = collectors/sector_rs.py 1:1 mirror (lazy compute, DB 저장 X — 호출 시점 read 만).
config = config/screening.yaml (하드코딩 금지, watchdog hot reload). 로더는 본 모듈 내부.

cutoff_date 지정 시 그 시점까지 OHLCV 만 read → 과거 임의 시점 스크리닝 재현 (백테스팅 친화,
feedback_backtest_essence). 모든 scoring 함수는 순수 (collectors.scoring).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from collectors.charts import load_ohlcv_from_db
from collectors.scoring import extension_score, screening_score, stock_rs_score
from core.logging import get_logger

log = get_logger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[1]
SCREENING_PATH = REPO_ROOT / "config" / "screening.yaml"

_CONFIG_CACHE: dict[str, Any] | None = None

_DEFAULTS: dict[str, Any] = {
    "rs_window": 60,
    "k": 1.0,
    "k_below": 1.0,
    "below_deadband_adr": 1.0,
    "adr_window": 14,
    "regime_weights": {},
}


# ---------------------------------------------------------------------------
# config 로더 (score_inputs_config.py 패턴 mirror — 모듈 캐시 + reload)
# ---------------------------------------------------------------------------


def _load_screening_config() -> dict[str, Any]:
    """config/screening.yaml 로드 (캐시). 부재·파싱 실패 시 default fallback."""
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        if not SCREENING_PATH.exists():
            log.warning("screening_config_missing", path=str(SCREENING_PATH))
            _CONFIG_CACHE = dict(_DEFAULTS)
        else:
            try:
                loaded = yaml.safe_load(SCREENING_PATH.read_text(encoding="utf-8")) or {}
                _CONFIG_CACHE = {**_DEFAULTS, **loaded}
            except Exception as e:  # noqa: BLE001
                log.warning("screening_config_load_failed", error=str(e))
                _CONFIG_CACHE = dict(_DEFAULTS)
    return _CONFIG_CACHE


def reload_screening_config() -> None:
    """테스트/hot reload — 캐시 클리어."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None


def get_rs_window() -> int:
    try:
        return int(_load_screening_config().get("rs_window", 60))
    except (TypeError, ValueError):
        return 60


def get_k() -> float:
    try:
        return float(_load_screening_config().get("k", 1.0))
    except (TypeError, ValueError):
        return 1.0


def get_k_below() -> float:
    """이탈(ma20 아래) 감점 스케일 계수 (SCREEN-RS C). 부재 시 1.0."""
    try:
        return float(_load_screening_config().get("k_below", 1.0))
    except (TypeError, ValueError):
        return 1.0


def get_below_deadband_adr() -> float:
    """ma20 아래 완충대 (ADR 단위, SCREEN-RS C). 부재 시 1.0."""
    try:
        return float(_load_screening_config().get("below_deadband_adr", 1.0))
    except (TypeError, ValueError):
        return 1.0


def get_adr_window() -> int:
    try:
        return int(_load_screening_config().get("adr_window", 14))
    except (TypeError, ValueError):
        return 14


def get_universe_limits() -> tuple[int, int]:
    """universe 백필 시 거래대금 상위 (kospi_limit, kosdaq_limit). 부재 시 (30, 20)."""
    cfg = _load_screening_config().get("universe") or {}
    try:
        return int(cfg.get("kospi_limit", 30)), int(cfg.get("kosdaq_limit", 20))
    except (TypeError, ValueError):
        return 30, 20


def get_universe_max_tickers() -> int:
    """일일 chart_ohlcv refresh 상한 (rate limit 보호). 부재 시 200."""
    cfg = _load_screening_config().get("universe") or {}
    try:
        return int(cfg.get("max_tickers", 200))
    except (TypeError, ValueError):
        return 200


def get_signal_min_score() -> float:
    """자동 권고 funnel Stage 0 결정론 컷 임계 (AUTO-SIGNAL-GENERATION-001).

    screening_score(0~10) 가 이 값 이상인 종목만 Stage 1(전략가) 대상. 부재 시 5.0(중앙값).
    """
    cfg = _load_screening_config().get("signal_gate") or {}
    try:
        return float(cfg.get("min_score", 5.0))
    except (TypeError, ValueError):
        return 5.0


def get_signal_max_candidates() -> int:
    """Stage 0 통과 종목 상한 (LLM 비용·rate limit 보호). 부재 시 20. 0/음수 = 무제한."""
    cfg = _load_screening_config().get("signal_gate") or {}
    try:
        return int(cfg.get("max_candidates", 20))
    except (TypeError, ValueError):
        return 20


def get_auto_signal_enabled() -> bool:
    """자동 권고 생성 cron 마스터 스위치 (AUTO-SIGNAL-GENERATION-001 M3). 부재 시 True.

    False 면 4 cadence 잡이 모두 no-op — 비용 부담 시 코드 변경 없이 전체 OFF (watchdog).
    """
    cfg = _load_screening_config().get("signal_gate") or {}
    return bool(cfg.get("auto_run_enabled", True))


def get_signal_concurrency() -> int:
    """자동 권고 종목 병렬 처리 동시성 (AUTO-SIGNAL M6). 부재 시 3 (저사양 보수값).

    asyncio 코루틴 동시성(스레드·프로세스 X) — CPU·RAM 부하 거의 없음(I/O 대기 겹침).
    제약은 KIS rate-limit. 8GB·서버 동시 가동 환경 고려 기본 3. 1 = 순차. config 로 조절.
    """
    cfg = _load_screening_config().get("signal_gate") or {}
    try:
        n = int(cfg.get("concurrency", 3))
        return n if n >= 1 else 1
    except (TypeError, ValueError):
        return 3


def get_signal_strategist_retries() -> int:
    """전략가 호출 transient 실패(503·no_yaml) 재시도 횟수. 부재 시 1 (총 2회 시도)."""
    cfg = _load_screening_config().get("signal_gate") or {}
    try:
        n = int(cfg.get("strategist_retries", 1))
        return max(0, n)
    except (TypeError, ValueError):
        return 1


def get_band_gate_enabled() -> bool:
    """의사결정 밴드 게이트 ON/OFF (자동 권고 비용 제어). 부재 시 True.

    True 면 밴드 지문이 직전 cadence 와 같은 종목은 전략가 재호출 스킵(직전 verdict 유지).
    """
    cfg = _load_screening_config().get("signal_gate") or {}
    return bool(cfg.get("band_gate_enabled", True))


def get_band_score_width() -> float:
    """점수 밴드 폭 (F/T/S/buy 양자화 단위). 부재 시 1.0 (정수 버킷).

    클수록 둔감(재호출 적음·비용↓), 작을수록 민감. 경계 진동은 hysteresis SLOT.
    """
    cfg = _load_screening_config().get("signal_gate") or {}
    try:
        w = float(cfg.get("band_score_width", 1.0))
        return w if w > 0 else 1.0
    except (TypeError, ValueError):
        return 1.0


def load_posture_config() -> Any:
    """차등 변조 임계 (config/screening.yaml `alpha_posture`) → PostureConfig.

    BRAIN-ALPHA-FLEXIBILITY-001 M1 — funnel(M3)이 derive_alpha_posture 에 주입.
    섹션 부재/오타입은 posture_config_from_dict 가 graceful default 처리. watchdog hot reload.
    """
    from core.signal.alpha_posture import posture_config_from_dict

    raw = _load_screening_config().get("alpha_posture")
    return posture_config_from_dict(raw if isinstance(raw, dict) else {})


def load_trade_plan_config() -> Any:
    """결정론 가격대 메뉴 임계 (config/screening.yaml `trade_plan`) → TradePlanConfig.

    TRADE-PLAN-LIFECYCLE-001 B-MS1 — funnel 이 build_trade_plan_menu 에 주입.
    섹션 부재/오타입은 trade_plan_config_from_dict 가 graceful default 처리. watchdog hot reload.
    """
    from core.signal.trade_plan_menu import trade_plan_config_from_dict

    raw = _load_screening_config().get("trade_plan")
    return trade_plan_config_from_dict(raw if isinstance(raw, dict) else {})


def load_curation_config() -> Any:
    """관심종목 잡주 floor + 정배열 임계 (config/screening.yaml `curation`) → CurationConfig.

    거래대금/거래량양봉 리스트 persist 전 curate_groups 에 주입. graceful default. watchdog hot reload.
    """
    from collectors.universe_curation import curation_config_from_dict

    raw = _load_screening_config().get("curation")
    return curation_config_from_dict(raw if isinstance(raw, dict) else {})


async def fetch_universe_tickers(kis: Any | None = None) -> list[str]:
    """거래대금 상위(leading) 종목 ticker 평탄화 — universe 백필 입력.

    `kr_leading_stocks.fetch_kr_leading_stocks` 재사용 (KIS 3콜). config universe limit 적용.
    중복 제거(순서 보존) + 빈 ticker 제외. KIS 실패 시 호출부(refresh_all_tickers)가 graceful 처리.
    """
    from collectors.kr_leading_stocks import fetch_kr_leading_stocks

    kospi_limit, kosdaq_limit = get_universe_limits()
    data = await fetch_kr_leading_stocks(
        kis, kospi_limit=kospi_limit, kosdaq_limit=kosdaq_limit
    )
    # 거래대금 상위 멤버십 영속 — 잡주 floor+정배열 큐레이션 후(관심종목 페이지용). 멱등, 실패해도 universe 무영향.
    # screening universe(반환 tickers)는 *전체* 유지 — 큐레이션은 관심종목 리스트에만(screening 동작 불변).
    try:
        from collectors.universe_curation import curate_groups
        from collectors.universe_membership import persist_universe_membership

        curated = curate_groups(data, list_type="trade_value", cfg=load_curation_config())
        persist_universe_membership(curated)
    except Exception as e:  # noqa: BLE001
        log.warning("universe_membership_persist_failed", error=str(e))
    tickers = [i.get("ticker", "") for i in data.get("kospi", [])]
    tickers += [i.get("ticker", "") for i in data.get("kosdaq", [])]
    return [t for t in dict.fromkeys(tickers) if t]


def get_regime_thresholds() -> dict[str, float]:
    """시장 체제 분류 임계 (market_macro.classify_market_regime DI). 부재 시 빈 dict→함수 default."""
    raw = _load_screening_config().get("regime_thresholds") or {}
    out: dict[str, float] = {}
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                out[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
    return out


def get_regime_weights() -> dict[str, dict[str, float]]:
    raw = _load_screening_config().get("regime_weights") or {}
    out: dict[str, dict[str, float]] = {}
    if isinstance(raw, dict):
        for regime, w in raw.items():
            if isinstance(w, dict):
                try:
                    out[str(regime)] = {
                        "w_rs": float(w.get("w_rs", 0.5)),
                        "w_ext": float(w.get("w_ext", 0.5)),
                    }
                except (TypeError, ValueError):
                    continue
    return out


# ---------------------------------------------------------------------------
# 종목 지표 산출 (순수 — df → return_60d / price / ma20 / adr)
# ---------------------------------------------------------------------------


def _slice_to_cutoff(df: pd.DataFrame, cutoff_date: str | None) -> pd.DataFrame:
    """cutoff_date(YYYY-MM-DD) 이하 봉만. 빈/미지정 시 원본."""
    if df is None or df.empty or not cutoff_date:
        return df
    try:
        return df[df.index <= pd.Timestamp(cutoff_date)]
    except Exception:  # noqa: BLE001
        return df


def compute_stock_metrics(
    df: pd.DataFrame,
    *,
    rs_window: int = 60,
    adr_window: int = 14,
) -> dict[str, float | None]:
    """일봉 df → {return_60d, price, ma20, adr}. 데이터 부족 시 해당 키 None.

    순수 (df 입력만). return_60d 는 최근 rs_window 봉 close 수익률 %,
    ma20 = 최근 20봉 close 평균, adr = 최근 adr_window 봉 (high-low)/close 평균.
    """
    out: dict[str, float | None] = {
        "return_60d": None,
        "price": None,
        "ma20": None,
        "adr": None,
    }
    if df is None or df.empty or "close" not in df.columns:
        return out

    close = df["close"]
    out["price"] = float(close.iloc[-1])

    # 60일 수익률 (%)
    if len(close) >= rs_window:
        start = close.iloc[-rs_window]
        if start is not None and start > 0:
            out["return_60d"] = float((close.iloc[-1] - start) / start * 100)

    # MA20
    if len(close) >= 20:
        out["ma20"] = float(close.iloc[-20:].mean())

    # ADR = mean((high - low) / close) 최근 adr_window 봉
    if {"high", "low"}.issubset(df.columns) and len(df) >= 1:
        tail = df.iloc[-adr_window:]
        rng = (tail["high"] - tail["low"]) / tail["close"]
        rng = rng.replace([float("inf"), float("-inf")], pd.NA).dropna()
        if len(rng) > 0:
            out["adr"] = float(rng.mean())

    return out


# ---------------------------------------------------------------------------
# orchestrator — rank_candidates (screening-rank-v1)
# ---------------------------------------------------------------------------


def rank_candidates(
    tickers: list[str],
    regime: str | None,
    *,
    cutoff_date: str | None = None,
    k_override: float | None = None,
    k_below_override: float | None = None,
    deadband_override: float | None = None,
) -> list[dict[str, Any]]:
    """후보 풀 종목별 RS + 과열도 + regime 가중 합성 → 랭킹 (screening-rank-v1).

    Args:
        tickers: 스크리닝 대상 universe (호출부 제공).
        regime: 시장 체제 6단계 중 하나. None/미정의 → 균등 가중 fallback.
        cutoff_date: 지정 시 그 시점까지 OHLCV 만 (백테스팅 재현).
        k_override: 지정 시 config `k`(과열) 대신 이 값으로 채점 (진단/캘리브레이션
            스윕 전용 — config 편집 없이 한 프로세스에서 여러 값 비교). production 은 None.
        k_below_override: 지정 시 config `k_below`(이탈) 대신 이 값. 스윕 전용.
        deadband_override: 지정 시 config `below_deadband_adr` 대신 이 값. 스윕 전용.

    Returns:
        종목별 dict 리스트. 각 = {ticker, rs_score, extension_score, screening_score,
        rank, reason, extension_pct, adr, normalized}. screening_score 내림차순 정렬
        (산출 가능 종목 우선), 랭킹 불가 종목(60일 데이터 부족)은 rank=None + reason 으로
        뒤에. extension_pct/adr/normalized 는 과열도 포화 원인 진단용 raw 값. DB 저장 X.
    """
    rs_window = get_rs_window()
    adr_window = get_adr_window()
    k = k_override if k_override is not None else get_k()
    k_below = k_below_override if k_below_override is not None else get_k_below()
    deadband = deadband_override if deadband_override is not None else get_below_deadband_adr()
    weights = get_regime_weights()
    regime_key = regime or ""

    # 1) 각 종목 지표 산출
    metrics: dict[str, dict[str, float | None]] = {}
    for ticker in tickers:
        df = load_ohlcv_from_db(ticker, limit=rs_window + 10)
        df = _slice_to_cutoff(df, cutoff_date)
        metrics[ticker] = compute_stock_metrics(
            df, rs_window=rs_window, adr_window=adr_window
        )

    # 2) 후보 풀 60일 수익률 (rs 백분위 정규화 입력 — 자신 포함)
    pool_returns = [
        m["return_60d"] for m in metrics.values() if m["return_60d"] is not None
    ]

    ranked: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []

    for ticker in tickers:
        m = metrics[ticker]
        ret = m["return_60d"]
        if ret is None:
            excluded.append({
                "ticker": ticker,
                "rs_score": None,
                "extension_score": None,
                "screening_score": None,
                "rank": None,
                "reason": "60일 데이터 부족 (랭킹 제외)",
                "extension_pct": None,
                "adr": None,
                "normalized": None,
            })
            continue

        rs = stock_rs_score(ret, pool_returns)
        ext = extension_score(
            m["price"], m["ma20"], m["adr"],
            k=k, k_below=k_below, below_deadband_adr=deadband,
        )
        ext_axis = ext if ext is not None else 5.0
        score = screening_score(rs, ext_axis, regime_key, weights)
        reason = "" if ext is not None else "과열도 미산출 → 중립 5.0"
        # 과열도 포화 원인 진단용 raw — ma20 대비 이격(%) + ADR 정규화 값.
        # ma20 아래(ext_pct ≤ 0)면 공식상 extension_score 가 무조건 10 clamp → k 무관.
        price, ma20, adr = m["price"], m["ma20"], m["adr"]
        ext_pct: float | None = None
        normalized: float | None = None
        if ma20 is not None and ma20 > 0 and price is not None:
            ext_pct = (price - ma20) / ma20 * 100.0
            if adr is not None and adr > 0:
                normalized = (price - ma20) / ma20 / adr
        ranked.append({
            "ticker": ticker,
            "rs_score": rs,
            "extension_score": ext,
            "screening_score": score,
            "rank": None,  # 정렬 후 부여
            "reason": reason,
            "extension_pct": round(ext_pct, 4) if ext_pct is not None else None,
            "adr": round(adr, 6) if adr is not None else None,
            "normalized": round(normalized, 4) if normalized is not None else None,
        })

    # 3) screening_score 내림차순 정렬 + rank 부여 (동점 시 ticker 안정 정렬)
    ranked.sort(key=lambda r: (-r["screening_score"], r["ticker"]))
    for idx, row in enumerate(ranked, start=1):
        row["rank"] = idx

    return ranked + excluded


# ---------------------------------------------------------------------------
# 발굴 셔틀리스트 렌더 (screening-shortlist-v1) — 종목 미지정 추천 질의용
# ---------------------------------------------------------------------------


_TRACK_LABEL = {"track_a": "중장기 주도주", "track_b": "단기 트레이딩"}


def render_screening_shortlist_md(
    ranked: list[dict[str, Any]],
    names: dict[str, str] | None = None,
    *,
    top_n: int = 5,
    track: str | None = None,
    regime: str | None = None,
) -> str:
    """rank_candidates 결과 → 발굴 후보 셔틀리스트 md (stock_picker 컨텍스트 주입용).

    결정론 랭킹(권위)이 상위 후보를 제시하고, stock_picker LLM 이 큐레이션·근거를 발행한다.
    rank=None(60일 데이터 부족) 종목은 제외. 산출 가능 후보 0개면 안내 문구.
    """
    names = names or {}
    track_label = _TRACK_LABEL.get(track or "", "종목 발굴")
    rankable = [r for r in ranked if r.get("rank") is not None
                and r.get("screening_score") is not None]
    top = rankable[:max(1, top_n)]

    lines: list[str] = []
    lines.append(f"## [발굴] 스크리닝 랭킹 상위 후보 ({track_label})")
    lines.append("")
    regime_part = f" · 시장 체제 `{regime}`" if regime else ""
    lines.append(
        f"> 결정론 스크리닝(상대강도 RS + 과열도, 60일 기준{regime_part}) 상위 {len(top)}종. "
        "아래 후보 중에서 추천 셔틀리스트를 큐레이션·발행하라 — 점수는 결정론 권위, "
        "선정·근거·경고는 본인 판단."
    )
    lines.append("")
    if not top:
        lines.append("_산출 가능한 후보 없음 (후보 풀 60일 데이터 부족) — 추천 보류 안내._")
        return "\n".join(lines)

    lines.append("| 순위 | 종목 | 상대강도(RS) | 과열도 | 종합 |")
    lines.append("|---|---|---|---|---|")
    for r in top:
        tk = r["ticker"]
        nm = names.get(tk) or tk
        rs = r.get("rs_score")
        ext = r.get("extension_score")
        sc = r.get("screening_score")
        rs_s = "—" if rs is None else f"{rs:.1f}"
        ext_s = "—" if ext is None else f"{ext:.1f}"
        sc_s = "—" if sc is None else f"{sc:.1f}"
        lines.append(f"| {r['rank']} | {nm} ({tk}) | {rs_s} | {ext_s} | {sc_s} |")
    lines.append("")
    lines.append(
        "> 과열도 = 높을수록 건강(낮으면 과열·이탈). 상대강도 = 풀 내 백분위(10=최강). "
        "종합 = 두 축 regime 가중 합성. **신고가 추격·과열 종목은 경고 병기.**"
    )
    return "\n".join(lines)
