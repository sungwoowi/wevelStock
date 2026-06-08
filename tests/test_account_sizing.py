"""ACCOUNT-MANAGER-001 (RB-MS1) — 비중 산정 결정론 코어 단위 테스트.

순수 함수 (DB·LLM·네트워크 0): 리스크R 해석 / 배포 한도(regime 변조) / 분할 비율(과열도) /
size_position 통합(두 레버 + 7계명 게이트). config 는 명시 주입(파일 비의존, classify_us_risk mirror).
"""
from __future__ import annotations

import pytest

from core.account.sizing import (
    AccountDef,
    AccountState,
    deployment_cap,
    resolve_risk_fraction,
    size_position,
    split_ratios,
)


def _cfg() -> dict:
    """테스트용 sizing config (config/accounts.yaml 의 sizing 블록 미러)."""
    return {
        "risk_per_trade": {"A": 0.01, "B": 0.015},
        "conviction_threshold": 7.0,
        "conviction_min_scores": 3,
        "conviction_r_bonus": 0.5,
        "deployment_cap": {
            "aggressive": 0.80,
            "neutral": 0.60,
            "defensive": 0.45,
        },
        "vix_panic_freeze": True,
        "commandments": {
            "max_total_deployment": 0.80,
            "max_single_position": 0.15,
            "max_trading_deployment": 0.20,
        },
        "split_entry": {
            "bands": [
                {"min_ext": 7.0, "ratios": [0.6, 0.3, 0.1]},
                {"min_ext": 4.0, "ratios": [0.4, 0.3, 0.3]},
                {"min_ext": 0.0, "ratios": [0.2, 0.3, 0.5]},
            ],
            "neutral_ratios": [0.4, 0.3, 0.3],
        },
    }


def _acct(track: str = "A", horizon: str = "long") -> AccountDef:
    return AccountDef(
        account_id=f"kr_{horizon}",
        market="KR",
        track=track,
        horizon=horizon,
        seed_krw=10_000_000,
        label="국장 중장기",
    )


def _state(deployed: float = 0.0, trading_deployed: float = 0.0) -> AccountState:
    return AccountState(
        account_id="kr_long",
        deployed_weight=deployed,
        trading_deployed_weight=trading_deployed,
        positions=[],
    )


def _rec(**over) -> dict:
    base = {
        "recommendation_id": "REC-20260609-005930-A",
        "track": "A",
        "entry_price": 100.0,
        "stop_loss": 90.0,        # 10% 손절폭
        "target_price_1": 130.0,
        "cited_scores": {"s_score": 8.0, "f_score": 7.5, "buy_score": None,
                         "t_score": None, "alpha": None},
    }
    base.update(over)
    return base


# ---------------------------------------------------------------------------
# 레버 1 — resolve_risk_fraction (종목당 고정 리스크 R)
# ---------------------------------------------------------------------------


def test_risk_fraction_track_a_base():
    assert resolve_risk_fraction("A", conviction_count=0, config=_cfg()) == 0.01


def test_risk_fraction_track_b_base():
    assert resolve_risk_fraction("B", conviction_count=0, config=_cfg()) == 0.015


def test_risk_fraction_conviction_bonus_when_3_scores_cross():
    # 3개 이상 점수 교차 → +0.5R (7계명 5번: 단일 지표 금지)
    r = resolve_risk_fraction("A", conviction_count=3, config=_cfg())
    assert r == pytest.approx(0.01 * 1.5)


def test_risk_fraction_no_bonus_below_min_scores():
    # 2개만 교차 → 보너스 없음
    assert resolve_risk_fraction("A", conviction_count=2, config=_cfg()) == 0.01


# ---------------------------------------------------------------------------
# 레버 2 — deployment_cap (regime/entry_posture 변조)
# ---------------------------------------------------------------------------


def test_deployment_cap_aggressive_is_seven_commandment_ceiling():
    assert deployment_cap("aggressive", extreme="none", config=_cfg()) == 0.80


def test_deployment_cap_neutral():
    assert deployment_cap("neutral", extreme="none", config=_cfg()) == 0.60


def test_deployment_cap_defensive_lowered():
    assert deployment_cap("defensive", extreme="none", config=_cfg()) == 0.45


def test_deployment_cap_vix_panic_freezes_new_entry():
    # 극단 게이트: vix_panic → 신규 진입 동결 (방어 하드)
    assert deployment_cap("defensive", extreme="vix_panic", config=_cfg()) == 0.0


# ---------------------------------------------------------------------------
# 분할 — split_ratios (과열도 = extension_score 함수, 높을수록 저과열)
# ---------------------------------------------------------------------------


def test_split_low_extension_back_loads():
    # 고과열(낮은 extension) → 소액 분할 back-load
    assert split_ratios(2.0, config=_cfg()) == [0.2, 0.3, 0.5]


def test_split_high_extension_front_loads():
    # 저과열·좋은 타점(높은 extension) → 초기 비중 front-load
    assert split_ratios(8.5, config=_cfg()) == [0.6, 0.3, 0.1]


