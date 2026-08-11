"""시장 판세 결정론 팩트 수집 (ADVISOR-CORE-001 M1-a).

M1-a 는 **LLM 없음** — 이미 DB 에 쌓이는데 판세 해석에 안 쓰이던 재료를 모아
구조화하고 md 로 렌더하는 것까지. 판단은 M1-e 의 LLM 이 이 팩트를 읽고 한다.
"""
from __future__ import annotations

import pytest

from core.db.connection import Database, reset_db
from core.signal import market_stance as ms
from core.signal.market_stance import build_stance_facts, render_stance_facts_md


@pytest.fixture()
def db(tmp_path, monkeypatch):
    reset_db()
    d = Database(tmp_path / "stance.sqlite")
    monkeypatch.setattr(ms, "get_db", lambda: d)
    return d


def _macro(db, date, market, **kw):
    row = {
        "date": date, "market": market, "index_close": 6258.77, "change_pct": -0.60,
        "advancing": 697, "declining": 183, "breadth_ratio": 0.792,
        "ma_20d": 6574.78, "trend": "downtrend", "distribution_count_25d": 7,
        "kospi200_night_change_pct": 0.03,
    }
    row.update(kw)
    cols = ", ".join(row)
    db.execute(
        f"INSERT OR REPLACE INTO market_macro_snapshot ({cols}) "
        f"VALUES ({', '.join('?' * len(row))})", tuple(row.values()),
    )


def _sector(db, date, market, sector, rs_ratio, rs_score=5.0):
    db.execute(
        "INSERT OR REPLACE INTO sector_rs_snapshot "
        "(date, market, sector, etf_ticker, rs_score, return_60d, kospi_return_60d, rs_ratio) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (date, market, sector, "000000", rs_score, 0.0, 0.0, rs_ratio),
    )


def _flow(db, date, market, foreign, institution=0, individual=0, pension=0):
    db.execute(
        "INSERT OR REPLACE INTO supply_demand_history "
        "(date, market, foreign_net, institution_net, individual_net, financial_inv_net, pension_net, source) "
        "VALUES (?,?,?,?,?,?,?,'test')",
        (date, market, foreign, institution, individual, 0, pension),
    )


def _usm(db, date, **kw):
    row = {"date": date, "nasdaq_change_pct": 0.08, "sox_change_pct": -1.16, "vix": 15.22,
           "dxy": 99.72, "us_10y": 4.68, "us_10y_change_bp": 2.0, "gold_change_pct": 1.48,
           "wti_change_pct": 2.97, "nq_futures_change_pct": 0.17, "es_futures_change_pct": 0.15}
    row.update(kw)
    cols = ", ".join(row)
    db.execute(
        f"INSERT OR REPLACE INTO us_macro_snapshot ({cols}) "
        f"VALUES ({', '.join('?' * len(row))})", tuple(row.values()),
    )


# --- 1. 양대 시장 (v1 샘플이 통째로 놓쳤던 축) -------------------------------


def test_both_markets_are_collected(db) -> None:
    _macro(db, "2026-08-10", "KOSPI")
    _macro(db, "2026-08-10", "KOSDAQ", index_close=798.81, change_pct=-0.36,
           advancing=1431, declining=236, breadth_ratio=0.858, distribution_count_25d=10)
    f = build_stance_facts("2026-08-10", "postclose")
    assert {leg.market for leg in f.legs} == {"KOSPI", "KOSDAQ"}
    kq = next(l for l in f.legs if l.market == "KOSDAQ")
    assert kq.advancing == 1431 and kq.declining == 236
    assert kq.distribution_count == 10


def test_leg_computes_ma20_gap(db) -> None:
    _macro(db, "2026-08-10", "KOSPI", index_close=6258.77, ma_20d=6574.78)
    leg = build_stance_facts("2026-08-10", "postclose").legs[0]
    assert leg.ma20_gap_pct == pytest.approx(-4.81, abs=0.05)


def test_breadth_trend_divergence_is_flagged(db) -> None:
    """지수는 하락 추세인데 상승종목이 다수 — 대형주 단독 하락 신호."""
    _macro(db, "2026-08-10", "KOSPI", trend="downtrend", breadth_ratio=0.792)
    f = build_stance_facts("2026-08-10", "postclose")
    assert f.legs[0].breadth_diverges is True


def test_no_divergence_when_trend_matches_breadth(db) -> None:
    _macro(db, "2026-08-10", "KOSPI", trend="downtrend", breadth_ratio=0.31)
    assert build_stance_facts("2026-08-10", "postclose").legs[0].breadth_diverges is False


# --- 2. 야간선물 → 시초가 -----------------------------------------------------


