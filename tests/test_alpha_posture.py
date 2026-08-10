"""BRAIN-ALPHA-FLEXIBILITY-001 M1 — 결정론 차등 변조 (alpha_posture) 단위 테스트.

핵심 명세: regime 은 더 이상 blanket 게이트가 아니다 — 섹터RS·주도주·파동 생존이
종목별로 verdict 후보를 override 한다. (약세장도 강세섹터+주도주+파동 = 눌림목 타점 /
강세장도 과열 추격은 회피.) 순수 함수라 I/O·LLM 없음.
"""
from __future__ import annotations

from dataclasses import asdict

from core.signal.alpha_posture import (
    AlphaPosture,
    FunnelStage,
    PostureConfig,
    PostureInputs,
    derive_alpha_posture,
    derive_funnel_stage,
    enrich_conditional_entry,
    posture_config_from_dict,
    render_alpha_posture_md,
)
from core.signal.trade_plan_menu import PriceLevel, TradePlanMenu


def _strong_a(**over: object) -> PostureInputs:
    """Track A 매수 후보로 충분한 기본 입력 (테스트별 override)."""
    base = dict(
        track="A", regime="strong_bull", s_score=8.0, buy_score=7.0,
        rs_score=8.0, extension_score=7.0, sector_rs_score=8.0,
        distribution_day_count=0, wave_alive=True,
    )
    base.update(over)
    return PostureInputs(**base)  # type: ignore[arg-type]


# --- 강세장 ---------------------------------------------------------------


def test_bull_with_good_scores_and_healthy_is_buy() -> None:
    p = derive_alpha_posture(_strong_a())
    assert p.verdict_candidate == "buy"
    assert p.regime_class == "bullish"
    assert p.selection_reason  # 설명가능성 — 사유 항상 존재


def test_bull_but_overextended_chase_is_demoted_to_wait() -> None:
    # 강세장이지만 과열도(건강도)가 낮음 = 추격 구간 → buy 후보 강등.
    p = derive_alpha_posture(_strong_a(extension_score=2.0))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("bull_chase_demote") is True
    assert p.conditional_entry is not None
    assert p.conditional_entry["trigger"] == "pullback"


# --- 약세장 (오늘 버그의 핵심) ------------------------------------------


def test_bear_without_sector_strength_defaults_to_wait() -> None:
    # 약세장 + 강세섹터 아님 → 기본 관망 (blanket 보수 유지가 정상인 케이스).
    p = derive_alpha_posture(_strong_a(regime="moderate_bear", sector_rs_score=3.0))
    assert p.verdict_candidate == "wait"
    assert p.regime_class == "bearish"
    assert p.modulation.get("bear_override") is not True


def test_bear_with_strong_sector_leader_wave_pullback_overrides_to_buy() -> None:
    # ★ 약세장이어도 강세섹터 + 주도주 + 파동 생존 + 눌림목 = 차등 매수 후보.
    #   오늘 "strong_bull인데 전부 wait" 의 반대편 — regime 에 통째로 눌리지 않음을 증명.
    p = derive_alpha_posture(_strong_a(
        regime="moderate_bear", sector_rs_score=8.0, s_score=8.0,
        wave_alive=True, extension_score=7.0,
    ))
    assert p.verdict_candidate == "buy"
    assert p.modulation.get("bear_override") is True


def test_bear_override_requires_wave_alive() -> None:
    # 파동 생존 안 하면 약세장 override 불가 (require_wave_for_bear_override 기본 True).
    p = derive_alpha_posture(_strong_a(
        regime="moderate_bear", sector_rs_score=8.0, wave_alive=False,
    ))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("bear_override") is not True


# --- 복합 위험 게이트 (폭락 회피 — blanket, 절대) ------------------------


def test_mild_distribution_no_longer_blanket_blocks() -> None:
    # ★ dd=5 는 더 이상 blanket kill 아님(dd_kill=6 으로 상향) — 강세장 우량주는 buy 후보.
    #   "완만한 분산에도 전부 wait" 의 해소(2026-06-15 라이브 발견).
    p = derive_alpha_posture(_strong_a(distribution_day_count=5))
    assert p.verdict_candidate == "buy"
    assert p.modulation.get("danger_gate") is not True


