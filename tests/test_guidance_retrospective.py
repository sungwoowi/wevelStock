"""GUIDANCE-ACCURACY-TRACKER-001 (RB-MS3) G3 — 회고 렌더 테스트 (순수)."""
from __future__ import annotations

from core.guidance.retrospective import render_retrospective


def _summary(**over):
    base = {
        "track": "all", "period_days": 90, "as_of": "2026-06-12",
        "closed_count": 2, "realized_return_avg_pct": 15.0, "benchmark_return_avg_pct": 5.0,
        "alpha_avg_pct": 10.0, "win_rate_pct": 100.0, "rr_realization_avg_pct": 90.0,
        "avg_holding_days": 8.0, "realized_pnl_sum_krw": 450000.0,
        "by_track": {
            "A": {"closed_count": 0, "win_rate_pct": None, "realized_return_avg_pct": None},
            "B": {"closed_count": 2, "win_rate_pct": 100.0, "realized_return_avg_pct": 15.0},
        },
        "records": [
            {"ticker": "005930", "entry_date": "2026-06-01", "exit_date": "2026-06-09",
             "realized_return_pct": 20.0, "alpha_pct": 15.0},
            {"ticker": "000660", "entry_date": "2026-06-02", "exit_date": "2026-06-10",
             "realized_return_pct": 10.0, "alpha_pct": 5.0},
        ],
    }
    base.update(over)
    return base


def test_render_empty_when_no_closed():
    text = render_retrospective(_summary(closed_count=0, records=[]))
    assert "청산된 권고가 아직 없습니다" in text


def test_render_shows_core_metrics():
    text = render_retrospective(_summary())
    assert "청산 권고" in text and "2건" in text
    assert "실현수익률" in text
    assert "시장 대비" in text and "+10.0%p" in text   # 알파
    assert "적중률" in text and "100.0%" in text


def test_render_uses_friendly_track_labels_not_code():
    text = render_retrospective(_summary())
    assert "단기" in text          # Track B → 친화 라벨
    # 코드 라벨 노출 금지
    assert "verdict" not in text.lower()
    assert "track_b" not in text.lower()


def test_render_lists_best_records():
    text = render_retrospective(_summary())
    assert "005930" in text   # best 권고 노출