def test_night_futures_flat_reads_as_neutral_open(db) -> None:
    _macro(db, "2026-08-10", "KOSPI", kospi200_night_change_pct=0.03)
    _usm(db, "2026-08-10")
    n = build_stance_facts("2026-08-10", "postclose").night
    assert n.k200_night_pct == pytest.approx(0.03)
    assert n.nq_futures_pct == pytest.approx(0.17)
    assert n.gap_call == "flat"


def test_night_futures_breakdown_reads_as_gap_down(db) -> None:
    _macro(db, "2026-08-10", "KOSPI", kospi200_night_change_pct=-0.9)
    _usm(db, "2026-08-10")
    assert build_stance_facts("2026-08-10", "postclose").night.gap_call == "gap_down"


def test_night_futures_surge_reads_as_gap_up(db) -> None:
    _macro(db, "2026-08-10", "KOSPI", kospi200_night_change_pct=1.2)
    _usm(db, "2026-08-10")
    assert build_stance_facts("2026-08-10", "postclose").night.gap_call == "gap_up"


def test_night_missing_is_unknown_not_crash(db) -> None:
    _macro(db, "2026-08-10", "KOSPI", kospi200_night_change_pct=None)
    assert build_stance_facts("2026-08-10", "postclose").night.gap_call == "unknown"


# --- 3. 섹터 3밴드 (강세 / 중립 / 회피) --------------------------------------


def test_sectors_split_into_three_bands(db) -> None:
    _macro(db, "2026-08-10", "KOSPI")
    for name, ratio in [("화장품", 27.4), ("건설", 21.6), ("원자력", 17.5),
                        ("방산", 1.3), ("금융", 0.9),
                        ("조선", -7.4), ("반도체", -10.7), ("AI전력", -20.6)]:
        _sector(db, "2026-08-10", "KOSPI", name, ratio)
    b = build_stance_facts("2026-08-10", "postclose").sectors
    assert [s.sector for s in b.strong] == ["화장품", "건설", "원자력"]
    assert [s.sector for s in b.neutral] == ["방산", "금융"]
    assert [s.sector for s in b.avoid] == ["AI전력", "반도체", "조선"]  # 나쁜 순


def test_sector_bands_empty_when_no_data(db) -> None:
    _macro(db, "2026-08-10", "KOSPI")
    b = build_stance_facts("2026-08-10", "postclose").sectors
    assert b.strong == [] and b.avoid == []


# --- 4. 수급 — 5일 연속성 + 현물↔선물 엇갈림 --------------------------------


def test_foreign_streak_counts_consecutive_selling(db) -> None:
    for d, v in [("2026-08-04", -370577), ("2026-08-05", -100000), ("2026-08-06", -3289274),
                 ("2026-08-07", -858826), ("2026-08-10", -1490868)]:
        _flow(db, d, "KOSPI", v)
    _macro(db, "2026-08-10", "KOSPI")
    fl = build_stance_facts("2026-08-10", "postclose").flows
    assert fl.foreign_streak == -5                       # 음수 = 연속 순매도
    assert fl.foreign_5d == pytest.approx(-6109545)


def test_streak_breaks_on_sign_flip(db) -> None:
    for d, v in [("2026-08-06", -3289274), ("2026-08-07", 500000), ("2026-08-10", -1490868)]:
        _flow(db, d, "KOSPI", v)
    _macro(db, "2026-08-10", "KOSPI")
    assert build_stance_facts("2026-08-10", "postclose").flows.foreign_streak == -1


def test_spot_futures_divergence_detected(db) -> None:
    """외인이 현물은 팔고 선물은 사는 국면 — 헤지 청산/반등 대비 신호."""
    _macro(db, "2026-08-10", "KOSPI")
    _flow(db, "2026-08-10", "KOSPI", -1490868)
    _flow(db, "2026-08-10", "K200_FUT", 547000)
    fl = build_stance_facts("2026-08-10", "postclose").flows
    assert fl.futures_foreign_net == pytest.approx(547000)
    assert fl.spot_futures_diverge is True


def test_no_divergence_when_same_direction(db) -> None:
    _macro(db, "2026-08-10", "KOSPI")
    _flow(db, "2026-08-10", "KOSPI", -1490868)
    _flow(db, "2026-08-10", "K200_FUT", -300000)
    assert build_stance_facts("2026-08-10", "postclose").flows.spot_futures_diverge is False


# --- 5. 자산군 ---------------------------------------------------------------


def test_assets_collected(db) -> None:
    _macro(db, "2026-08-10", "KOSPI")
    _usm(db, "2026-08-10")
    a = build_stance_facts("2026-08-10", "postclose").assets
    assert a.gold_pct == pytest.approx(1.48)
    assert a.sox_pct == pytest.approx(-1.16)
    assert a.us_10y == pytest.approx(4.68)
    assert a.vix == pytest.approx(15.22)