def test_soft_band_lower_boundary_is_not_blanket() -> None:
    # 2026-08-11 재보정: dd=6(= dd_soft 하단)은 더 이상 blanket 이 아니다.
    #   60일 표본 중앙값이 6 이라 여기서 막으면 절반의 날에 매수가 원천 봉쇄된다.
    #   대신 차등 요구(주도주·강세섹터·눌림목·파동)로 이관 — 정렬된 우량주는 통과.
    p = derive_alpha_posture(_strong_a(distribution_day_count=6))
    assert p.modulation.get("danger_gate") is not True
    assert p.modulation.get("distribution_elevated") is True
    assert p.verdict_candidate == "buy"


def test_same_day_crash_blocks_even_strong_stock(monkeypatch) -> None:
    # 당일 지수 급락(change_pct ≤ -2.5%) = 폭락장 → 우량주여도 blanket 방어(반대매매·프로그램 매도 회피).
    p = derive_alpha_posture(_strong_a(index_change_pct=-3.2))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("danger_gate") is True
    assert p.modulation.get("danger_signal") == "crash"


def test_breadth_collapse_blocks() -> None:
    p = derive_alpha_posture(_strong_a(breadth_ratio=0.15))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("danger_gate") is True


def test_vix_panic_blocks() -> None:
    p = derive_alpha_posture(_strong_a(vix_panic=True))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("danger_gate") is True


def test_danger_in_strong_bear_is_sell_intent() -> None:
    p = derive_alpha_posture(_strong_a(regime="strong_bear", index_change_pct=-3.5))
    assert p.verdict_candidate == "sell"
    assert p.modulation.get("danger_gate") is True


def test_normal_day_no_danger_proceeds_to_differentiation() -> None:
    # 평상시(완만 신호) — 위험 게이트 안 걸리면 차등 변조 작동.
    p = derive_alpha_posture(_strong_a(index_change_pct=0.5, breadth_ratio=0.55, distribution_day_count=3))
    assert p.verdict_candidate == "buy"
    assert p.modulation.get("danger_gate") is not True


# --- 점수 하한 ------------------------------------------------------------


def test_low_scores_below_floor_is_wait_regardless_of_regime() -> None:
    p = derive_alpha_posture(_strong_a(s_score=2.0, buy_score=2.0))
    assert p.verdict_candidate == "wait"
    assert p.conditional_entry is not None


def test_track_b_uses_t_score_floor() -> None:
    # Track B 는 t_score(트리거) 하한을 본다 — s_score 높아도 t_score 낮으면 관망.
    p = derive_alpha_posture(PostureInputs(
        track="B", regime="strong_bull", s_score=9.0, t_score=2.0,
        buy_score=7.0, rs_score=8.0, extension_score=7.0,
        sector_rs_score=8.0, distribution_day_count=0, wave_alive=True,
    ))
    assert p.verdict_candidate == "wait"


def test_track_b_strong_trigger_is_buy() -> None:
    p = derive_alpha_posture(PostureInputs(
        track="B", regime="strong_bull", t_score=8.0, buy_score=6.0,
        rs_score=8.0, extension_score=7.0, sector_rs_score=8.0,
        distribution_day_count=0, wave_alive=True,
    ))
    assert p.verdict_candidate == "buy"


# --- 미상 regime / graceful -----------------------------------------------


def test_unknown_regime_is_conservative_wait() -> None:
    p = derive_alpha_posture(_strong_a(regime=None))
    assert p.verdict_candidate == "wait"
    assert p.regime_class == "unknown"


def test_posture_serializes_to_dict_for_data_json() -> None:
    p = derive_alpha_posture(_strong_a())
    d = p.to_dict()
    assert d["verdict_candidate"] == "buy"
    assert "selection_reason" in d
    assert "modulation" in d


# --- config 주입 ----------------------------------------------------------


def test_config_threshold_override_changes_verdict() -> None:
    # strong_sector_rs 임계를 9.0 으로 올리면 sector_rs=8.0 은 더이상 강세섹터 아님.
    cfg = PostureConfig(strong_sector_rs=9.0)
    p = derive_alpha_posture(
        _strong_a(regime="moderate_bear", sector_rs_score=8.0), config=cfg
    )
    assert p.modulation.get("bear_override") is not True


def test_posture_config_from_dict_empty_is_defaults() -> None:
    cfg = posture_config_from_dict({})
    assert cfg == PostureConfig()


