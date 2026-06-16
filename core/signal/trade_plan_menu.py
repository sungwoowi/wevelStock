"""결정론 가격대 메뉴 — buy 권고에 다단 손절/분할매수/목표/분할매도 *후보*를 사실로 산출
(TRADE-PLAN-LIFECYCLE-001 B-MS1).

핵심 원칙 (2026-06-15 확정): **결정론 = 후보 메뉴·신호 계산기, 결정자 아님.**
- 결정론은 객관 가격대를 *계산*만 한다 (스윙저점 9,500 / ATR손절 9,400 / ma60 이탈 9,300 /
  오닐 −7% 9,300). 산수라 신뢰도 질문 자체가 없다.
- *어느 것을 이 상황에 쓰나(적재적소)·임계·수정*은 LLM(전략가 persona)이 한다.
- 이 메뉴를 LLM 에 **사실**로 주입해 숫자 환각을 막는다(prism·cited_scores 누수 교훈).
- 소수의 절대 가드레일(오닐 −7%·종가기준)만 결정론 강제 — 신뢰도 높아 당연히 박음.

이 모듈은 **순수 함수**다 (I/O·LLM 0). 어댑터(`trade_plan_inputs_from_ohlcv`)만 collectors
계산 함수를 호출(네트워크 없음). alpha_posture.py 구조 미러링.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# 손절 ATR 밴드 — compute_rr(SLOT S3) 정합. floor=잔파동 털림 방지, cap=수직급등주 손절폭발 방지.
# 분할 사다리 분율([0.4,0.7])·과열도 비중은 paper_trading·sizing 재사용(아래 build).


@dataclass
class TradePlanConfig:
    """가격대 메뉴 임계 (config/screening.yaml `trade_plan` 에서 로드, 기본값 = 여기).

    순수 함수가 파일 I/O 없이 동작하도록 기본값을 코드에 둔다 — funnel 은 load_trade_plan_config()
    로 yaml override 주입. 수치는 SLOT(라이브 누적 후 BRAIN-QUALITY 회고 루프로 캘리브레이션).
    """

    enabled: bool = True
    oneill_max_loss_pct: float = 0.07   # 오닐 −7% 절대 손실 한도 (손절 floor)
    atr_period: int = 14
    atr_k_floor: float = 1.5            # 손절 ATR 밴드 tight (compute_rr 정합)
    atr_k_cap: float = 3.0             # 손절 ATR 밴드 wide
    n_buy_tranches: int = 3
    n_sell_tranches: int = 3
    ladder_fractions: tuple[float, ...] = (0.4, 0.7)  # 2·3차 보간 분율 (paper_trading 정합)
    sell_ratios: tuple[float, ...] = (0.4, 0.3, 0.3)  # 분할매도 기본 비중 (앞단 많이)
    menu_bound_tol_pct: float = 0.03   # LLM 가격이 메뉴 후보와 이 % 이내면 menu-bound(환각 아님)
    max_levels: int = 4                # 다단 지지/저항 최대 단수
    max_swing_stop_pct: float = 0.25   # 스윙저점이 진입 대비 이 % 초과로 멀면 stale(수년전 저점) → 메뉴 제외
    level_dedup_pct: float = 0.005     # 두 가격대가 이 % 이내면 동일 레벨로 dedup (스윙고점==52주고가 등)


@dataclass
class TradePlanInputs:
    """가격대 메뉴 입력 — 전부 결정론 산출값 (OHLCV 에서 계산, I/O 없음)."""

    ticker: str = ""
    current_close: float | None = None
    swing_lows: list[float] = field(default_factory=list)   # 진입 아래 스윙저점 (가까운=높은 順 기대)
    swing_highs: list[float] = field(default_factory=list)  # 진입 위 스윙고점
    ma20: float | None = None
    ma60: float | None = None
    ma120: float | None = None
    atr: float | None = None
    wk52_high: float | None = None
    wk52_low: float | None = None
    anchor_b: float | None = None        # measured-move proxy (WAVE-ALPHA anchor B 가격)
    extension_score: float | None = None  # 과열도 (분할 비중 — 높을수록 저과열=front-load)


@dataclass
class PriceLevel:
    """라벨된 가격 후보 — '무엇인지' 가 핵심(선택은 LLM)."""

    label: str
    price: float

    def to_dict(self) -> dict[str, Any]:
        return {"label": self.label, "price": round(self.price, 2)}


@dataclass
class LadderLeg:
    """분할 차수 — 가격 + 비중."""

    leg: int
    price: float
    ratio: float

    def to_dict(self) -> dict[str, Any]:
        return {"leg": self.leg, "price": round(self.price, 2), "ratio": round(self.ratio, 4)}


@dataclass
class TradePlanMenu:
    """결정론 가격대 메뉴 — buy 권고용 다단 후보 (LLM 이 이 중에서 선택·조합)."""

    ticker: str
    entry_hint: float | None = None
    stop_candidates: list[PriceLevel] = field(default_factory=list)
    support_levels: list[PriceLevel] = field(default_factory=list)
    resistance_levels: list[PriceLevel] = field(default_factory=list)
    target_candidates: list[PriceLevel] = field(default_factory=list)
    buy_ladder: list[LadderLeg] = field(default_factory=list)
    sell_ladder: list[LadderLeg] = field(default_factory=list)
    default_stop: float | None = None   # 스윙저점 ATR-clamp + 오닐 −7% floor (LLM 시작점)
    oneill_floor: float | None = None    # entry × (1 − 7%)
    basis: str = "close"                 # 손절·트리거 = 종가 기준 (장중 wick 무시)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """team_outputs.data_json 가산 주입용 — JSON 직렬화 가능."""
        d = asdict(self)
        d["stop_candidates"] = [c.to_dict() for c in self.stop_candidates]
        d["support_levels"] = [c.to_dict() for c in self.support_levels]
        d["resistance_levels"] = [c.to_dict() for c in self.resistance_levels]
        d["target_candidates"] = [c.to_dict() for c in self.target_candidates]
        d["buy_ladder"] = [c.to_dict() for c in self.buy_ladder]
        d["sell_ladder"] = [c.to_dict() for c in self.sell_ladder]
        d["default_stop"] = round(self.default_stop, 2) if self.default_stop is not None else None
        d["oneill_floor"] = round(self.oneill_floor, 2) if self.oneill_floor is not None else None
        return d


_BOOL_FIELDS = frozenset({"enabled"})
_INT_FIELDS = frozenset({"atr_period", "n_buy_tranches", "n_sell_tranches", "max_levels"})
_TUPLE_FIELDS = frozenset({"ladder_fractions", "sell_ratios"})


def trade_plan_config_from_dict(raw: dict[str, Any] | None) -> TradePlanConfig:
    """yaml `trade_plan` 섹션 → TradePlanConfig (graceful — 미지정/오타입은 default 유지)."""
    cfg = TradePlanConfig()
    if not isinstance(raw, dict):
        return cfg
    for fname in TradePlanConfig.__dataclass_fields__:
        if fname not in raw:
            continue
        val = raw[fname]
        try:
            if fname in _BOOL_FIELDS:
                setattr(cfg, fname, bool(val))
            elif fname in _INT_FIELDS:
                setattr(cfg, fname, int(val))
            elif fname in _TUPLE_FIELDS:
                setattr(cfg, fname, tuple(float(x) for x in val))
            else:
                setattr(cfg, fname, float(val))
        except (TypeError, ValueError):
            continue
    return cfg


# ---------------------------------------------------------------------------
# 절대 가드레일 (소수·고신뢰 = 결정론 강제)
# ---------------------------------------------------------------------------


def clamp_stop_to_oneill(
    entry: float, stop: float, config: TradePlanConfig
) -> tuple[float, bool]:
    """손절이 오닐 −N% 보다 느슨하면(=가격이 더 낮으면) floor(entry×(1−N%))로 끌어올림.

    Returns: (clamped_stop, was_clamped). 오닐 = 최대 손실 한도라 손절 가격의 *하한*.
    """
    floor = entry * (1.0 - config.oneill_max_loss_pct)
    if stop < floor:
        return floor, True
    return stop, False


def is_menu_bound(price: float, candidates: list[float], tol_pct: float) -> bool:
    """price 가 어느 메뉴 후보와 tol_pct 이내면 True. 전부 멀면 False(LLM 환각 의심)."""
    if not candidates or price <= 0:
        return False
    return any(abs(price - c) <= tol_pct * price for c in candidates if c and c > 0)


# ---------------------------------------------------------------------------
# build — 후보 메뉴 산출 (순수)
# ---------------------------------------------------------------------------


def _dedup_levels(levels: list[PriceLevel], tol_pct: float) -> list[PriceLevel]:
    """가격이 tol_pct 이내로 같은 레벨은 첫 항목만 유지 (정렬 순서 보존 — 스윙고점==52주고가 등)."""
    out: list[PriceLevel] = []
    for lv in levels:
        if any(abs(lv.price - k.price) <= tol_pct * max(lv.price, 1.0) for k in out):
            continue
        out.append(lv)
    return out


def _split_ratios(extension: float | None, n: int) -> list[float]:
    """과열도 → 분할 비중 (core.account.sizing 재사용, n 단으로 정규화)."""
    from core.account.sizing import split_ratios

    ratios = list(split_ratios(extension))[:n]
    if not ratios:
        ratios = [1.0 / n] * n
    s = sum(ratios)
    return [r / s for r in ratios] if s else [1.0 / n] * n


def build_trade_plan_menu(inputs: TradePlanInputs, config: TradePlanConfig) -> TradePlanMenu:
    """결정론 가격대 메뉴 산출 — 순수. 결측은 graceful(빈 후보 + reason)."""
    menu = TradePlanMenu(ticker=inputs.ticker, basis="close")
    if not config.enabled:
        menu.reasons.append("trade_plan disabled (config)")
        return menu

    entry = inputs.current_close
    if entry is None or entry <= 0:
        menu.reasons.append("현재가(entry) 부재 — 메뉴 산출 불가")
        return menu
    menu.entry_hint = float(entry)
    menu.oneill_floor = entry * (1.0 - config.oneill_max_loss_pct)

    # --- 손절 후보 메뉴 (라벨된 후보들 — 선택 안 함) ---
    # 스윙저점은 진입 인근만 유효 — 수년전 저점(예: 현재 2.36M인데 808K)은 stale 라 제외.
    stop_floor = entry * (1.0 - config.max_swing_stop_pct)
    near_lows = [p for p in inputs.swing_lows if stop_floor <= p < entry]
    swing_low = max(near_lows, default=None)  # 가까운(높은) 저점
    atr = inputs.atr
    if swing_low is not None:
        menu.stop_candidates.append(PriceLevel("직전 스윙저점", swing_low))
    if atr is not None and atr > 0:
        menu.stop_candidates.append(PriceLevel(f"ATR({config.atr_k_floor}×) 손절", entry - config.atr_k_floor * atr))
    for ma_val, lab in ((inputs.ma60, "60일선 이탈"), (inputs.ma120, "120일선 이탈")):
        if ma_val is not None and ma_val < entry:
            menu.stop_candidates.append(PriceLevel(lab, ma_val))
    menu.stop_candidates.append(PriceLevel("오닐 −7% 절대", menu.oneill_floor))

    # --- 기본 손절 (LLM 시작점) = 스윙저점 ATR-clamp + 오닐 floor (compute_rr 정합) ---
    if atr is not None and atr > 0:
        lo = entry - config.atr_k_cap * atr   # 가장 멈 = cap risk
        hi = entry - config.atr_k_floor * atr  # 가장 가까움 = floor risk
        if swing_low is not None:
            stop = min(max(swing_low, lo), hi)
        else:
            stop = hi
    else:
        stop = swing_low
    if stop is not None:
        clamped, was = clamp_stop_to_oneill(entry, stop, config)
        menu.default_stop = clamped
        if was:
            menu.reasons.append("스윙·ATR 손절이 −7% 초과 → 오닐 floor 로 clamp")
    else:
        menu.reasons.append("손절 레벨 부재 (스윙저점·ATR 미산출) — 분할 사다리 생략")

    # --- 다단 지지/저항 (stale 스윙저점 제외 + 동일가 dedup) ---
    supports: list[PriceLevel] = []
    for p in inputs.swing_lows:
        if stop_floor <= p < entry:
            supports.append(PriceLevel("스윙저점", p))
    for ma_val, lab in ((inputs.ma20, "20일선"), (inputs.ma60, "60일선"), (inputs.ma120, "120일선")):
        if ma_val is not None and ma_val < entry:
            supports.append(PriceLevel(lab, ma_val))
    supports.sort(key=lambda lv: lv.price, reverse=True)  # 가까운(높은) 지지 먼저
    menu.support_levels = _dedup_levels(supports, config.level_dedup_pct)[: config.max_levels]

    resistances: list[PriceLevel] = []
    for p in inputs.swing_highs:
        if p > entry:
            resistances.append(PriceLevel("스윙고점", p))
    if inputs.wk52_high is not None and inputs.wk52_high > entry:
        resistances.append(PriceLevel("52주 고가", inputs.wk52_high))
    resistances.sort(key=lambda lv: lv.price)  # 가까운(낮은) 저항 먼저
    menu.resistance_levels = _dedup_levels(resistances, config.level_dedup_pct)[: config.max_levels]

    # --- 목표 후보 (분할매도용) = 인근 고점 + 파동 목표(anchor B) + 52주 고가 (동일가 dedup) ---
    targets: list[PriceLevel] = list(menu.resistance_levels)
    if inputs.anchor_b is not None and inputs.anchor_b > entry:
        targets.append(PriceLevel("파동 목표(anchor B)", inputs.anchor_b))
    targets.sort(key=lambda lv: lv.price)
    menu.target_candidates = _dedup_levels(targets, config.level_dedup_pct)[: config.max_levels]

    # --- 분할매수 사다리 (entry→stop 보간, paper_trading 재사용) ---
    if menu.default_stop is not None:
        from core.account.paper_trading import compute_tranche_ladder

        ladder = compute_tranche_ladder(
            entry, menu.default_stop, config.n_buy_tranches,
            fractions=list(config.ladder_fractions),
        )
        ratios = _split_ratios(inputs.extension_score, len(ladder))
        menu.buy_ladder = [
            LadderLeg(i + 1, price, ratios[i]) for i, price in enumerate(ladder)
        ]

    # --- 분할매도 사다리 (목표 후보 기반) ---
    if menu.target_candidates:
        k = min(config.n_sell_tranches, len(menu.target_candidates))
        sell_r = list(config.sell_ratios)[:k]
        s = sum(sell_r) or 1.0
        sell_r = [r / s for r in sell_r]
        menu.sell_ladder = [
            LadderLeg(i + 1, menu.target_candidates[i].price, sell_r[i]) for i in range(k)
        ]

    return menu


# ---------------------------------------------------------------------------
# 어댑터 — OHLCV → TradePlanInputs (collectors 계산 함수 호출, 네트워크 없음)
# ---------------------------------------------------------------------------


def trade_plan_inputs_from_ohlcv(
    ohlcv: Any,
    *,
    ticker: str = "",
    entry_hint: float | None = None,
    extension: float | None = None,
    anchor_b: float | None = None,
    config: TradePlanConfig | None = None,
) -> TradePlanInputs:
    """일봉 OHLCV → 결정론 사실(스윙·MA·ATR·52주). extract_swing/compute_indicators/_atr 재사용.

    네트워크 없음(이미 로드된 DataFrame). 각 축 graceful — 실패해도 해당 필드만 None.
    """
    cfg = config or TradePlanConfig()
    inp = TradePlanInputs(ticker=ticker, extension_score=extension, anchor_b=anchor_b)
    if ohlcv is None or len(ohlcv) == 0:
        return inp

    # MA·52주·현재가 (compute_indicators).
    try:
        from collectors.charts import compute_indicators

        ind = compute_indicators(ohlcv)
        inp.current_close = entry_hint if entry_hint is not None else ind.get("current_close")
        dma = ind.get("daily_ma", {})
        inp.ma20, inp.ma60, inp.ma120 = dma.get("ma20"), dma.get("ma60"), dma.get("ma120")
        ftw = ind.get("fifty_two_week", {})
        inp.wk52_high, inp.wk52_low = ftw.get("high"), ftw.get("low")
    except Exception:  # noqa: BLE001 — 지표 실패가 메뉴를 막지 않음
        if entry_hint is not None:
            inp.current_close = entry_hint

    # ATR (technicals._atr).
    try:
        from collectors.technicals import _atr

        inp.atr = _atr(ohlcv, cfg.atr_period)
    except Exception:  # noqa: BLE001
        inp.atr = None

    # 스윙 저점/고점 (anchors.extract_swing_candidates, daily).
    try:
        from collectors.anchors import extract_swing_candidates

        swings = extract_swing_candidates(ohlcv, "daily")
        inp.swing_lows = [p for _, p, k in swings if k == "low"]
        inp.swing_highs = [p for _, p, k in swings if k == "high"]
    except Exception:  # noqa: BLE001
        pass

    return inp


# ---------------------------------------------------------------------------
# render — LLM 프롬프트용 마크다운 (사실 메뉴 — 선택·조합 지시)
# ---------------------------------------------------------------------------


def _fmt(p: float | None) -> str:
    return f"{p:,.0f}" if p is not None else "—"


def render_trade_plan_menu_md(menu: TradePlanMenu) -> str:
    """결정론 가격대 메뉴 → 전략가 프롬프트 주입용 마크다운.

    LLM 은 이 *사실*에서 다단 손절/분할매수/목표/분할매도를 **선택·조합**한다 — 메뉴 밖 가격을
    쓰면 사실 근거를 data 에 로그. −7%·종가기준은 절대 룰. 추측 숫자 금지(환각 차단).
    """
    if menu.entry_hint is None:
        return "## [결정론 가격대 메뉴] 산출 불가 (현재가·OHLCV 부재) — 통상 판단."

    lines = [
        "## [결정론 가격대 메뉴] (객관 산출 — **사실**, 이 중에서 선택·조합하라)",
        f"- 기준가(현재 종가): {_fmt(menu.entry_hint)}",
    ]
    if menu.stop_candidates:
        lines.append("- **손절 후보**: " + " · ".join(
            f"{c.label} {_fmt(c.price)}" for c in menu.stop_candidates))
    if menu.default_stop is not None:
        lines.append(f"  - 결정론 기본 손절(시작점): {_fmt(menu.default_stop)} — 상황에 맞게 선택/조정 가능")
    if menu.support_levels:
        lines.append("- **다단 지지**: " + " · ".join(
            f"{c.label} {_fmt(c.price)}" for c in menu.support_levels))
    if menu.resistance_levels:
        lines.append("- **다단 저항**: " + " · ".join(
            f"{c.label} {_fmt(c.price)}" for c in menu.resistance_levels))
    if menu.target_candidates:
        lines.append("- **목표 후보**: " + " · ".join(
            f"{c.label} {_fmt(c.price)}" for c in menu.target_candidates))
    if menu.buy_ladder:
        lines.append("- **분할매수 사다리(제안)**: " + " · ".join(
            f"{leg.leg}차 {_fmt(leg.price)}({leg.ratio*100:.0f}%)" for leg in menu.buy_ladder))
    if menu.sell_ladder:
        lines.append("- **분할매도 사다리(제안)**: " + " · ".join(
            f"{leg.leg}차 {_fmt(leg.price)}({leg.ratio*100:.0f}%)" for leg in menu.sell_ladder))
    lines.append(
        f"- ⛔ 절대 룰: 손절은 **종가 기준**(장중 wick 무시), 오닐 **−7% 절대**(floor {_fmt(menu.oneill_floor)}) "
        "위반 금지. 메뉴 밖 가격을 쓰면 `data` 에 사실 근거 로그. **추측 숫자 금지.**"
    )
    return "\n".join(lines)