def test_assets_missing_is_none_not_crash(db) -> None:
    _macro(db, "2026-08-10", "KOSPI")
    assert build_stance_facts("2026-08-10", "postclose").assets.gold_pct is None


# --- 6. 렌더 — LLM 이 읽을 md ------------------------------------------------


def test_render_contains_every_axis(db) -> None:
    _macro(db, "2026-08-10", "KOSPI")
    _macro(db, "2026-08-10", "KOSDAQ", index_close=798.81, change_pct=-0.36,
           advancing=1431, declining=236, breadth_ratio=0.858, distribution_count_25d=10)
    for name, ratio in [("화장품", 27.4), ("반도체", -10.7)]:
        _sector(db, "2026-08-10", "KOSPI", name, ratio)
    _flow(db, "2026-08-10", "KOSPI", -1490868)
    _flow(db, "2026-08-10", "K200_FUT", 547000)
    _usm(db, "2026-08-10")
    md = render_stance_facts_md(build_stance_facts("2026-08-10", "postclose"))
    for token in ("코스피", "코스닥", "697", "1,431", "야간선물", "화장품", "반도체",
                  "외국인", "선물", "금", "국채", "VIX"):
        assert token in md, f"{token} 누락"


def test_render_marks_divergences_explicitly(db) -> None:
    """엇갈림은 LLM 이 놓치지 않게 문장으로 명시한다."""
    _macro(db, "2026-08-10", "KOSPI", trend="downtrend", breadth_ratio=0.792)
    _flow(db, "2026-08-10", "KOSPI", -1490868)
    _flow(db, "2026-08-10", "K200_FUT", 547000)
    md = render_stance_facts_md(build_stance_facts("2026-08-10", "postclose"))
    assert "엇갈림" in md


def test_render_is_budget_bounded(db) -> None:
    """판세 md 는 Track C 예산(2,000자)을 넘지 않아야 한다."""
    _macro(db, "2026-08-10", "KOSPI")
    _macro(db, "2026-08-10", "KOSDAQ")
    for i in range(30):
        _sector(db, "2026-08-10", "KOSPI", f"섹터{i}", (i - 15) * 2.0)
    _flow(db, "2026-08-10", "KOSPI", -1490868)
    _usm(db, "2026-08-10")
    md = render_stance_facts_md(build_stance_facts("2026-08-10", "postclose"))
    assert len(md) <= 2000, f"{len(md)}자 — 예산 초과"


def test_empty_day_renders_without_crash(db) -> None:
    md = render_stance_facts_md(build_stance_facts("2026-08-10", "postclose"))
    assert isinstance(md, str) and md


# --- 7. session 축 -----------------------------------------------------------


def test_session_is_carried(db) -> None:
    _macro(db, "2026-08-10", "KOSPI")
    assert build_stance_facts("2026-08-10", "premarket").session == "premarket"


def test_facts_roundtrip_to_dict(db) -> None:
    """facts_json 영속용 — 리플레이 재현 가능해야 한다."""
    _macro(db, "2026-08-10", "KOSPI")
    _usm(db, "2026-08-10")
    d = build_stance_facts("2026-08-10", "postclose").to_dict()
    assert d["as_of"] == "2026-08-10" and d["session"] == "postclose"
    assert d["legs"][0]["market"] == "KOSPI"
    assert d["assets"]["gold_pct"] == pytest.approx(1.48)


# --- 8. 선물 수급 영속 (M1-a — 지금까지 계산만 하고 버려지던 것) --------------


def test_futures_supply_persisted_and_unit_normalized(db, monkeypatch) -> None:
    """KRX 십억원 → 현물 행과 같은 백만원 단위로 정규화해 저장."""
    from collectors import kr_futures_supply_demand as kfsd

    monkeypatch.setattr(kfsd, "get_db", lambda: db, raising=False)
    import core.db as core_db

    monkeypatch.setattr(core_db, "get_db", lambda: db)
    ok = kfsd.persist_futures_supply_demand({
        "trade_date": "20260810", "foreign_net_amount_b": 547,
        "institution_net_amount_b": -120, "individual_net_amount_b": -427,
    })
    assert ok is True
    row = db.fetch_one(
        "SELECT * FROM supply_demand_history WHERE market = ? AND date = ?",
        (ms.FUTURES_MARKET, "2026-08-10"),
    )
    assert row["foreign_net"] == 547_000          # 십억 → 백만
    assert row["institution_net"] == -120_000


def test_futures_persist_rejects_bad_date(db, monkeypatch) -> None:
    from collectors import kr_futures_supply_demand as kfsd
    import core.db as core_db

    monkeypatch.setattr(core_db, "get_db", lambda: db)
    assert kfsd.persist_futures_supply_demand({"trade_date": "", "foreign_net_amount_b": 1}) is False