def test_posture_config_from_dict_overrides_known_keys() -> None:
    cfg = posture_config_from_dict({"strong_sector_rs": 9.0, "dd_kill": 5, "enabled": False})
    assert cfg.strong_sector_rs == 9.0
    assert cfg.dd_kill == 5
    assert cfg.enabled is False
    assert cfg.leader_s_score == PostureConfig().leader_s_score  # 미지정 키는 default


def test_posture_config_from_dict_ignores_garbage() -> None:
    # 알 수 없는 키·잘못된 타입은 무시(graceful, watchdog hot-reload 안전).
    cfg = posture_config_from_dict({"bogus": 1, "strong_sector_rs": "nope"})
    assert cfg == PostureConfig()


def test_render_alpha_posture_md_buy_candidate() -> None:
    md = render_alpha_posture_md(derive_alpha_posture(_strong_a()))
    assert "결정론 차등 변조 후보" in md   # 전략가 주입 섹션 헤더
    assert "buy" in md                      # verdict 후보
    assert "bullish" in md                  # regime_class
    # 선정 사유(설명가능성) 한 줄 이상 노출
    assert any(reason[:8] in md for reason in derive_alpha_posture(_strong_a()).selection_reason)


def test_render_alpha_posture_md_wait_shows_conditional_entry() -> None:
    # 강세장 과열 → wait + 조건부 진입(pullback) 노출.
    p = derive_alpha_posture(_strong_a(extension_score=2.0))
    md = render_alpha_posture_md(p)
    assert "wait" in md
    assert "pullback" in md or "조건부" in md


def test_render_alpha_posture_md_instructs_deviation_logging() -> None:
    # 후보를 뒤집으려면 사실 근거 로그 필수라는 지시가 md 에 포함(가드레일 있는 C).
    md = render_alpha_posture_md(derive_alpha_posture(_strong_a()))
    assert "llm_deviation_reason" in md


def test_load_posture_config_reads_yaml_section() -> None:
    # 얇은 로더 smoke — screening.yaml `alpha_posture` 섹션을 PostureConfig 로 (파일 read).
    from collectors.screening import load_posture_config, reload_screening_config

    reload_screening_config()
    cfg = load_posture_config()
    assert isinstance(cfg, PostureConfig)
    assert cfg.enabled is True
    assert cfg.dd_soft == 6   # 분산 고조 진입 = 차등 요구 (blanket 아님)
    assert cfg.dd_kill == 9   # blanket = 표본 최대(8) 초과 시에만
    assert cfg.crash_change_pct == -2.5


# === TRADE-PLAN-LIFECYCLE-001 2단계: 매수대기 단계 ========================
#
# A. conditional_entry 진입존(팩트) 보강 — 결정론은 가격 *후보*(zone)만 붙이고,
#    어느 진입가를 택할지는 LLM. 숫자 출처는 메뉴(환각 0).


def _menu_with_supports() -> TradePlanMenu:
    """진입 10,000 아래 다단 지지(가까운=높은 順): 20일선 9,800·스윙저점 9,500·60일선 9,300."""
    return TradePlanMenu(
        ticker="X",
        entry_hint=10000.0,
        support_levels=[
            PriceLevel("20일선", 9800.0),
            PriceLevel("스윙저점", 9500.0),
            PriceLevel("60일선", 9300.0),
        ],
    )


def test_enrich_pullback_attaches_ma20_and_swing_low() -> None:
    # 강세장 과열 눌림 대기(pullback) → 진입존 = 20일선 + 직전 스윙저점(메뉴 후보 그대로).
    ce = {"trigger": "pullback", "note": "과열 해소 후 눌림", "ref": "ma20"}
    out = enrich_conditional_entry(ce, _menu_with_supports())
    prices = [z["price"] for z in out["entry_zone"]]
    assert 9800.0 in prices and 9500.0 in prices   # ma20·스윙저점
    assert all(p < 10000.0 for p in prices)         # 전부 진입 아래
    assert out["zone_basis"]                         # 방법 라벨 존재
    assert out["trigger"] == "pullback"              # 원본 보존


