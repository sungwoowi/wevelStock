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


def _ohlcv(db, ticker, *, end="2026-08-12", bars=260, start=100.0, rate=0.004):
    """일봉 적재 — F3 이평 구조의 유일한 입력. 기하 상승이라 정배열이 나온다.

    260봉 = 일봉 120MA·주봉 20MA(100일)·월봉 7MA(~147일)를 모두 채우는 최소치.
    `execute` 는 호출마다 커넥션을 여닫으므로 **executemany 한 번**으로 넣는다.
    """
    import pandas as pd

    dates = pd.bdate_range(end=pd.Timestamp(end), periods=bars)
    rows, price = [], start
    for d in dates:
        rows.append((ticker, d.strftime("%Y-%m-%d"), price, price * 1.01, price * 0.99,
                     price, 1000, f"{end}T18:00:00+09:00"))
        price *= 1 + rate
    db.executemany(
        "INSERT OR REPLACE INTO chart_ohlcv "
        "(ticker, date, open, high, low, close, volume, adjusted, fetched_at) "
        "VALUES (?,?,?,?,?,?,?,1,?)",
        rows,
    )


def _universe(db, date, ticker, name, *, rank=1, market="KOSPI", change_pct=3.0):
    db.execute(
        "INSERT OR REPLACE INTO universe_membership "
        "(date, market, ticker, list_type, name, rank, trade_amount, change_pct, source) "
        "VALUES (?,?,?,'trade_value',?,?,?,?,'test')",
        (date, market, ticker, name, rank, 1_000_000, change_pct),
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


# ===========================================================================
# M1-e — 판세 LLM + 영속 + 알림
#   실 LLM 호출 0 (call_llm stub). 결정론 팩트(M1-a~c)는 위 테스트가 담당.
# ===========================================================================

_STANCE_JSON = """{
  "headline": "대형 반도체만 무너지는 중 — 회피가 아니라 갈아타기 국면.",
  "narrative": "지수는 20일선 아래지만 상승종목이 8할이다. 시총 상위가 지수를 눌렀다.",
  "rotation_read": "기술주에서 가치·방어로 자금이 옮겨간다. 반도체 반등 근거는 아직 없다.",
  "risk_read": "무너짐이 아니라 눌림. 상승종목 비율 50% 붕괴가 경계선.",
  "stance": "selective",
  "scenarios": [
    {"trigger": "야간선물 -0.5% 붕괴", "action": "갭하락 대응, 시초 추격 금지", "kind": "risk"},
    {"trigger": "외국인 현물 순매수 전환", "action": "반도체 재평가 시작", "kind": "opportunity"}
  ]
}"""


@pytest.fixture()
def stub_llm(monkeypatch):
    """call_llm 치환 — 호출 인자 캡처 + 고정 응답."""
    calls: list[dict] = []

    async def _fake(**kw):
        calls.append(kw)
        return {"content": _STANCE_JSON, "tokens_in": 1200, "tokens_out": 300,
                "model": "gemini-2.5-flash", "cost_usd": 0.001, "raw": {}}

    monkeypatch.setattr(ms, "call_llm", _fake)
    return calls


def _seed_day(db, day="2026-08-10"):
    # 지수 차트도 당일치로 — 신선도 가드가 통과해야 판세가 발행된다.
    db.execute(
        "INSERT OR REPLACE INTO chart_ohlcv "
        "(ticker, date, open, high, low, close, volume, fetched_at) "
        "VALUES ('0001',?,6258.77,6258.77,6258.77,6258.77,1000,'2026-08-12T18:00:00')", (day,),
    )
    _macro(db, day, "KOSPI")
    _macro(db, day, "KOSDAQ", index_close=798.81, change_pct=-0.36,
           advancing=1431, declining=236, breadth_ratio=0.858, distribution_count_25d=10)
    _sector(db, day, "KOSPI", "화장품", 27.4)
    _sector(db, day, "KOSPI", "반도체", -10.7)
    _flow(db, day, "KOSPI", -1490868)
    _usm(db, day)


async def test_generate_persists_stance_and_facts(db, stub_llm) -> None:
    _seed_day(db)
    out = await ms.generate_market_stance("2026-08-10", "postclose")
    assert out is not None and out.stance == "selective"

    row = db.fetch_one(
        "SELECT * FROM market_view_snapshot WHERE date='2026-08-10' "
        "AND market='KOSPI' AND session='postclose'"
    )
    assert row["narrative"]
    assert row["rotation_read"]
    assert row["risk_read"]
    assert row["stance"] == "selective"
    assert row["facts_json"], "리플레이 재현용 팩트 스냅샷이 없다"


async def test_llm_receives_deterministic_facts(db, stub_llm) -> None:
    """LLM 프롬프트에 결정론 사실이 실려야 한다 — 지어내지 않게."""
    _seed_day(db)
    await ms.generate_market_stance("2026-08-10", "postclose")
    user_msg = stub_llm[0]["messages"][0]["content"]
    for token in ("코스피", "코스닥", "1,431", "화장품", "야간선물"):
        assert token in user_msg, f"{token} 누락"


async def test_llm_call_is_budget_shaped(db, stub_llm) -> None:
    """판세는 1콜·소형. thinking 예산 잠식으로 JSON 잘리는 사고 방지."""
    _seed_day(db)
    await ms.generate_market_stance("2026-08-10", "postclose")
    assert len(stub_llm) == 1
    kw = stub_llm[0]
    assert kw["call_type"] == "market_stance"
    assert kw.get("thinking_budget") == 0
    assert kw.get("max_tokens", 0) >= 1024


async def test_two_sessions_do_not_overwrite(db, stub_llm) -> None:
    _seed_day(db)
    await ms.generate_market_stance("2026-08-10", "postclose")
    await ms.generate_market_stance("2026-08-10", "premarket")
    rows = db.fetch_all(
        "SELECT session FROM market_view_snapshot WHERE date='2026-08-10' AND market='KOSPI'"
    )
    assert {r["session"] for r in rows} == {"postclose", "premarket"}


async def test_llm_failure_is_graceful(db, monkeypatch) -> None:
    """LLM 이 죽어도 크래시 없이 None — 결정론 팩트는 이미 영속돼 있다."""
    _seed_day(db)

    async def _boom(**kw):
        raise RuntimeError("upstream down")

    monkeypatch.setattr(ms, "call_llm", _boom)
    assert await ms.generate_market_stance("2026-08-10", "postclose") is None


async def test_bad_json_is_graceful(db, monkeypatch) -> None:
    _seed_day(db)

    async def _junk(**kw):
        return {"content": "이건 JSON 이 아니다", "tokens_in": 1, "tokens_out": 1, "raw": {}}

    monkeypatch.setattr(ms, "call_llm", _junk)
    assert await ms.generate_market_stance("2026-08-10", "postclose") is None


# --- 알림 렌더 --------------------------------------------------------------


def test_notification_body_has_every_section() -> None:
    stance = ms.MarketStance(
        as_of="2026-08-10", session="postclose",
        headline="대형 반도체만 무너지는 중 — 회피가 아니라 갈아타기 국면.",
        narrative="지수는 20일선 아래지만 상승종목이 8할이다.",
        rotation_read="기술주에서 가치·방어로 자금이 옮겨간다.",
        risk_read="무너짐이 아니라 눌림.",
        stance="selective",
        scenarios=[{"trigger": "야간선물 -0.5% 붕괴", "action": "갭하락 대응", "kind": "risk"}],
        facts_md="### 지수\n- 코스피 6,258.77 -0.60%",
    )
    body = ms.render_stance_notification(stance)
    assert "갈아타기" in body
    assert "기민한 선별" in body          # stance 코드 → 한국어
    assert "selective" not in body        # 코드 라벨 노출 금지
    assert "야간선물 -0.5% 붕괴" in body
    assert "갭하락 대응" in body
    assert "코스피" in body               # 사실 블록 동반


def test_notification_stance_labels_are_korean() -> None:
    for code, kr in (("selective", "기민한 선별"), ("watch", "관망"), ("avoid", "회피")):
        s = ms.MarketStance(as_of="d", session="postclose", headline="h", narrative="n",
                            rotation_read="r", risk_read="k", stance=code, scenarios=[],
                            facts_md="")
        assert kr in ms.render_stance_notification(s)


def test_notification_without_scenarios_is_graceful() -> None:
    s = ms.MarketStance(as_of="d", session="postclose", headline="h", narrative="n",
                        rotation_read="r", risk_read="k", stance="watch", scenarios=[],
                        facts_md="")
    assert ms.render_stance_notification(s)


async def test_emit_sends_notification(db, stub_llm, monkeypatch) -> None:
    sent: list[dict] = []

    async def _fake_notify(**kw):
        sent.append(kw)
        return {"channel": "test"}

    monkeypatch.setattr(ms, "notify", _fake_notify)
    _seed_day(db)
    await ms.run_market_stance("2026-08-10", "postclose")
    assert len(sent) == 1
    assert sent[0]["notification_type"] == "market_briefing"
    assert "판세" in sent[0]["title"]
    assert "장마감" in sent[0]["title"]


async def test_emit_skipped_when_llm_fails(db, monkeypatch) -> None:
    sent: list[dict] = []

    async def _fake_notify(**kw):
        sent.append(kw)
        return {"channel": "test"}

    async def _boom(**kw):
        raise RuntimeError("down")

    monkeypatch.setattr(ms, "notify", _fake_notify)
    monkeypatch.setattr(ms, "call_llm", _boom)
    _seed_day(db)
    await ms.run_market_stance("2026-08-10", "postclose")
    assert sent == []   # 빈 판세를 보내느니 안 보낸다


# --- cron 등록 --------------------------------------------------------------


def test_stance_cron_registered_at_both_sessions() -> None:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from server.schedulers.jobs import register_infra_jobs
    from server.schedulers.jobs.auto_signal import MISFIRE_GRACE_SEC

    sched = AsyncIOScheduler(timezone="Asia/Seoul")
    register_infra_jobs(sched)

    for session, hour, minute in (("postclose", 18, 0), ("premarket", 7, 5)):
        job = sched.get_job(f"market_stance::{session}")
        assert job is not None, f"{session} 미등록"
        assert tuple(job.args) == (session,)
        assert job.misfire_grace_time == MISFIRE_GRACE_SEC
        assert job.coalesce is True and job.max_instances == 1
        assert job.trigger.fields[job.trigger.FIELD_NAMES.index("hour")].expressions[0].first == hour
        assert job.trigger.fields[job.trigger.FIELD_NAMES.index("minute")].expressions[0].first == minute


def test_stance_runs_before_auto_signal() -> None:
    """판세(18:00)가 자동 권고(18:05)보다 앞 — 판세가 권고의 입력이어야 한다."""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler

    from server.schedulers.jobs import register_infra_jobs

    sched = AsyncIOScheduler(timezone="Asia/Seoul")
    register_infra_jobs(sched)

    def _hm(job_id: str) -> tuple[int, int]:
        j = sched.get_job(job_id)
        names = j.trigger.FIELD_NAMES
        return (
            j.trigger.fields[names.index("hour")].expressions[0].first,
            j.trigger.fields[names.index("minute")].expressions[0].first,
        )

    assert _hm("market_stance::postclose") < _hm("infra::daily_refresh")


async def test_stance_job_returns_published_flag(db, stub_llm, monkeypatch) -> None:
    from server.schedulers.jobs.market_stance import run_market_stance_job

    monkeypatch.setattr(ms, "notify", lambda **kw: _noop())
    _seed_day(db, "2026-08-10")
    monkeypatch.setattr(
        "server.schedulers.jobs.market_stance.datetime",
        _FrozenDatetime,
    )
    out = await run_market_stance_job("postclose")
    assert out["session"] == "postclose"
    assert out["published"] is True
    assert out["stance"] == "selective"


async def _noop():
    return {"channel": "test"}


class _FrozenDatetime:
    @staticmethod
    def now(tz=None):
        import datetime as _dt

        return _dt.datetime(2026, 8, 10, 18, 0, tzinfo=tz)


# --- 시나리오 정규화 (LLM 출력 형태가 흔들려도 버리지 않는다) ------------------


def test_scenarios_accept_object_form() -> None:
    out = ms._coerce_scenarios(
        [{"trigger": "상승종목 50% 붕괴", "action": "비중 축소", "kind": "reduce"}]
    )
    assert out == [{"trigger": "상승종목 50% 붕괴", "action": "비중 축소", "kind": "reduce"}]


def test_scenarios_accept_string_form() -> None:
    """실측: claude_code 가 객체 대신 'A 시 → B' 문자열 배열을 낸다."""
    out = ms._coerce_scenarios(["외국인 5일 누적 순매수 전환 시 → 반도체 재평가 시작"])
    assert len(out) == 1
    assert "외국인 5일 누적 순매수 전환" in out[0]["trigger"]
    assert out[0]["action"] == "반도체 재평가 시작"
    assert out[0]["kind"] == "opportunity"     # "전환" 힌트


def test_scenarios_string_without_separator_kept_as_trigger() -> None:
    out = ms._coerce_scenarios(["분산일 12건 도달"])
    assert out[0]["trigger"] == "분산일 12건 도달" and out[0]["action"] == ""


def test_scenarios_drop_empty_and_bad_types() -> None:
    assert ms._coerce_scenarios([None, 3, "", {"action": "x"}]) == []
    assert ms._coerce_scenarios(None) == []


def test_scenario_kind_defaults_to_risk() -> None:
    assert ms._coerce_scenarios(["지수 급락 시 → 대기"])[0]["kind"] == "risk"


def test_render_scenario_without_action() -> None:
    s = ms.MarketStance(as_of="d", session="postclose", headline="h", narrative="",
                        rotation_read="", risk_read="", stance="watch",
                        scenarios=[{"trigger": "분산일 12건", "action": "", "kind": "risk"}],
                        facts_md="")
    body = ms.render_stance_notification(s)
    assert "분산일 12건" in body and "→" not in body.split("■ 시나리오")[1]


def test_scenario_kind_prefers_reduce_over_mixed_words() -> None:
    """실측 오분류: '이탈폭 확대 → 방어적 비중 축소' 가 opportunity 로 갔다."""
    out = ms._coerce_scenarios(
        ["갭업이 되밀리며 코스피 20일선 이탈폭이 확대되면 → 분산일 누적 경계, 방어적 비중 축소"]
    )
    assert out[0]["kind"] == "reduce"


def test_scenario_kind_uses_action_over_trigger() -> None:
    out = ms._coerce_scenarios(
        [{"trigger": "지수 급락", "action": "낙폭과대 반등 노려 비중 확대"}]
    )
    assert out[0]["kind"] == "opportunity"


# ===========================================================================
# 신선도 가드 (2026-08-12 사고) — 지수 OHLCV 가 08-07 에서 멈췄는데 breadth·야간선물은
#   실시간이라 "반쯤 신선한" 판세가 나갔다. 실제 KOSPI +3.75% 급반등인데 판세는
#   "지수는 밀렸지만"이라고 서술. 완전히 죽었으면 알아챘을 것을 반쯤 살아서 못 잡았다.
#   → 모르는 걸 아는 척하지 않는다 (투자 7계명 #6).
# ===========================================================================


def _index_ohlcv(db, ticker: str, date: str, close: float) -> None:
    db.execute(
        "INSERT OR REPLACE INTO chart_ohlcv "
        "(ticker, date, open, high, low, close, volume, fetched_at) "
        "VALUES (?,?,?,?,?,?,1000,'2026-08-12T18:00:00')",
        (ticker, date, close, close, close, close),
    )


def test_fresh_index_is_not_flagged(db) -> None:
    _macro(db, "2026-08-12", "KOSPI", index_close=6584.41)
    _index_ohlcv(db, "0001", "2026-08-12", 6584.41)
    f = build_stance_facts("2026-08-12", "postclose")
    assert f.stale_axes == []
    assert f.index_data_date == "2026-08-12"


def test_stale_index_is_flagged(db) -> None:
    """지수 차트가 as_of 보다 낡으면 축 이름과 실제 날짜를 남긴다."""
    _macro(db, "2026-08-12", "KOSPI")
    _index_ohlcv(db, "0001", "2026-08-07", 6258.77)
    db.execute("DELETE FROM chart_ohlcv WHERE ticker='0001' AND date='2026-08-12'")
    f = build_stance_facts("2026-08-12", "postclose")
    assert "index_ohlcv" in f.stale_axes
    assert f.index_data_date == "2026-08-07"


def test_missing_index_chart_is_flagged(db) -> None:
    _macro(db, "2026-08-12", "KOSPI")
    f = build_stance_facts("2026-08-12", "postclose")
    assert "index_ohlcv" in f.stale_axes


def test_stale_warning_appears_at_top_of_md(db) -> None:
    """LLM 이 못 지나치게 사실 md 최상단에 경고를 박는다."""
    _macro(db, "2026-08-12", "KOSPI")
    _index_ohlcv(db, "0001", "2026-08-07", 6258.77)
    md = render_stance_facts_md(build_stance_facts("2026-08-12", "postclose"))
    head = md.split("\n")[:4]
    assert any("낡" in ln or "stale" in ln.lower() or "⚠" in ln for ln in head), head
    assert "2026-08-07" in md


async def test_stale_index_blocks_publication(db, stub_llm, monkeypatch) -> None:
    """핵심 축(지수)이 낡으면 판세를 아예 발행하지 않는다 — 틀린 판세보다 침묵."""
    sent: list[dict] = []

    async def _fake_notify(**kw):
        sent.append(kw)
        return {"channel": "test"}

    monkeypatch.setattr(ms, "notify", _fake_notify)
    _seed_day(db, "2026-08-12")
    # 실제 사고 재현 — 지수 차트가 08-07 에서 멈춘 상태(당일 봉 없음)
    db.execute("DELETE FROM chart_ohlcv WHERE ticker='0001'")
    _index_ohlcv(db, "0001", "2026-08-07", 6258.77)

    out = await ms.run_market_stance("2026-08-12", "postclose")
    assert out is None
    assert sent == []
    assert stub_llm == [], "낡은 데이터로 LLM 을 호출하지도 말 것 (비용 낭비)"


async def test_fresh_index_publishes(db, stub_llm, monkeypatch) -> None:
    sent: list[dict] = []

    async def _fake_notify(**kw):
        sent.append(kw)
        return {"channel": "test"}

    monkeypatch.setattr(ms, "notify", _fake_notify)
    _seed_day(db, "2026-08-12")   # macro·chart 종가 일치 상태

    out = await ms.run_market_stance("2026-08-12", "postclose")
    assert out is not None and len(sent) == 1


def test_snapshot_mismatch_is_flagged_even_when_chart_is_fresh(db) -> None:
    """2026-08-12 사고의 핵심 — 원천은 신선한데 소비 스냅샷이 옛 값을 복사한 경우."""
    _macro(db, "2026-08-12", "KOSPI", index_close=6258.77)   # 08-07 종가를 복사한 상태
    _index_ohlcv(db, "0001", "2026-08-12", 6584.41)          # 원천은 오늘치
    f = build_stance_facts("2026-08-12", "postclose")
    assert f.stale_axes == ["index_snapshot_mismatch"]


def test_matching_snapshot_is_fresh(db) -> None:
    _macro(db, "2026-08-12", "KOSPI", index_close=6584.41)
    _index_ohlcv(db, "0001", "2026-08-12", 6584.41)
    assert build_stance_facts("2026-08-12", "postclose").stale_axes == []


def test_small_rounding_difference_is_tolerated(db) -> None:
    _macro(db, "2026-08-12", "KOSPI", index_close=6584.41)
    _index_ohlcv(db, "0001", "2026-08-12", 6584.60)
    assert build_stance_facts("2026-08-12", "postclose").stale_axes == []


# --- F3. 이평 구조 축 (지수 + 주도 종목, 2026-08-13) -------------------------
#
# 판세에 개별 종목 축이 없어 "삼성전자가 20일선 하단에서 변곡하는 장대양봉" 같은 걸
# 못 보던 자리. 검증 무게중심 = ① 지수·종목에 **같은 렌즈** ② 낡은 차트는 아예 안 씀
# ③ 빠진 종목 수를 **숫자로 남김**(조용히 사라지면 갱신 중단을 아무도 모른다).


@pytest.fixture()
def chart_db(db, monkeypatch):
    """F3 는 collectors.charts.load_ohlcv_from_db 를 거쳐 DB 를 읽는다."""
    from collectors import charts

    monkeypatch.setattr(charts, "get_db", lambda: db)
    return db


def test_index_structure_collected_for_both_markets(chart_db) -> None:
    _macro(chart_db, "2026-08-12", "KOSPI")
    _ohlcv(chart_db, "0001")
    _ohlcv(chart_db, "1001")
    f = build_stance_facts("2026-08-12", "postclose")
    assert [d.name for d in f.structures.indices] == ["코스피", "코스닥"]
    assert all(d.kind == "index" for d in f.structures.indices)


def test_index_structure_reports_order_and_ma20_motion(chart_db) -> None:
    _macro(chart_db, "2026-08-12", "KOSPI")
    _ohlcv(chart_db, "0001")
    d = build_stance_facts("2026-08-12", "postclose").structures.indices[0]
    assert d.daily_order == "bullish_stack"
    assert d.ma20_deviation_pct is not None
    assert d.ma20_motion in ("diverging", "converging", "flat")


def test_leaders_come_from_universe_by_rank(chart_db) -> None:
    _macro(chart_db, "2026-08-12", "KOSPI")
    for i, (tk, nm) in enumerate([("005930", "삼성전자"), ("000660", "SK하이닉스")], start=1):
        _universe(chart_db, "2026-08-12", tk, nm, rank=i)
        _ohlcv(chart_db, tk)
    names = [d.name for d in build_stance_facts("2026-08-12", "postclose").structures.leaders]
    assert names == ["삼성전자", "SK하이닉스"]


def test_leader_axis_is_capped(chart_db) -> None:
    """실을 수 있는 종목 수 상한 — 넘치면 md 예산을 먹고 LLM 이 뭉갠다."""
    _macro(chart_db, "2026-08-12", "KOSPI")
    for i in range(ms._MAX_LEADERS + 3):
        tk = f"90000{i}"
        _universe(chart_db, "2026-08-12", tk, f"종목{i}", rank=i + 1)
        _ohlcv(chart_db, tk)
    leaders = build_stance_facts("2026-08-12", "postclose").structures.leaders
    assert len(leaders) == ms._MAX_LEADERS


def test_stale_chart_is_skipped_not_guessed(chart_db) -> None:
    """차트가 어제까지면 오늘 이평 변곡을 **말하지 않는다** (근거 없으면 None)."""
    _macro(chart_db, "2026-08-12", "KOSPI")
    _universe(chart_db, "2026-08-12", "005930", "삼성전자")
    _ohlcv(chart_db, "005930", end="2026-08-07")     # 5일 낡음
    s = build_stance_facts("2026-08-12", "postclose").structures
    assert s.leaders == []
    assert s.skipped_stale == 1


def test_short_history_is_skipped_with_its_own_counter(chart_db) -> None:
    _macro(chart_db, "2026-08-12", "KOSPI")
    _universe(chart_db, "2026-08-12", "900001", "신규상장")
    _ohlcv(chart_db, "900001", bars=20)
    s = build_stance_facts("2026-08-12", "postclose").structures
    assert s.leaders == []
    assert s.skipped_short == 1 and s.skipped_stale == 0


def test_render_names_skipped_coverage(chart_db) -> None:
    """빠진 종목을 조용히 지우면 '커버리지가 원래 이만큼'으로 읽힌다."""
    _macro(chart_db, "2026-08-12", "KOSPI")
    _ohlcv(chart_db, "0001")
    _universe(chart_db, "2026-08-12", "005930", "삼성전자")
    _ohlcv(chart_db, "005930", end="2026-08-07")
    md = render_stance_facts_md(build_stance_facts("2026-08-12", "postclose"))
    assert "차트 미갱신 1종" in md


def test_total_wipeout_still_warns_instead_of_vanishing(chart_db) -> None:
    """전멸 시 블록을 통째로 생략하면 갱신 중단이 숨는다 — 2026-08-13 사고의 은폐 경로."""
    _macro(chart_db, "2026-08-12", "KOSPI")
    _universe(chart_db, "2026-08-12", "005930", "삼성전자")
    _ohlcv(chart_db, "005930", end="2026-08-07")
    md = render_stance_facts_md(build_stance_facts("2026-08-12", "postclose"))
    assert "산출 0" in md
    assert "이평 구조·변곡을 언급하지 말 것" in md


def test_render_shows_stock_name_never_code(chart_db) -> None:
    """노출 단은 종목명만 (feedback_no_stock_code_in_display)."""
    _macro(chart_db, "2026-08-12", "KOSPI")
    _universe(chart_db, "2026-08-12", "005930", "삼성전자")
    _ohlcv(chart_db, "005930")
    md = render_stance_facts_md(build_stance_facts("2026-08-12", "postclose"))
    assert "삼성전자" in md
    assert "005930" not in md


def test_structure_block_states_the_ma_system(chart_db) -> None:
    """LLM 이 어떤 이평 체계를 읽고 있는지 사실 블록에 명시 (사용자 정의 체계)."""
    _macro(chart_db, "2026-08-12", "KOSPI")
    _ohlcv(chart_db, "0001")
    md = render_stance_facts_md(build_stance_facts("2026-08-12", "postclose"))
    assert "일 7·13·20·60·120" in md and "주 5·10·20" in md and "월 7" in md


def test_structures_survive_to_dict_for_replay(chart_db) -> None:
    _macro(chart_db, "2026-08-12", "KOSPI")
    _ohlcv(chart_db, "0001")
    payload = build_stance_facts("2026-08-12", "postclose").to_dict()
    assert payload["structures"]["indices"][0]["name"] == "코스피"


def test_missing_universe_does_not_break_stance(chart_db) -> None:
    """종목 축이 비어도 판세는 발행된다 (축별 독립 graceful)."""
    _macro(chart_db, "2026-08-12", "KOSPI")
    _ohlcv(chart_db, "0001")
    f = build_stance_facts("2026-08-12", "postclose")
    assert f.structures.leaders == []
    assert f.structures.indices and render_stance_facts_md(f)


# --- F3′. 섹터 RS 신선도 (2026-08-13) ----------------------------------------
#
# 지수와 같은 함정: `sector_rs_snapshot` 행은 매일 생기지만 계산 입력인 ETF 일봉이
# 멈추면 밴드가 며칠 전 시장을 가리킨다. 08-10~08-12 에 실제로 이 상태로 발행됐다.


def test_stale_sector_etf_charts_are_counted(chart_db) -> None:
    _macro(chart_db, "2026-08-12", "KOSPI")
    _sector(chart_db, "2026-08-12", "KOSPI", "반도체", -18.5)
    chart_db.execute(
        "UPDATE sector_rs_snapshot SET etf_ticker = '091160' WHERE sector = '반도체'"
    )
    _ohlcv(chart_db, "091160", end="2026-08-07")      # 5일 낡은 ETF 차트
    f = build_stance_facts("2026-08-12", "postclose")
    assert f.stale_sector_etfs == 1 and f.sector_etf_total == 1


def test_fresh_sector_etf_charts_raise_no_warning(chart_db) -> None:
    _macro(chart_db, "2026-08-12", "KOSPI")
    _sector(chart_db, "2026-08-12", "KOSPI", "반도체", -18.5)
    chart_db.execute(
        "UPDATE sector_rs_snapshot SET etf_ticker = '091160' WHERE sector = '반도체'"
    )
    _ohlcv(chart_db, "091160", end="2026-08-12")
    f = build_stance_facts("2026-08-12", "postclose")
    assert f.stale_sector_etfs == 0
    assert "섹터 회전을 오늘의 사실로" not in render_stance_facts_md(f)


def test_stale_sector_warning_sits_above_the_numbers(chart_db) -> None:
    """경고가 밴드 아래 붙으면 LLM 이 숫자를 먼저 읽고 결론을 굳힌다."""
    _macro(chart_db, "2026-08-12", "KOSPI")
    _sector(chart_db, "2026-08-12", "KOSPI", "반도체", -18.5)
    chart_db.execute(
        "UPDATE sector_rs_snapshot SET etf_ticker = '091160' WHERE sector = '반도체'"
    )
    _ohlcv(chart_db, "091160", end="2026-08-07")
    md = render_stance_facts_md(build_stance_facts("2026-08-12", "postclose"))
    assert md.index("섹터 ETF 1/1종") < md.index("반도체")


def test_stale_sector_does_not_block_publication(chart_db) -> None:
    """섹터 강등은 **차단이 아니다** — stale_axes 에 들어가면 판세가 통째로 안 나간다."""
    _macro(chart_db, "2026-08-12", "KOSPI", index_close=6584.41)
    _index_ohlcv(chart_db, "0001", "2026-08-12", 6584.41)
    _sector(chart_db, "2026-08-12", "KOSPI", "반도체", -18.5)
    chart_db.execute(
        "UPDATE sector_rs_snapshot SET etf_ticker = '091160' WHERE sector = '반도체'"
    )
    _ohlcv(chart_db, "091160", end="2026-08-07")
    f = build_stance_facts("2026-08-12", "postclose")
    assert f.stale_sector_etfs == 1
    assert f.stale_axes == []          # 발행 차단은 핵심 축(지수)에만