def test_futures_persist_is_idempotent(db, monkeypatch) -> None:
    from collectors import kr_futures_supply_demand as kfsd
    import core.db as core_db

    monkeypatch.setattr(core_db, "get_db", lambda: db)
    payload = {"trade_date": "20260810", "foreign_net_amount_b": 547,
               "institution_net_amount_b": 0, "individual_net_amount_b": 0}
    kfsd.persist_futures_supply_demand(payload)
    kfsd.persist_futures_supply_demand({**payload, "foreign_net_amount_b": 600})
    rows = db.fetch_all(
        "SELECT foreign_net FROM supply_demand_history WHERE market = ?", (ms.FUTURES_MARKET,)
    )
    assert len(rows) == 1 and rows[0]["foreign_net"] == 600_000


# --- 9. 섹터명 — 사용자 노출단은 짧은 이름 -----------------------------------


def test_sector_name_uses_config_label(db) -> None:
    """ETF 풀네임이 아니라 config sector_labels 의 짧은 이름으로 렌더."""
    _macro(db, "2026-08-10", "KOSPI")
    db.execute(
        "INSERT OR REPLACE INTO sector_rs_snapshot "
        "(date, market, sector, etf_ticker, rs_score, return_60d, kospi_return_60d, rs_ratio) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("2026-08-10", "KOSPI", "KODEX AI전력핵심", "487240", 0.0, -40.8, -20.2, -20.6),
    )
    b = build_stance_facts("2026-08-10", "postclose").sectors
    assert b.avoid[0].sector == "AI전력"


def test_sector_name_falls_back_to_brand_stripped_stem(db) -> None:
    """config 에 없는 티커여도 브랜드 접두는 벗긴다."""
    _macro(db, "2026-08-10", "KOSPI")
    db.execute(
        "INSERT OR REPLACE INTO sector_rs_snapshot "
        "(date, market, sector, etf_ticker, rs_score, return_60d, kospi_return_60d, rs_ratio) "
        "VALUES (?,?,?,?,?,?,?,?)",
        ("2026-08-10", "KOSPI", "TIGER 코스닥150바이오테크", "261070", 9.0, 5.0, 0.0, 12.0),
    )
    b = build_stance_facts("2026-08-10", "postclose").sectors
    assert b.strong[0].sector == "코스닥150바이오테크"


# --- 10. session PK 축 (M1-a 스키마 v21) ------------------------------------


def _view(mv, **over):
    base = dict(
        date="2026-08-10", market="KOSPI", regime="moderate_bear",
        leading_sectors=[], fading_sectors=[], rotation=mv.Rotation(direction="—"),
        entry_posture="defensive", one_liner="장마감", confidence=60, reasons=[],
    )
    base.update(over)
    return mv.MarketView(**base)


def test_two_sessions_coexist_on_same_day(db, monkeypatch) -> None:
    """하루 2회 발행 — 장마감/아침이 서로 덮어쓰지 않는다."""
    from collectors import market_view as mv

    monkeypatch.setattr(mv, "get_db", lambda: db)
    mv.upsert_market_view(_view(mv), session="postclose")
    mv.upsert_market_view(_view(mv, one_liner="아침", entry_posture="neutral"), session="premarket")

    rows = db.fetch_all(
        "SELECT session, one_liner FROM market_view_snapshot WHERE date='2026-08-10'"
    )
    assert {r["session"] for r in rows} == {"postclose", "premarket"}
    assert mv.get_today_view("2026-08-10", "KOSPI", session="premarket").one_liner == "아침"
    assert mv.get_today_view("2026-08-10", "KOSPI", session="postclose").one_liner == "장마감"


def test_default_read_returns_single_latest_session(db, monkeypatch) -> None:
    """session 미지정 = 최신 1건 (기존 호출부 무변 — 두 행이 있어도 하나만)."""
    from collectors import market_view as mv

    monkeypatch.setattr(mv, "get_db", lambda: db)
    mv.upsert_market_view(_view(mv), session="postclose")
    mv.upsert_market_view(_view(mv, one_liner="아침"), session="premarket")
    got = mv.get_today_view("2026-08-10", "KOSPI")
    assert got is not None and got.one_liner in ("아침", "장마감")


def test_upsert_is_idempotent_within_session(db, monkeypatch) -> None:
    from collectors import market_view as mv

    monkeypatch.setattr(mv, "get_db", lambda: db)
    mv.upsert_market_view(_view(mv), session="postclose")
    mv.upsert_market_view(_view(mv, one_liner="갱신"), session="postclose")
    rows = db.fetch_all("SELECT one_liner FROM market_view_snapshot WHERE date='2026-08-10'")
    assert len(rows) == 1 and rows[0]["one_liner"] == "갱신"