def test_enrich_bear_alignment_uses_swing_low_and_ma60() -> None:
    # 약세장 정렬 대기(bear_alignment) → 스윙저점·60일선만, 20일선 제외(추세 하단).
    ce = {"trigger": "bear_alignment", "note": "정렬 대기", "missing": ["주도주"]}
    out = enrich_conditional_entry(ce, _menu_with_supports())
    prices = [z["price"] for z in out["entry_zone"]]
    assert 9500.0 in prices and 9300.0 in prices
    assert 9800.0 not in prices                      # 20일선 제외
    assert out["missing"] == ["주도주"]               # 원본 extra 보존


def test_enrich_score_improve_has_empty_zone() -> None:
    # 조건 재평가형 trigger(가격 없음) → entry_zone 비고 사유만.
    for trig in ("score_improve", "danger_release", "regime_confirm", "alignment"):
        out = enrich_conditional_entry({"trigger": trig, "note": "n"}, _menu_with_supports())
        assert out["entry_zone"] == []
        assert "재평가" in out["zone_basis"]


def test_enrich_none_menu_returns_original() -> None:
    ce = {"trigger": "pullback", "note": "n"}
    out = enrich_conditional_entry(ce, None)
    assert out == ce                                 # menu 없으면 원본 그대로(graceful)
    assert "entry_zone" not in out


def test_enrich_none_conditional_entry_returns_none() -> None:
    assert enrich_conditional_entry(None, _menu_with_supports()) is None


def test_enrich_no_matching_support_empty_zone() -> None:
    # pullback 인데 메뉴에 지지 후보가 없음 → entry_zone 비되 basis 는 존재(크래시 0).
    empty_menu = TradePlanMenu(ticker="X", entry_hint=10000.0, support_levels=[])
    out = enrich_conditional_entry({"trigger": "pullback", "note": "n"}, empty_menu)
    assert out["entry_zone"] == []
    assert out["zone_basis"]


def test_render_md_shows_entry_zone() -> None:
    p = derive_alpha_posture(_strong_a(extension_score=2.0))   # 강세장 과열 → pullback wait
    p.conditional_entry = enrich_conditional_entry(p.conditional_entry, _menu_with_supports())
    md = render_alpha_posture_md(p)
    assert "진입존" in md
    assert "9,800" in md or "9,500" in md             # 메뉴 가격 노출


def test_render_md_no_zone_unchanged() -> None:
    # zone 없는 conditional_entry(보강 전) → 진입존 라인 없음(회귀).
    p = derive_alpha_posture(_strong_a(extension_score=2.0))
    md = render_alpha_posture_md(p)
    assert "진입존" not in md
    assert "pullback" in md or "조건부" in md          # 기존 한 줄은 유지


# B. 단계 라벨 파생(결정론 룰) — 관심/매수대기/진입. 새 판단 아니라 조립.


def test_stage_buy_is_entering() -> None:
    inp = _strong_a()
    st = derive_funnel_stage("buy", inp, None)
    assert st.stage == "entering"


def test_stage_wait_near_with_conditional_is_watching() -> None:
    # wait + 1차 점수가 min 근처(margin 1.0 안) + conditional_entry 존재 → 매수대기.
    inp = _strong_a(s_score=5.5, buy_score=5.5)        # floor 6.0, margin 1.0 → 둘 다 ≥5.0
    st = derive_funnel_stage("wait", inp, {"trigger": "pullback"})
    assert st.stage == "watching"
    assert "매수대기" in st.reason


def test_stage_wait_far_below_is_interest() -> None:
    inp = _strong_a(s_score=2.0, buy_score=2.0)
    st = derive_funnel_stage("wait", inp, {"trigger": "score_improve"})
    assert st.stage == "interest"


def test_stage_wait_near_but_no_conditional_is_interest() -> None:
    # 근접해도 트리거(conditional_entry) 없으면 매수대기 아님.
    inp = _strong_a(s_score=5.5, buy_score=5.5)
    st = derive_funnel_stage("wait", inp, None)
    assert st.stage == "interest"


def test_stage_track_b_uses_t_score() -> None:
    inp = PostureInputs(track="B", regime="strong_bull", t_score=5.5, buy_score=4.5)
    st = derive_funnel_stage("wait", inp, {"trigger": "pullback"})
    assert st.stage == "watching"                      # t_score floor 6.0 − 1.0 = 5.0 이상


