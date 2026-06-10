"""WEALTH-COMPOUND-TRACKER-001 (RB-MS4) — 매일 자산 스냅샷·곡선·복리 진척 테스트."""
from __future__ import annotations

import pytest

from core.account import compounding, holdings, paper_trading, portfolio
from core.account.compounding import (
    compute_mdd,
    get_compound_progress,
    get_equity_curve,
    render_compound_summary,
    snapshot_equity,
)
from core.account.sizing import reload_accounts_config
from core.db.connection import Database, reset_db


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    reset_db()
    reload_accounts_config()
    db = Database(tmp_path / "test_compound.sqlite")
    for mod in (paper_trading, portfolio, holdings, compounding):
        monkeypatch.setattr(mod, "get_db", lambda: db)
    return db


def _buy(account="kr_swing", shares_value=10_000.0, fill=100.0, date="2026-06-01"):
    paper_trading.record_buy_fill(
        recommendation_id="REC-X", account_id=account, ticker="005930", track="B",
        leg=1, limit_price=fill, fill_price=fill, value_krw=shares_value, filled_date=date, reason="entry",
    )


# ---------------------------------------------------------------------------
# compute_mdd — 순수
# ---------------------------------------------------------------------------


def test_compute_mdd_pure():
    # 고점 110 → 저점 90 = (110-90)/110 = 18.18%
    assert compute_mdd([100, 110, 90, 120]) == pytest.approx(18.18, abs=0.01)


def test_compute_mdd_no_drawdown():
    assert compute_mdd([100, 110, 120]) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# snapshot_equity — DB
# ---------------------------------------------------------------------------


def test_snapshot_equity_realized_plus_unrealized(isolated_db):
    _buy(shares_value=10_000.0, fill=100.0)            # 100주
    paper_trading.record_sell_fill(
        recommendation_id="REC-X", account_id="kr_swing", ticker="005930", track="B",
        leg=1, fill_price=130.0, shares=50.0, filled_date="2026-06-10", reason="target_1",
    )  # 50주 익절 → 실현 (130-100)*50 = 1500, 50주 보유
    snaps = snapshot_equity("2026-06-12", price_lookup=lambda t: 120.0)
    kr = next(s for s in snaps if s["account_id"] == "kr_swing")
    assert kr["realized_cum_krw"] == pytest.approx(1500.0)
    assert kr["unrealized_krw"] == pytest.approx((120.0 - 100.0) * 50.0)  # 1000
    assert kr["equity_krw"] == pytest.approx(100_000_000.0 + 1500.0 + 1000.0)


def test_snapshot_equity_idempotent(isolated_db):
    _buy()
    snapshot_equity("2026-06-12", price_lookup=lambda t: 100.0)
    snapshot_equity("2026-06-12", price_lookup=lambda t: 100.0)
    rows = isolated_db.fetch_all("SELECT * FROM account_equity_snapshot WHERE account_id='kr_swing'")
    assert len(rows) == 1


def test_snapshot_equity_all_four_accounts(isolated_db):
    snaps = snapshot_equity("2026-06-12", price_lookup=lambda t: 100.0)
    assert len(snaps) == 4  # 자산 0 계좌도 seed 기준 스냅샷


# ---------------------------------------------------------------------------
# get_equity_curve — DB
# ---------------------------------------------------------------------------


def test_get_equity_curve_combined_points_ordered(isolated_db):
    _buy(fill=100.0)
    snapshot_equity("2026-06-11", price_lookup=lambda t: 100.0)
    snapshot_equity("2026-06-12", price_lookup=lambda t: 110.0)  # 보유 평가 ↑
    curve = get_equity_curve()
    dates = [p["date"] for p in curve["points"]]
    assert dates == ["2026-06-11", "2026-06-12"]
    assert curve["points"][1]["equity_krw"] > curve["points"][0]["equity_krw"]


def test_get_equity_curve_per_account(isolated_db):
    snapshot_equity("2026-06-12", price_lookup=lambda t: 100.0)
    curve = get_equity_curve(account_id="kr_long")
    assert len(curve["points"]) == 1
    assert curve["points"][0]["equity_krw"] == pytest.approx(100_000_000.0)


def test_get_equity_curve_two_series_realized_vs_total(isolated_db):
    # 보유 평가이익 있을 때: 총자산(마크투마켓) > 실현만 자산
    _buy(fill=100.0)  # 100주 보유 (미실현 대상)
    snapshot_equity("2026-06-12", price_lookup=lambda t: 120.0)  # +20/주 평가이익
    p = get_equity_curve(account_id="kr_swing")["points"][0]
    assert p["equity_krw"] == pytest.approx(100_000_000.0 + (120.0 - 100.0) * 100.0)  # 총 = +2000 평가
    assert p["realized_equity_krw"] == pytest.approx(100_000_000.0)  # 실현만 = seed (아직 안 팜)
    assert p["equity_krw"] > p["realized_equity_krw"]


# ---------------------------------------------------------------------------
# get_compound_progress — 목표 대비
# ---------------------------------------------------------------------------


def test_compound_progress_vs_target(isolated_db):
    _buy(fill=100.0)
    snapshot_equity("2026-06-01", price_lookup=lambda t: 100.0)   # 시작 (평가 0)
    paper_trading.record_sell_fill(
        recommendation_id="REC-X", account_id="kr_swing", ticker="005930", track="B",
        leg=1, fill_price=200.0, shares=100.0, filled_date="2027-06-01", reason="target_1",
    )  # 1년 뒤 +10000 실현
    snapshot_equity("2027-06-01", price_lookup=lambda t: None)
    prog = get_compound_progress(as_of="2027-06-01", benchmark_fetch=lambda *a: (100.0, 110.0))
    assert prog["total_seed_krw"] == pytest.approx(400_000_000.0)   # 4계좌 합 (계좌당 1억)
    assert prog["mdd_pct"] is not None
    # 목표곡선 = seed × 1.18^1 (1년) — target_return ≈ 18%
    assert prog["target_return_pct"] == pytest.approx(18.0, abs=1.0)
    assert prog["alpha_pct"] is not None


def test_render_compound_summary(isolated_db):
    _buy(fill=100.0)
    snapshot_equity("2026-06-12", price_lookup=lambda t: 120.0)
    curve = get_equity_curve()
    prog = get_compound_progress(as_of="2026-06-12", benchmark_fetch=lambda *a: None)
    text = render_compound_summary(prog, curve)
    # 워딩 분리 (2026-06-10): "복리" 는 지식부 자산복리부 용어 — 추적 노출은 "자산 곡선"
    assert "자산 곡선 추적" in text
    assert "복리" not in text
    assert "실현만" in text and "평가 포함" in text   # 두 곡선
    assert "MDD" in text
    # 코드 라벨 노출 금지
    assert "equity_krw" not in text


def test_render_compound_summary_empty(isolated_db):
    text = render_compound_summary(
        get_compound_progress(as_of="2026-06-12", benchmark_fetch=lambda *a: None),
        get_equity_curve(),
    )
    assert "아직 자산 스냅샷이 없습니다" in text
