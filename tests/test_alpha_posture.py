"""BRAIN-ALPHA-FLEXIBILITY-001 M1 — 결정론 차등 변조 (alpha_posture) 단위 테스트.

핵심 명세: regime 은 더 이상 blanket 게이트가 아니다 — 섹터RS·주도주·파동 생존이
종목별로 verdict 후보를 override 한다. (약세장도 강세섹터+주도주+파동 = 눌림목 타점 /
강세장도 과열 추격은 회피.) 순수 함수라 I/O·LLM 없음.
"""
from __future__ import annotations

from core.signal.alpha_posture import (
    AlphaPosture,
    PostureConfig,
    PostureInputs,
    derive_alpha_posture,
    posture_config_from_dict,
)


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


# --- kill-switch (보존) ---------------------------------------------------


def test_distribution_kill_switch_blocks_buy_even_in_bull() -> None:
    # 분산일 ≥4 = kill-switch. 강세장·고득점이라도 신규 진입 차단.
    p = derive_alpha_posture(_strong_a(distribution_day_count=5))
    assert p.verdict_candidate == "wait"
    assert p.modulation.get("kill_switch") is True


def test_strong_bear_kill_switch_is_sell_intent() -> None:
    p = derive_alpha_posture(_strong_a(regime="strong_bear", distribution_day_count=6))
    assert p.verdict_candidate == "sell"
    assert p.modulation.get("kill_switch") is True


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


def test_load_posture_config_reads_yaml_section() -> None:
    # 얇은 로더 smoke — screening.yaml `alpha_posture` 섹션을 PostureConfig 로 (파일 read).
    from collectors.screening import load_posture_config, reload_screening_config

    reload_screening_config()
    cfg = load_posture_config()
    assert isinstance(cfg, PostureConfig)
    assert cfg.enabled is True
    assert cfg.dd_kill == 4
