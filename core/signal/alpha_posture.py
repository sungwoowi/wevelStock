"""결정론 차등 변조 — regime baseline 위에 섹터RS·주도주·파동이 종목별 override
(BRAIN-ALPHA-FLEXIBILITY-001 M1).

문제: regime 이 verdict 의 **binary blanket 게이트**라 "약세장이면 다 막고 강세장이면 다 연다".
오늘 라이브 = strong_bull 인데 32건 전부 wait. 알파는 그 사이의 차이에 있다.

해법: regime 은 **기본값(baseline)** 일 뿐, 섹터RS·주도주 지위·파동 생존·과열도가 종목별로
verdict 후보를 변조한다.
  - 약세장이어도 강세섹터 + 주도주 + 파동 생존 + 눌림목 → 매수 후보(눌림목 타점, bear_override).
  - 강세장이어도 과열 추격 구간 → 매수 회피(bull_chase_demote).
  - kill-switch(분산일 ≥4)는 보존 — 어떤 regime 이든 신규 진입 차단.

이 모듈은 **순수 함수**다 (I/O·LLM 0, 입력만으로 결정). 가드레일 있는 C 의 결정론 절반 —
LLM(전략가 persona)은 이 후보를 받아 "반박할 사실 있나?" 검증자로 시작하고, 후보를 뒤집을 땐
사실 근거를 로그해야 한다(M2). 점수 collapse 아님(feedback_score_collapse_advisory) —
여러 결정론 지표의 차등 게이트일 뿐, advisory override 여지는 LLM 에 남는다.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

# regime 6단계 → 차등 변조용 3분류 (market_macro.classify_market_regime 출력 기준).
BULLISH = frozenset({"parabolic", "strong_bull", "moderate_bull"})
NEUTRAL = frozenset({"sideways"})
BEARISH = frozenset({"moderate_bear", "strong_bear"})


@dataclass
class PostureConfig:
    """차등 변조 임계 (config/screening.yaml `alpha_posture` 에서 로드, 기본값 = 여기).

    순수 함수가 파일 I/O 없이 동작하도록 기본값을 코드에 둔다 — funnel(M3)은 load_posture_config()
    로 yaml override 를 주입. 모든 값은 SLOT(라이브 누적 후 BRAIN-QUALITY 회고 루프로 캘리브레이션).
    """

    enabled: bool = True
    # 점수 하한 — 매수 후보 최소 품질 (track별 1차 지표 + buy_score AND).
    min_s_score_a: float = 6.0     # Track A 1차 = S-Score(주도주)
    min_buy_score_a: float = 6.0
    min_t_score_b: float = 6.0     # Track B 1차 = T-Score(트리거)
    min_buy_score_b: float = 5.0
    # 차등 변조 임계.
    strong_sector_rs: float = 7.0   # 섹터 RS 이 이상 = 강세섹터
    leader_s_score: float = 7.0     # S-Score 이 이상 = 주도주
    leader_rs_score: float = 8.0    # RS 이 이상 = 주도주 (대체 경로)
    pullback_min_health: float = 6.0  # 과열도(건강도) 이 이상 = 눌림목 건강 (이탈/과열 아님)
    chase_min_health: float = 4.0     # 강세장에서 이 미만 = 과열 추격 → buy 강등
    require_wave_for_bear_override: bool = True  # 약세장 override 에 파동 생존 필수
    # 단계 라벨(매수대기 승격) — wait 인데 1차 점수가 min − margin 이상 + conditional_entry 존재 → "매수대기".
    watching_score_margin: float = 1.0   # 승격 근접 마진 (TRADE-PLAN-LIFECYCLE-001 2단계, SLOT)
    # 복합 위험 게이트 (폭락 회피 — blanket 방어, 차등보다 우선). 2026-06-15 라이브 발견:
    # dd 단독 blanket(4)은 완만한 분산에도 전부 wait + 당일 급락은 못 잡는 최악 조합. 교체.
    crash_change_pct: float = -2.5    # 당일 지수 등락률 이 이하 = 폭락장(반대매매·프로그램 매도)
    breadth_collapse: float = 0.20    # 당일 상승종목 비율 이 이하 = 폭 붕괴
    dd_kill: int = 6                  # 25일 분산일 이 이상 = 지속 천장(오닐 5~6). 4→6 상향(완만 분산 통과)
    # 방어 태세 차등 게이트 (AUTO-SIGNAL-INTEGRITY-001 T0-a) — blanket 아님:
    # entry_posture=defensive 면 buy 후보에 주도주·강세섹터·건강 위치·파동 생존을 추가 요구.
    # (2026-06-29 라이브: defensive 인데 buy 5건 발령 → 07-02 급락 직격이 근거 사고.)
    defensive_gate_enabled: bool = True


@dataclass
class PostureInputs:
    """차등 변조 입력 — Scorecard + 스크리닝 랭킹 행에서 채운다 (전부 결정론 산출값)."""

    track: str                            # "A" | "B"
    regime: str | None = None
    s_score: float | None = None
    t_score: float | None = None
    f_score: float | None = None
    buy_score: float | None = None
    rs_score: float | None = None         # 풀 내 상대강도 (screening rank_candidates)
    extension_score: float | None = None  # 과열도/건강도 (높을수록 건강, 낮으면 과열·이탈)
    sector_rs_score: float | None = None  # 종목 섹터의 섹터 RS (0~10)
    distribution_day_count: int | None = None
    wave_alive: bool | None = None        # 파동 생존 (WAVE-ALPHA α·verdict 매트릭스 → bool)
    # 복합 위험 게이트 입력 (시장 전체 — market_macro/us_macro). 폭락장 blanket 방어용.
    index_change_pct: float | None = None  # 당일 지수 등락률 (market_macro.change_pct)
    breadth_ratio: float | None = None     # 당일 상승종목 비율 (market_macro.breadth_ratio)
    vix_panic: bool | None = None          # 미장 VIX 패닉 (us_macro.extreme == "vix_panic")
    entry_posture: str | None = None       # 시장 진입 자세 (market_view — aggressive/neutral/defensive)


@dataclass
class AlphaPosture:
    """차등 변조 결과 — verdict 후보 + 변조 추적(설명가능성) + 조건부 진입 의도."""

    verdict_candidate: str               # "buy" | "wait" | "sell"
    regime_class: str                    # "bullish" | "neutral" | "bearish" | "unknown"
    selection_reason: list[str] = field(default_factory=list)
    modulation: dict[str, Any] = field(default_factory=dict)
    conditional_entry: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """team_outputs.data_json 가산 주입용 (M5). JSON 직렬화 가능한 평탄 dict."""
        return asdict(self)


@dataclass
class FunnelStage:
    """다층 진입 단계 라벨 (TRADE-PLAN-LIFECYCLE-001 2단계) — 파생 라벨, 새 판단 아님.

    관심(interest) → 매수대기(watching) → 진입(entering). 이미 있는 판단(verdict·점수·
    conditional_entry)을 조립·표면화. legibility = "쓰는 데스크" 차별화.
    """

    stage: str                  # "interest" | "watching" | "entering"
    reason: str                 # 라벨이 된 사유(한 줄)
    score_gap: float | None = None  # 1차 점수 − min (음수=미달). 감사·설명가능성.


_BOOL_FIELDS = frozenset({"enabled", "require_wave_for_bear_override", "defensive_gate_enabled"})
_INT_FIELDS = frozenset({"dd_kill"})


def posture_config_from_dict(raw: dict[str, Any] | None) -> PostureConfig:
    """yaml `alpha_posture` 섹션 dict → PostureConfig (graceful — 미지정/오타입 키는 default).

    순수 매퍼 (파일 I/O 없음). 알 수 없는 키 무시, float 변환 실패 시 해당 필드 default 유지 —
    watchdog hot-reload 중 잘못된 값이 들어와도 크래시 없이 직전/기본 동작 보존.
    """
    cfg = PostureConfig()
    if not isinstance(raw, dict):
        return cfg
    for fname in PostureConfig.__dataclass_fields__:
        if fname not in raw:
            continue
        val = raw[fname]
        try:
            if fname in _BOOL_FIELDS:
                setattr(cfg, fname, bool(val))
            elif fname in _INT_FIELDS:
                setattr(cfg, fname, int(val))
            else:
                setattr(cfg, fname, float(val))
        except (TypeError, ValueError):
            continue  # 오타입 → default 유지
    return cfg


def render_alpha_posture_md(posture: AlphaPosture) -> str:
    """결정론 차등 변조 후보 → 전략가 주입용 md (가드레일 있는 C 의 결정론 절반).

    전략가는 이 후보를 *기본 채택*하되, 뒤집으려면(예: 후보 buy 인데 wait 발행) 사실 근거를
    권고 YAML 의 `data: llm_deviation_reason:` 에 남겨야 한다 — blanket 보수 강등 금지.
    """
    lines = [
        "## 결정론 차등 변조 후보 (AlphaPosture — 권위 베이스라인)",
        "",
        "아래는 regime 을 통째 게이트로 쓰지 않고 **섹터RS·주도주·파동·과열도로 종목별 변조**한",
        "결정론 verdict 후보다. 이 후보를 **기본 채택**하라.",
        "",
        f"- **verdict 후보**: `{posture.verdict_candidate}` (시장 체제 분류: {posture.regime_class})",
    ]
    if posture.selection_reason:
        lines.append("- **선정 근거**:")
        lines.extend(f"  - {r}" for r in posture.selection_reason)
    if posture.modulation:
        mod = ", ".join(f"{k}={v}" for k, v in posture.modulation.items())
        lines.append(f"- **변조 추적**: {mod}")
    if posture.conditional_entry:
        ce = posture.conditional_entry
        lines.append(
            f"- **조건부 진입(관망 시)**: trigger=`{ce.get('trigger')}` — {ce.get('note', '')}"
        )
        zone = ce.get("entry_zone")
        if zone:
            zone_str = " · ".join(f"{z.get('label')} {z.get('price'):,.0f}" for z in zone)
            basis = ce.get("zone_basis", "")
            lines.append(
                f"  - **진입존 후보(팩트 — 이 중에서 선택하라)**: {zone_str}"
                + (f" ({basis})" if basis else "")
            )
    lines += [
        "",
        "**deviation 규칙 (중요)**: 위 후보와 다른 verdict 를 발행하려면 권고 YAML 의",
        "`data: llm_deviation_reason:` 에 **사실 근거**(악재·실적·이벤트 등)를 명시하라. "
        "근거 없는 보수적 강등(blanket wait) 금지 — 후보가 buy 면 반박 사실이 없는 한 buy.",
    ]
    return "\n".join(lines)


def regime_class(regime: str | None) -> str:
    """regime 6단계 → 3분류. 미정의/None → 'unknown'(보수 처리)."""
    if regime in BULLISH:
        return "bullish"
    if regime in NEUTRAL:
        return "neutral"
    if regime in BEARISH:
        return "bearish"
    return "unknown"


def _passes_score_floor(inp: PostureInputs, cfg: PostureConfig) -> tuple[bool, str]:
    """매수 후보 최소 품질 통과 여부 + 사유. 결측 1차 지표 = 보수적 불통과."""
    if inp.track == "A":
        ok = (
            inp.s_score is not None and inp.s_score >= cfg.min_s_score_a
            and inp.buy_score is not None and inp.buy_score >= cfg.min_buy_score_a
        )
        return ok, "중장기 점수 하한(주도주·매수강도) 미달" if not ok else ""
    ok = (
        inp.t_score is not None and inp.t_score >= cfg.min_t_score_b
        and inp.buy_score is not None and inp.buy_score >= cfg.min_buy_score_b
    )
    return ok, "단기 점수 하한(트리거·매수강도) 미달" if not ok else ""


def _cond_entry(trigger: str, note: str, **extra: Any) -> dict[str, Any]:
    """관망 종목 조건부 진입 의도 (M1 = 심볼릭, 진입가 zone 은 enrich_conditional_entry 가 채움)."""
    return {"trigger": trigger, "note": note, **extra}


# trigger → 진입존에 실을 메뉴 지지 후보 라벨 (팩트만 — 어느 가격을 택할지는 LLM).
# 가격형 trigger 만 등록. 조건 재평가형(score_improve/danger_release/regime_confirm/alignment)은
# 특정 눌림가가 없어(조건 충족 후 재평가) entry_zone 을 비운다.
_ZONE_TRIGGER_MAP: dict[str, dict[str, Any]] = {
    "pullback": {
        "labels": ("20일선", "스윙저점"),
        "basis": "눌림목 분할 (20일선·직전 스윙저점)",
    },
    "bear_alignment": {
        "labels": ("스윙저점", "60일선"),
        "basis": "추세 하단 분할 (스윙저점·60일선)",
    },
}


def enrich_conditional_entry(
    conditional_entry: dict[str, Any] | None,
    menu: Any,
) -> dict[str, Any] | None:
    """trigger 별 진입가 *후보 zone*(메뉴 지지 후보에서 선별)을 conditional_entry 에 가산.

    결정론 = 팩트만 — 단일 진입가를 *선택*하지 않고 후보 리스트(zone)만 붙인다(선택은 LLM).
    숫자는 menu.support_levels 에서 그대로 복사 → 환각 0(prism·cited_scores 누수 교훈).
    순수: conditional_entry None → None / menu None → 원본 그대로(graceful).
    가격형이 아닌 trigger → entry_zone=[] + 재평가 사유.
    """
    if conditional_entry is None:
        return None
    if menu is None:
        return conditional_entry
    out = dict(conditional_entry)
    spec = _ZONE_TRIGGER_MAP.get(out.get("trigger"))
    if spec is None:
        out["entry_zone"] = []
        out["zone_basis"] = "조건 재평가 (특정 눌림가 없음 — 조건 충족 후 재산정)"
        return out
    supports = list(getattr(menu, "support_levels", []) or [])
    zone: list[dict[str, Any]] = []
    seen: set[float] = set()
    for lv in supports:
        if lv.label in spec["labels"] and lv.price not in seen:
            zone.append(lv.to_dict())
            seen.add(lv.price)
    if not zone and supports:  # 라벨 매칭 0 → 가장 가까운(첫) 지지로 fallback (빈 zone 회피)
        zone.append(supports[0].to_dict())
    zone.sort(key=lambda z: z["price"], reverse=True)  # 가까운(높은) 진입가 먼저
    out["entry_zone"] = zone
    out["zone_basis"] = spec["basis"]
    return out


def derive_funnel_stage(
    verdict: str,
    inp: PostureInputs,
    conditional_entry: dict[str, Any] | None,
    config: PostureConfig | None = None,
) -> FunnelStage:
    """단계 라벨 파생 (결정론 룰) — 새 판단 아니라 verdict·점수근접·conditional_entry 조립.

    - verdict == "buy"                                        → entering (진입)
    - verdict in (wait, hold) AND 1차 점수 ≥ (min − margin)
      AND conditional_entry 존재                              → watching (매수대기)
    - 그 외                                                   → interest (관심)

    근접 임계 = derive_alpha_posture 의 점수 하한(min)과 한 출처(floor − margin) — 표류 방지.
    1차 점수 결측 = 보수적 interest.
    """
    cfg = config or PostureConfig()
    if inp.track == "A":
        primary, p_floor = inp.s_score, cfg.min_s_score_a
        secondary, s_floor = inp.buy_score, cfg.min_buy_score_a
    else:
        primary, p_floor = inp.t_score, cfg.min_t_score_b
        secondary, s_floor = inp.buy_score, cfg.min_buy_score_b
    gap = (primary - p_floor) if primary is not None else None

    if verdict == "buy":
        return FunnelStage("entering", "매수 발행 — 진입 단계", gap)
    if verdict in ("wait", "hold"):
        m = cfg.watching_score_margin
        near = (
            primary is not None and primary >= p_floor - m
            and secondary is not None and secondary >= s_floor - m
        )
        if near and conditional_entry is not None:
            return FunnelStage(
                "watching", "점수 근접 + 진입 트리거 대기 — 매수대기 단계", gap
            )
    return FunnelStage("interest", "관심 — 점수 미근접 또는 진입 트리거 부재", gap)


def derive_wave_alive(alpha_results: Any, track: str) -> bool | None:
    """α 3tf 결과 → 트랙별 파동 생존 (AUTO-SIGNAL-INTEGRITY-001 T0-b).

    타임프레임↔트랙 철학(2026-06-20): Track A=주봉(추세) / Track B=일봉(단기스윙).
    생존 = 해당 timeframe α 산출됨(value not None) AND label != trend_broken.
    산출 불가·timeframe 부재·입력 None → None (미상 — 소비처가 보수 처리).
    """
    if not alpha_results:
        return None
    tf = "weekly" if track == "A" else "daily"
    r = alpha_results.get(tf) if hasattr(alpha_results, "get") else None
    if r is None or getattr(r, "value", None) is None:
        return None
    return getattr(r, "label", None) != "trend_broken"


def _apply_defensive_gate(
    posture: AlphaPosture, inp: PostureInputs, cfg: PostureConfig
) -> AlphaPosture:
    """방어 태세 차등 게이트 (T0-a) — blanket 아님.

    entry_posture=defensive 인 시장에서 buy 후보는 bear_override 와 같은 결의 조건
    (강세섹터 + 주도주 + 건강 위치 + 파동 생존)을 전부 충족해야 유지된다. 미충족 시
    wait 강등 + 원판단 기록(pre_defensive_candidate) — 채점·설명가능성 보존
    (사용자 결정 2026-07-05: 차등 게이트 + wait 강등·원판단 기록).
    """
    if (
        not cfg.defensive_gate_enabled
        or inp.entry_posture != "defensive"
        or posture.verdict_candidate != "buy"
    ):
        return posture
    mod = posture.modulation
    wave_req_ok = mod.get("wave_ok") is True or not cfg.require_wave_for_bear_override
    missing = [
        label for ok, label in (
            (mod.get("sector_strong") is True, "강세섹터"),
            (mod.get("is_leader") is True, "주도주"),
            (mod.get("healthy") is True, "눌림목(건강 위치)"),
            (wave_req_ok, "파동 생존"),
        ) if not ok
    ]
    if not missing:
        mod["defensive_pass"] = True
        posture.selection_reason.append(
            "시장 방어 태세(defensive)이나 주도주·강세섹터·눌림목·파동 전부 충족 — buy 유지"
        )
        return posture
    mod["defensive_demote"] = True
    mod["pre_defensive_candidate"] = "buy"  # 원판단 기록 (Tier 4 채점 재료)
    posture.verdict_candidate = "wait"
    posture.selection_reason.append(
        "시장 방어 태세(defensive) — 차등 게이트 미충족, 관망 강등 (미충족: "
        + ", ".join(missing) + ")"
    )
    posture.conditional_entry = _cond_entry(
        "defensive_release",
        "방어 태세 해제 또는 주도주·강세섹터·눌림목 정렬 시 재평가",
        missing=missing,
    )
    return posture


def derive_alpha_posture(
    inp: PostureInputs, config: PostureConfig | None = None
) -> AlphaPosture:
    """결정론 차등 변조 — regime baseline × 섹터RS × 주도주 × 파동 × 과열도 → verdict 후보.

    순수: 같은 입력 → 같은 출력. 부작용 0. 모든 분기에 selection_reason 을 남긴다(설명가능성).
    마지막에 방어 태세 차등 게이트(_apply_defensive_gate)가 buy 후보를 한 번 더 검증한다.
    """
    cfg = config or PostureConfig()
    return _apply_defensive_gate(_derive_base(inp, cfg), inp, cfg)


def _derive_base(inp: PostureInputs, cfg: PostureConfig) -> AlphaPosture:
    """차등 변조 본체 (위험 게이트 → 점수 하한 → regime × 차등)."""
    rclass = regime_class(inp.regime)
    reasons: list[str] = []
    mod: dict[str, Any] = {"regime": inp.regime, "regime_class": rclass}

    # 1) 복합 위험 게이트 (폭락 회피 — blanket 방어, 차등보다 우선).
    #    빠른 신호(당일 급락·breadth 붕괴·VIX 패닉) + 느린 신호(지속 분산) 결합. 하나라도 = blanket.
    #    "완만한 분산(dd 4~5)에 전부 wait" 는 풀고, "진짜 위험 당일"은 우량주여도 막는다.
    dd = inp.distribution_day_count or 0
    danger_signal: str | None = None
    if inp.index_change_pct is not None and inp.index_change_pct <= cfg.crash_change_pct:
        danger_signal = "crash"
    elif inp.breadth_ratio is not None and inp.breadth_ratio <= cfg.breadth_collapse:
        danger_signal = "breadth_collapse"
    elif inp.vix_panic is True:
        danger_signal = "vix_panic"
    elif dd >= cfg.dd_kill:
        danger_signal = "distribution"
    if danger_signal is not None:
        mod["danger_gate"] = True
        mod["danger_signal"] = danger_signal
        _DANGER_KR = {
            "crash": f"당일 지수 급락({inp.index_change_pct}%) — 폭락장 방어",
            "breadth_collapse": f"상승종목 폭 붕괴({inp.breadth_ratio}) — 시장 광범위 약세",
            "vix_panic": "미장 VIX 패닉 — 위험회피 전면 방어",
            "distribution": f"25일 분산일 {dd}건 — 지속 천장 경고",
        }
        reasons.append(f"위험 게이트 발동: {_DANGER_KR[danger_signal]}, 신규 진입 차단")
        verdict = "sell" if inp.regime == "strong_bear" else "wait"
        if verdict == "sell":
            reasons.append("강한 약세 + 위험 신호 — 보유 시 청산 우선")
        return AlphaPosture(
            verdict, rclass, reasons, mod,
            _cond_entry("danger_release", "시장 위험 해소 후 재평가"),
        )

    # 2) 점수 하한 — 매수 후보 최소 품질. 미달 시 regime 무관 관망.
    floor_ok, floor_reason = _passes_score_floor(inp, cfg)
    mod["score_floor_ok"] = floor_ok
    if not floor_ok:
        reasons.append(floor_reason)
        return AlphaPosture(
            "wait", rclass, reasons, mod,
            _cond_entry("score_improve", "점수 하한 회복 시 재평가"),
        )

    # 3) 차등 신호 산출.
    sector_strong = inp.sector_rs_score is not None and inp.sector_rs_score >= cfg.strong_sector_rs
    is_leader = (
        (inp.s_score is not None and inp.s_score >= cfg.leader_s_score)
        or (inp.rs_score is not None and inp.rs_score >= cfg.leader_rs_score)
    )
    wave_ok = inp.wave_alive is True  # None/False → 약세장 override 불가(보수)
    healthy = inp.extension_score is not None and inp.extension_score >= cfg.pullback_min_health
    over_extended = inp.extension_score is not None and inp.extension_score < cfg.chase_min_health
    mod.update({
        "sector_strong": sector_strong, "is_leader": is_leader,
        "wave_ok": wave_ok, "healthy": healthy, "over_extended": over_extended,
    })

    # 4) regime baseline × 차등.
    if rclass == "bullish":
        if over_extended:
            mod["bull_chase_demote"] = True
            reasons.append("강세장이나 과열 추격 구간 — 신규 진입 회피, 눌림 대기")
            return AlphaPosture(
                "wait", rclass, reasons, mod,
                _cond_entry("pullback", "과열 해소 후 이평선 부근 눌림 재평가", ref="ma20"),
            )
        reasons.append("강세장 + 점수 하한 통과 + 과열 아님 — 매수 후보")
        if sector_strong:
            reasons.append("강세섹터 동반")
        return AlphaPosture("buy", rclass, reasons, mod, None)

    if rclass == "neutral":
        if sector_strong and healthy:
            reasons.append("횡보장 + 강세섹터 + 건강한 위치 — 선별 매수 후보")
            return AlphaPosture("buy", rclass, reasons, mod, None)
        reasons.append("횡보장 — 강세섹터/건강 위치 미충족, 관망")
        return AlphaPosture(
            "wait", rclass, reasons, mod,
            _cond_entry("alignment", "강세섹터·건강 위치 정렬 시 재평가"),
        )

    if rclass == "bearish":
        wave_req_ok = wave_ok or not cfg.require_wave_for_bear_override
        override = sector_strong and is_leader and healthy and wave_req_ok
        if override:
            mod["bear_override"] = True
            reasons.append(
                "약세장이나 강세섹터 + 주도주 + 파동 생존 + 눌림목 — 차등 매수 후보(눌림목 타점)"
            )
            return AlphaPosture("buy", rclass, reasons, mod, None)
        missing = [
            label for cond, label in (
                (sector_strong, "강세섹터"), (is_leader, "주도주"),
                (healthy, "눌림목(건강 위치)"), (wave_req_ok, "파동 생존"),
            ) if not cond
        ]
        reasons.append("약세장 — 차등 진입 조건 미충족, 관망 (미충족: " + ", ".join(missing) + ")")
        return AlphaPosture(
            "wait", rclass, reasons, mod,
            _cond_entry("bear_alignment", "강세섹터·주도주·파동·눌림목 정렬 시 재평가", missing=missing),
        )

    # 5) regime 미상 — 보수적 관망.
    reasons.append("시장 체제 미상 — 보수적 관망")
    return AlphaPosture(
        "wait", rclass, reasons, mod,
        _cond_entry("regime_confirm", "시장 체제 확정 후 재평가"),
    )
