"""ACCOUNT-MANAGER-001 (RB-MS1) — position-sizing-v1 사람 친화 markdown 렌더 테스트."""
from __future__ import annotations

from core.account.sizing import (
    AccountDef,
    AccountState,
    render_position_sizing_md,
    size_position,
)


def _acct(track="A", horizon="long") -> AccountDef:
    return AccountDef(account_id=f"kr_{horizon}", market="KR", track=track,
                      horizon=horizon, seed_krw=10_000_000, label="국장 중장기")


def _rec(**over) -> dict:
    base = {
        "recommendation_id": "REC-20260609-005930-A",
        "ticker": "005930",
        "track": "A",
        "entry_price": 100.0,
        "stop_loss": 90.0,
        "cited_scores": {"s_score": 8.0, "f_score": 7.5},
    }
    base.update(over)
    return base


def _cfg() -> dict:
    return {
        "risk_per_trade": {"A": 0.01, "B": 0.015},
        "conviction_threshold": 7.0, "conviction_min_scores": 3, "conviction_r_bonus": 0.5,
        "deployment_cap": {"aggressive": 0.80, "neutral": 0.60, "defensive": 0.45},
        "vix_panic_freeze": True,
        "commandments": {"max_total_deployment": 0.80, "max_single_position": 0.15,
                         "max_trading_deployment": 0.20},
        "split_entry": {"bands": [{"min_ext": 7.0, "ratios": [0.6, 0.3, 0.1]},
                                  {"min_ext": 4.0, "ratios": [0.4, 0.3, 0.3]},
                                  {"min_ext": 0.0, "ratios": [0.2, 0.3, 0.5]}],
                        "neutral_ratios": [0.4, 0.3, 0.3]},
    }


def test_render_includes_account_label_and_weight():
    out = size_position(recommendation=_rec(), account=_acct(),
                        state=AccountState(account_id="kr_long"),
                        entry_posture="aggressive", extension=8.5, config=_cfg())
    md = render_position_sizing_md(out)
    assert "국장 중장기" in md
    assert "%" in md          # 비중 비율
    assert "005930" in md


def test_render_shows_tranches_with_amounts():
    out = size_position(recommendation=_rec(), account=_acct(),
                        state=AccountState(account_id="kr_long"),
                        entry_posture="aggressive", extension=8.5, config=_cfg())
    md = render_position_sizing_md(out)
    assert "1차" in md and "2차" in md and "3차" in md


def test_render_blocked_shows_reason():
    out = size_position(recommendation=_rec(stop_loss=None), account=_acct(),
                        state=AccountState(account_id="kr_long"),
                        entry_posture="neutral", extension=5.0, config=_cfg())
    md = render_position_sizing_md(out)
    assert "차단" in md
    assert "손절" in md


def test_render_no_code_label_leak():
    # production 친화 — 코드 라벨(target_weight·risk_fraction) 노출 금지
    out = size_position(recommendation=_rec(), account=_acct(),
                        state=AccountState(account_id="kr_long"),
                        entry_posture="aggressive", extension=8.5, config=_cfg())
    md = render_position_sizing_md(out)
    assert "target_weight" not in md
    assert "risk_fraction" not in md