def test_split_mid_extension_balanced():
    assert split_ratios(5.0, config=_cfg()) == [0.4, 0.3, 0.3]


def test_split_none_extension_uses_neutral():
    # MA 부재 → 중립 밴드 (추정 금지)
    assert split_ratios(None, config=_cfg()) == [0.4, 0.3, 0.3]


def test_split_ratios_sum_to_one():
    for ext in (1.0, 5.0, 9.0, None):
        assert sum(split_ratios(ext, config=_cfg())) == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# 통합 — size_position (두 레버 + 분할 + 7계명 게이트)
# ---------------------------------------------------------------------------


def test_size_blocks_when_stop_loss_missing():
    # 7계명 4번 + 리스크 역산 불가 → 하드 차단
    out = size_position(
        recommendation=_rec(stop_loss=None),
        account=_acct(),
        state=_state(),
        entry_posture="neutral",
        extension=5.0,
        config=_cfg(),
    )
    assert out.blocked is True
    assert "손절" in out.block_reason


def test_size_blocks_when_entry_not_above_stop():
    # 진입가 ≤ 손절 → 리스크 역산 불가(롱 전제)
    out = size_position(
        recommendation=_rec(entry_price=90.0, stop_loss=95.0),
        account=_acct(),
        state=_state(),
        entry_posture="neutral",
        extension=5.0,
        config=_cfg(),
    )
    assert out.blocked is True


def test_size_risk_based_share_count():
    # 계좌 1000만 × R 1% = 10만원 리스크. 주당 리스크 = 100-90 = 10 → 10,000주.
    # raw 비중 = 10,000×100/1000만 = 10% (단일 15% 아래 → 캡 미적용). 리스크 역산 검증.
    out = size_position(
        recommendation=_rec(),
        account=_acct(),
        state=_state(),
        entry_posture="aggressive",
        extension=5.0,
        config=_cfg(),
    )
    assert out.blocked is False
    assert out.risk_amount_krw == pytest.approx(100_000.0)
    assert out.raw_shares == pytest.approx(10_000.0)


def test_size_caps_at_single_position_limit():
    # 타이트한 손절(stop 95, 주당 리스크 5) → raw_shares 20,000 → raw_weight 0.2 > 단일 15%
    # → 15% 로 자동 축소 + 사유 기록
    out = size_position(
        recommendation=_rec(stop_loss=95.0),
        account=_acct(),
        state=_state(),
        entry_posture="aggressive",
        extension=5.0,
        config=_cfg(),
    )
    assert out.raw_shares == pytest.approx(20_000.0)
    assert out.target_weight == pytest.approx(0.15)
    assert any("단일" in c for c in out.applied_caps)


def test_size_caps_at_remaining_deployment_room():
    # 이미 75% 배포됨, aggressive 천장 80% → 남은 여력 5% 로 축소
    out = size_position(
        recommendation=_rec(),
        account=_acct(),
        state=_state(deployed=0.75),
        entry_posture="aggressive",
        extension=5.0,
        config=_cfg(),
    )
    assert out.target_weight == pytest.approx(0.05)
    assert any("배포" in c or "총" in c for c in out.applied_caps)


def test_size_trading_account_capped_at_20pct():
    # 단기(B) 계좌: 트레이딩 비중 20% 한도 — 단일 15% 보다 총 트레이딩이 먼저 물릴 수 있음
    out = size_position(
        recommendation=_rec(track="B", cited_scores={"t_score": 8.0, "buy_score": 7.5,
                                                     "f_score": 7.0, "s_score": None, "alpha": None}),
        account=_acct(track="B", horizon="swing"),
        state=_state(deployed=0.18, trading_deployed=0.18),
        entry_posture="aggressive",
        extension=5.0,
        config=_cfg(),
    )
    # 트레이딩 20% - 기존 18% = 2% 남음
    assert out.target_weight == pytest.approx(0.02)
    assert any("트레이딩" in c for c in out.applied_caps)


def test_size_freeze_blocks_on_vix_panic():
    # vix_panic → deployment_cap 0 → 신규 진입 0 (차단/사유)
    out = size_position(
        recommendation=_rec(),
        account=_acct(),
        state=_state(),
        entry_posture="defensive",
        extension=5.0,
        extreme="vix_panic",
        config=_cfg(),
    )
    assert out.target_weight == pytest.approx(0.0)
    assert out.blocked is True


def test_size_tranches_split_target_value():
    # 차수별 비중·금액이 target 을 분할, 합이 target 과 일치
    out = size_position(
        recommendation=_rec(),
        account=_acct(),
        state=_state(),
        entry_posture="aggressive",
        extension=8.5,            # front-load 0.6/0.3/0.1
        config=_cfg(),
    )
    assert len(out.tranches) == 3
    assert out.tranches[0].ratio == pytest.approx(0.6)
    assert sum(t.value_krw for t in out.tranches) == pytest.approx(out.value_krw)
    assert sum(t.weight for t in out.tranches) == pytest.approx(out.target_weight)