def test_stage_margin_config_override() -> None:
    # margin 을 2.0 으로 키우면 더 먼 점수도 매수대기 승격.
    cfg = PostureConfig(watching_score_margin=2.0)
    inp = _strong_a(s_score=4.5, buy_score=4.5)        # floor 6 − 2 = 4.0 이상
    st = derive_funnel_stage("wait", inp, {"trigger": "pullback"}, cfg)
    assert st.stage == "watching"


def test_stage_missing_score_is_conservative_interest() -> None:
    inp = _strong_a(s_score=None, buy_score=None)
    st = derive_funnel_stage("wait", inp, {"trigger": "pullback"})
    assert st.stage == "interest"


def test_funnel_stage_serializes() -> None:
    st = derive_funnel_stage("buy", _strong_a(), None)
    d = asdict(st)
    assert d["stage"] == "entering"
    assert "reason" in d


def test_watching_margin_in_config_from_dict() -> None:
    cfg = posture_config_from_dict({"watching_score_margin": 1.5})
    assert cfg.watching_score_margin == 1.5


# --- 분산일 재보정 (2026-08-11) — 절대 blanket → 차등 밴드 --------------------
#
# 실측 근거: KOSPI 25일 분산일 60일 표본의 **중앙값이 정확히 6** (분포 3~8, 평균 5.8).
# dd_kill=6 은 임계가 시장 기저율 한가운데 박힌 것이라 55% 의 날에 발동하고,
# 최근 40영업일은 100% 초과 → track_b 는 560건 전부 wait(buy 역대 0건)이었다.
# 임계만 올리면(9 이상 = 표본 0%) 폭락 방어를 잃으므로, **소프트 밴드**로 이관한다:
#   dd < dd_soft            → 무영향
#   dd_soft ≤ dd < dd_kill  → blanket 아님. 차등 요구(주도주·강세섹터·눌림목·파동)
#   dd ≥ dd_kill            → blanket (표본 최대 8 초과 = 진짜 이례적 악화)


def test_elevated_distribution_allows_aligned_leader_to_buy() -> None:
    """소프트 밴드(dd 6~8): 주도주·강세섹터·눌림목·파동 전부 정렬이면 buy 유지.

    이전엔 dd=7 이 무조건 blanket wait 였다 — 매수가 한 건도 안 나오던 직접 원인.
    """
    p = derive_alpha_posture(_strong_a(distribution_day_count=7))
    assert p.verdict_candidate == "buy"
    assert p.modulation.get("danger_gate") is not True
    assert p.modulation.get("distribution_elevated") is True


def test_elevated_distribution_demotes_unaligned_candidate() -> None:
    """소프트 밴드인데 품질 미정렬(섹터 약함) → wait 강등 + 원판단 기록."""
    p = derive_alpha_posture(_strong_a(distribution_day_count=7, sector_rs_score=3.0))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("danger_gate") is not True
    assert p.modulation.get("distribution_elevated") is True
    assert p.modulation.get("pre_defensive_candidate") == "buy"   # 채점 재료 보존
    assert any("강세섹터" in r for r in p.selection_reason)


def test_extreme_distribution_still_blanket_blocks() -> None:
    """dd ≥ dd_kill(9) = 표본 최대(8) 초과 = 진짜 이례적 → blanket 유지."""
    p = derive_alpha_posture(_strong_a(distribution_day_count=9))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("danger_gate") is True
    assert p.modulation.get("danger_signal") == "distribution"


def test_below_soft_band_distribution_is_untouched() -> None:
    p = derive_alpha_posture(_strong_a(distribution_day_count=5))
    assert p.verdict_candidate == "buy"
    assert p.modulation.get("distribution_elevated") is not True


def test_fast_danger_signals_remain_blanket_in_soft_band() -> None:
    """분산일이 소프트 밴드여도 당일 급락은 여전히 blanket — 폭락 방어 보존."""
    p = derive_alpha_posture(_strong_a(distribution_day_count=7, index_change_pct=-3.2))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("danger_gate") is True
    assert p.modulation.get("danger_signal") == "crash"


def test_elevated_distribution_and_defensive_posture_compose() -> None:
    """분산 소프트 밴드 + defensive 태세 동시 — 요구 조건은 같으므로 정렬되면 통과."""
    p = derive_alpha_posture(_strong_a(distribution_day_count=7, entry_posture="defensive"))
    assert p.verdict_candidate == "buy"
    assert p.modulation.get("defensive_pass") is True
