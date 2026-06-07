"""MARKET-VIEW-SYNTHESIS-001 — 시장관 종합 collector 테스트.

M1 (결정론 코어):
  - entry_posture 매트릭스 (6 regime × DD kill switch × breadth)
  - build_rotation_stage1 (다일 RS 변화 → to/from/direction/strength, 첫날 graceful)
  - synthesize_market_view 결정론 (고정 입력 → 고정 leading/fading/posture/one_liner)
  - one_liner 빈 축 생략
  - DB round-trip (sector_rs_snapshot + market_view_snapshot)
  - load_prev_sector_rs 다일 윈도우 선택
  - build_market_view DB-first (hit / 첫날 graceful)

LLM 실호출 금지 — M1 은 cross_check=False 또는 결정론 경로만 (Stage 2 는 M2 mock).
"""
from __future__ import annotations

import pytest

from collectors import market_view as mv
from collectors import sector_rs as srs
from collectors.market_view import (
    MarketView,
    Rotation,
    build_one_liner,
    build_rotation_stage1,
    entry_posture,
    synthesize_market_view,
)
from collectors.sector_rs import (
    SectorRS,
    load_prev_sector_rs,
    load_sector_rs_snapshot,
    persist_sector_rs,
)
from core.db.connection import Database, reset_db


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def isolated_db(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Database:
    """temp DB + market_view / sector_rs 모듈 get_db 패치."""
    reset_db()
    db = Database(tmp_path / "test_market_view.sqlite")
    monkeypatch.setattr(mv, "get_db", lambda: db)
    monkeypatch.setattr(srs, "get_db", lambda: db)
    mv.reload_market_view_config()
    return db


def _rs(sector: str, score: float) -> SectorRS:
    # etf_ticker = sector 명 (테스트 내 distinct 보장). config sector_labels 에 없는 키라
    # 라벨은 raw 섹터명으로 fallback → 기존 단언("방산"/"2차전지" 등) 유지.
    return SectorRS(
        sector=sector, etf_ticker=sector, rs_score=score,
        return_60d=0.0, kospi_return_60d=0.0, rs_ratio=0.0,
    )


def _macro(regime_inputs: dict) -> dict:
    """classify_market_regime 가 읽는 최소 dict."""
    return {
        "position": regime_inputs.get("position"),
        "trend": regime_inputs.get("trend"),
        "ma20_slope_pct_5d": regime_inputs.get("slope"),
        "breadth_ratio": regime_inputs.get("breadth"),
        "distribution_count_25d": regime_inputs.get("dd", 0),
    }


# ---------------------------------------------------------------------------
# entry_posture 매트릭스
# ---------------------------------------------------------------------------


def test_entry_posture_kill_switch_forces_defensive():
    # 강세 + 폭 강함이어도 분산일 4건이면 방어 강제
    assert entry_posture("strong_bull", 0.70, 4) == "defensive"
    assert entry_posture("moderate_bull", 0.60, 5) == "defensive"


def test_entry_posture_parabolic_and_bears_defensive():
    assert entry_posture("parabolic", 0.70, 0) == "defensive"
    assert entry_posture("strong_bear", 0.30, 0) == "defensive"
    assert entry_posture("moderate_bear", 0.45, 0) == "defensive"


def test_entry_posture_aggressive_requires_strong_breadth_low_dd():
    assert entry_posture("strong_bull", 0.60, 0) == "aggressive"
    assert entry_posture("moderate_bull", 0.55, 2) == "aggressive"
    # 폭 약하면 중립
    assert entry_posture("moderate_bull", 0.40, 0) == "neutral"
    # breadth 결측이면 중립 (추정 금지)
    assert entry_posture("strong_bull", None, 0) == "neutral"


def test_entry_posture_sideways_neutral():
    assert entry_posture("sideways", 0.50, 0) == "neutral"


# ---------------------------------------------------------------------------
# rotation Stage 1
# ---------------------------------------------------------------------------


def test_rotation_first_day_graceful_none():
    today = [_rs("반도체", 8.0), _rs("방산", 7.0)]
    rot, change_map = build_rotation_stage1(today, None)
    assert rot.strength == "none"
    assert rot.direction == "—"
    assert rot.method == "deterministic"
    assert change_map == {}


def test_rotation_detects_direction_from_to():
    prev = [_rs("2차전지", 8.0), _rs("방산", 5.0), _rs("반도체", 6.0)]
    today = [_rs("방산", 8.0), _rs("반도체", 6.2), _rs("2차전지", 6.0)]  # 방산 +3 유입, 2차전지 -2 유출
    rot, change_map = build_rotation_stage1(today, prev)
    assert "방산" in rot.to_sectors
    assert "2차전지" in rot.from_sectors
    assert rot.direction == "2차전지→방산"
    assert rot.strength == "strong"          # max_abs=3 ≥ strong_change(1.5)
    assert change_map["방산"] == 3.0
    assert change_map["2차전지"] == -2.0


def test_rotation_mild_when_small_moves():
    prev = [_rs("반도체", 7.0), _rs("방산", 6.0)]
    today = [_rs("반도체", 7.6), _rs("방산", 5.4)]  # +0.6 / -0.6 (≥ threshold 0.5, < strong 1.5)
    rot, _ = build_rotation_stage1(today, prev)
    assert rot.strength == "mild"
    assert rot.direction == "방산→반도체"


def test_rotation_no_significant_move_none():
    prev = [_rs("반도체", 7.0), _rs("방산", 6.0)]
    today = [_rs("반도체", 7.1), _rs("방산", 5.9)]  # ±0.1 < threshold 0.5
    rot, _ = build_rotation_stage1(today, prev)
    assert rot.strength == "none"
    assert rot.direction == "—"


# ---------------------------------------------------------------------------
# synthesize_market_view 결정론
# ---------------------------------------------------------------------------


def test_synthesize_deterministic_full():
    macro = _macro({"position": "above_both", "trend": "uptrend", "slope": 1.0, "breadth": 0.60, "dd": 0})
    prev = [_rs("2차전지", 8.0), _rs("방산", 5.0)]
    today = [_rs("방산", 8.0), _rs("2차전지", 6.0)]
    view = synthesize_market_view(macro, today, prev, market="KOSPI", date_str="2026-06-06")

    assert view.regime == "strong_bull"
    assert view.entry_posture == "aggressive"   # strong_bull + breadth 0.60 + dd 0
    assert view.leading_sectors[0]["sector"] == "방산"
    assert view.rotation.direction == "2차전지→방산"
    assert "오늘 시장" in view.one_liner
    assert view.source == "computed"
    assert view.confidence == 70


def _news_digest(tone: str, *, themes=None, source: str = "computed"):
    """C2 흡수 테스트용 경량 NewsDigest."""
    from collectors.news_source import NewsDigest

    return NewsDigest(
        date="2026-06-06", scope="market", tone=tone,
        top_themes=themes or [], source=source,
    )


def test_synthesize_absorbs_news_tone_into_reasons_and_one_liner():
    """C2 — 시장 scope digest tone·top_themes 가 reasons + one_liner 에 흡수 (NEWS-SOURCE-001 M5)."""
    macro = _macro({"position": "above_both", "trend": "uptrend", "slope": 1.0, "breadth": 0.60, "dd": 0})
    today = [_rs("방산", 8.0), _rs("2차전지", 6.0)]
    digest = _news_digest(
        "bullish",
        themes=[{"theme": "금리인하", "time_axis": "structural_trend", "trigger_titles": ["t1"]}],
    )
    view = synthesize_market_view(
        macro, today, None, market="KOSPI", date_str="2026-06-06", news_digest=digest,
    )
    assert any("뉴스 톤" in r and "호재 우세" in r for r in view.reasons)
    assert "금리인하" in " ".join(view.reasons)
    assert "뉴스 호재 우세" in view.one_liner


def test_synthesize_news_none_backward_compatible():
    """C2 — news_digest=None (기본) → 뉴스 reason 없음 (하위호환)."""
    macro = _macro({"position": "above_both", "trend": "uptrend", "slope": 1.0, "breadth": 0.60, "dd": 0})
    view = synthesize_market_view(macro, [_rs("방산", 8.0)], None, market="KOSPI", date_str="2026-06-06")
    assert not any("뉴스 톤" in r for r in view.reasons)
    assert "뉴스" not in view.one_liner


def test_synthesize_empty_news_not_absorbed():
    """C2 — source='empty' digest → 흡수 생략 (중립 톤 노이즈 방지)."""
    macro = _macro({"position": "above_both", "trend": "uptrend", "slope": 1.0, "breadth": 0.60, "dd": 0})
    digest = _news_digest("neutral", source="empty")
    view = synthesize_market_view(
        macro, [_rs("방산", 8.0)], None, market="KOSPI", date_str="2026-06-06", news_digest=digest,
    )
    assert not any("뉴스 톤" in r for r in view.reasons)


def test_sector_labels_clean_etf_brand_names():
    """ETF 브랜드명 → 친화 섹터명 (config sector_labels, ticker 기준). one_liner·leading·rotation 일관."""
    # 실 ticker 사용 (config/market_view.yaml sector_labels): 139260=금융, 244580=바이오
    def _rs_t(ticker, score):
        return SectorRS(sector="브랜드명-무시", etf_ticker=ticker, rs_score=score,
                        return_60d=0.0, kospi_return_60d=0.0, rs_ratio=0.0)
    macro = _macro({"position": "above_both", "trend": "uptrend", "slope": 1.0, "breadth": 0.60})
    prev = [_rs_t("244580", 8.0), _rs_t("139260", 5.0)]   # 바이오 high, 금융 low
    today = [_rs_t("139260", 8.0), _rs_t("244580", 6.0)]  # 금융 +3 유입, 바이오 -2 유출
    view = synthesize_market_view(macro, today, prev, market="KOSPI", date_str="2026-06-06")
    # ETF 원명("브랜드명-무시")이 아니라 친화 섹터명
    assert view.leading_sectors[0]["sector"] == "금융"
    assert view.rotation.direction == "바이오→금융"
    assert "금융" in view.one_liner
    assert "브랜드명-무시" not in view.one_liner


def test_synthesize_first_day_no_rotation():
    macro = _macro({"position": "above_both", "trend": "uptrend", "slope": 0.5, "breadth": 0.40, "dd": 0})
    today = [_rs("반도체", 8.0), _rs("방산", 7.0)]
    view = synthesize_market_view(macro, today, None, market="KOSPI", date_str="2026-06-06")
    assert view.rotation.strength == "none"
    assert view.fading_sectors == []
    # 폭 약한 강세 → 중립
    assert view.entry_posture == "neutral"
    # one_liner 에 순환 토막 생략
    assert "순환" not in view.one_liner


# ---------------------------------------------------------------------------
# one_liner 빈 축 생략
# ---------------------------------------------------------------------------


def test_one_liner_omits_empty_rotation():
    rot_none = Rotation(direction="—", strength="none")
    line = build_one_liner("moderate_bull", [{"sector": "반도체", "rs_score": 8.0}], rot_none, "neutral")
    assert "순환" not in line
    assert "주도 반도체" in line
    assert "진입 중립" in line


def test_one_liner_includes_rotation_when_present():
    rot = Rotation(direction="2차전지→방산", strength="mild")
    line = build_one_liner("strong_bull", [{"sector": "방산", "rs_score": 8.0}], rot, "aggressive")
    assert "순환 2차전지→방산" in line


# ---------------------------------------------------------------------------
# DB round-trip
# ---------------------------------------------------------------------------


def test_sector_rs_snapshot_round_trip(isolated_db: Database):
    rows = [_rs("반도체", 8.2), _rs("방산", 7.5)]
    persist_sector_rs("2026-06-06", "KOSPI", rows)
    loaded = load_sector_rs_snapshot("2026-06-06", "KOSPI")
    assert len(loaded) == 2
    assert loaded[0].sector == "반도체"      # rs_score desc
    assert loaded[0].rs_score == 8.2


def test_load_prev_sector_rs_window(isolated_db: Database):
    persist_sector_rs("2026-06-01", "KOSPI", [_rs("반도체", 7.0)])
    persist_sector_rs("2026-06-06", "KOSPI", [_rs("반도체", 8.0)])
    # window_days=5 → 2026-06-06 기준 06-01 이전(<=06-01) 최근 = 06-01
    prev = load_prev_sector_rs("2026-06-06", "KOSPI", window_days=5)
    assert prev is not None
    prev_date, prev_rows = prev
    assert prev_date == "2026-06-01"
    assert prev_rows[0].rs_score == 7.0


def test_load_prev_sector_rs_insufficient_history(isolated_db: Database):
    persist_sector_rs("2026-06-06", "KOSPI", [_rs("반도체", 8.0)])
    # 5일 이전 데이터 없음 → None
    assert load_prev_sector_rs("2026-06-06", "KOSPI", window_days=5) is None


def test_market_view_snapshot_round_trip(isolated_db: Database):
    macro = _macro({"position": "above_both", "trend": "uptrend", "slope": 1.0, "breadth": 0.60, "dd": 1})
    prev = [_rs("2차전지", 8.0), _rs("방산", 5.0)]
    today = [_rs("방산", 8.0), _rs("2차전지", 6.0)]
    view = synthesize_market_view(macro, today, prev, market="KOSPI", date_str="2026-06-06")
    mv.upsert_market_view(view)

    loaded = mv.get_today_view("2026-06-06", "KOSPI")
    assert loaded is not None
    assert loaded.source == "db"
    assert loaded.regime == view.regime
    assert loaded.entry_posture == view.entry_posture
    assert loaded.rotation.direction == "2차전지→방산"
    assert loaded.rotation.to_sectors == ["방산"]
    assert loaded.leading_sectors[0]["sector"] == "방산"
    assert loaded.one_liner == view.one_liner


# ---------------------------------------------------------------------------
# build_market_view DB-first
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_market_view_db_hit(isolated_db: Database, monkeypatch: pytest.MonkeyPatch):
    """오늘 row 가 있으면 compute_market_macro/sector_rs 호출 없이 즉시 반환."""
    called = {"macro": 0, "rs": 0}

    async def _macro_spy(market, **kw):
        called["macro"] += 1
        return _macro({"position": "above_both", "trend": "uptrend", "slope": 1.0, "breadth": 0.60})

    async def _rs_spy(*a, **kw):
        called["rs"] += 1
        return []

    monkeypatch.setattr(mv, "compute_market_macro", _macro_spy)
    monkeypatch.setattr(mv, "compute_sector_rs", _rs_spy)
    monkeypatch.setattr(mv, "_today_kst_str", lambda: "2026-06-06")

    # 미리 오늘 view 적재
    view = MarketView(
        date="2026-06-06", market="KOSPI", regime="strong_bull",
        leading_sectors=[{"sector": "방산", "rs_score": 8.0, "rs_change_nd": None}],
        fading_sectors=[], rotation=Rotation(direction="—"), entry_posture="aggressive",
        one_liner="오늘 시장: 강한 강세 · 주도 방산 · 진입 공격", confidence=70, reasons=[],
    )
    mv.upsert_market_view(view)

    result = await mv.build_market_view("KOSPI")
    assert result.source == "db"
    assert result.entry_posture == "aggressive"
    assert called["macro"] == 0   # DB hit → compute 미호출
    assert called["rs"] == 0


@pytest.mark.asyncio
async def test_build_market_view_first_day_computes(isolated_db: Database, monkeypatch: pytest.MonkeyPatch):
    """오늘 row 없으면 compute → persist → synthesize → upsert. cross_check=False."""
    async def _macro_stub(market, **kw):
        return _macro({"position": "above_both", "trend": "uptrend", "slope": 1.0, "breadth": 0.60, "dd": 0})

    async def _rs_stub(*a, **kw):
        return [_rs("반도체", 8.0), _rs("방산", 7.0)]

    monkeypatch.setattr(mv, "compute_market_macro", _macro_stub)
    monkeypatch.setattr(mv, "compute_sector_rs", _rs_stub)
    monkeypatch.setattr(mv, "_today_kst_str", lambda: "2026-06-06")

    result = await mv.build_market_view("KOSPI", cross_check=False)
    assert result.source == "computed"
    assert result.regime == "strong_bull"
    assert result.rotation.strength == "none"   # 첫날 (prev 없음)
    # sector_rs 가 persist 됐는지
    assert len(load_sector_rs_snapshot("2026-06-06", "KOSPI")) == 2
    # market_view 도 적재
    assert mv.get_today_view("2026-06-06", "KOSPI") is not None


# ---------------------------------------------------------------------------
# M2 — rotation LLM 크로스체크 (Stage 2, mock — 실호출 금지)
# ---------------------------------------------------------------------------


def _stub_llm(agree: bool, reasoning: str = "테스트 근거"):
    """call_llm mock — JSON content 반환. 호출 카운터 부착."""
    calls = {"n": 0}

    async def _fake(*args, **kwargs):
        calls["n"] += 1
        return {"content": f'{{"agree": {str(agree).lower()}, "reasoning": "{reasoning}"}}',
                "tokens_in": 10, "tokens_out": 5, "cost_usd": 0.0}

    return _fake, calls


def _strong_rotation() -> tuple[Rotation, dict]:
    rot = Rotation(direction="2차전지→방산", from_sectors=["2차전지"], to_sectors=["방산"],
                   strength="strong", method="deterministic", agreement="n/a")
    change_map = {"방산": 3.0, "2차전지": -2.0}
    return rot, change_map


@pytest.mark.asyncio
async def test_cross_check_returns_agree(isolated_db: Database, monkeypatch: pytest.MonkeyPatch):
    fake, calls = _stub_llm(True)
    monkeypatch.setattr(mv, "call_llm", fake)
    rot, change_map = _strong_rotation()
    result = await mv.cross_check_rotation_via_llm(
        "KOSPI", "2026-06-06", rot, change_map, window_days=5,
    )
    assert result == {"agree": True, "reasoning": "테스트 근거"}
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_cross_check_caches_daily(isolated_db: Database, monkeypatch: pytest.MonkeyPatch):
    """같은 market|date|direction 재호출 = 캐시 hit, LLM 1회만."""
    fake, calls = _stub_llm(True)
    monkeypatch.setattr(mv, "call_llm", fake)
    rot, change_map = _strong_rotation()
    await mv.cross_check_rotation_via_llm("KOSPI", "2026-06-06", rot, change_map, window_days=5)
    await mv.cross_check_rotation_via_llm("KOSPI", "2026-06-06", rot, change_map, window_days=5)
    assert calls["n"] == 1   # 두 번째는 캐시


@pytest.mark.asyncio
async def test_cross_check_llm_failure_returns_none(isolated_db: Database, monkeypatch: pytest.MonkeyPatch):
    async def _boom(*a, **kw):
        raise RuntimeError("llm down")
    monkeypatch.setattr(mv, "call_llm", _boom)
    rot, change_map = _strong_rotation()
    result = await mv.cross_check_rotation_via_llm("KOSPI", "2026-06-06", rot, change_map, window_days=5)
    assert result is None


@pytest.mark.asyncio
async def test_apply_cross_check_agree_raises_confidence(isolated_db: Database, monkeypatch: pytest.MonkeyPatch):
    fake, _ = _stub_llm(True)
    monkeypatch.setattr(mv, "call_llm", fake)
    rot, _ = _strong_rotation()
    view = MarketView(
        date="2026-06-06", market="KOSPI", regime="strong_bull",
        leading_sectors=[{"sector": "방산", "rs_score": 8.0, "rs_change_nd": 3.0}],
        fading_sectors=[], rotation=rot, entry_posture="aggressive",
        one_liner="...", confidence=70, reasons=["base"],
    )
    prev = [_rs("2차전지", 8.0), _rs("방산", 5.0)]
    today = [_rs("방산", 8.0), _rs("2차전지", 6.0)]
    out = await mv._apply_rotation_cross_check(view, prev, today, config=mv.load_market_view_config())
    assert out.rotation.method == "hybrid"
    assert out.rotation.agreement == "agree"
    assert out.confidence == 80   # 70 + 10
    assert any("일치" in r for r in out.reasons)


@pytest.mark.asyncio
async def test_apply_cross_check_disagree_lowers_confidence(isolated_db: Database, monkeypatch: pytest.MonkeyPatch):
    fake, _ = _stub_llm(False, reasoning="노이즈 수준")
    monkeypatch.setattr(mv, "call_llm", fake)
    rot, _ = _strong_rotation()
    view = MarketView(
        date="2026-06-06", market="KOSPI", regime="strong_bull",
        leading_sectors=[], fading_sectors=[], rotation=rot, entry_posture="aggressive",
        one_liner="...", confidence=70, reasons=["base"],
    )
    prev = [_rs("2차전지", 8.0), _rs("방산", 5.0)]
    today = [_rs("방산", 8.0), _rs("2차전지", 6.0)]
    out = await mv._apply_rotation_cross_check(view, prev, today, config=mv.load_market_view_config())
    assert out.rotation.agreement == "disagree"
    assert out.confidence == 55   # 70 - 15
    assert any("이견" in r for r in out.reasons)
    # 방향은 결정론 앵커 유지 (은폐 X)
    assert out.rotation.direction == "2차전지→방산"


@pytest.mark.asyncio
async def test_apply_cross_check_skips_when_no_rotation(isolated_db: Database, monkeypatch: pytest.MonkeyPatch):
    """strength=none 이면 LLM 호출 0 (검증 대상 없음)."""
    calls = {"n": 0}
    async def _spy(*a, **kw):
        calls["n"] += 1
        return {"content": '{"agree": true}'}
    monkeypatch.setattr(mv, "call_llm", _spy)
    view = MarketView(
        date="2026-06-06", market="KOSPI", regime="sideways",
        leading_sectors=[], fading_sectors=[], rotation=Rotation(direction="—", strength="none"),
        entry_posture="neutral", one_liner="...", confidence=50, reasons=[],
    )
    out = await mv._apply_rotation_cross_check(view, None, [], config=mv.load_market_view_config())
    assert calls["n"] == 0
    assert out.rotation.method == "deterministic"


@pytest.mark.asyncio
async def test_build_market_view_applies_cross_check(isolated_db: Database, monkeypatch: pytest.MonkeyPatch):
    """build_market_view 통합 — det strong rotation + mock agree → hybrid/agree."""
    fake, _ = _stub_llm(True)
    monkeypatch.setattr(mv, "call_llm", fake)
    monkeypatch.setattr(mv, "_today_kst_str", lambda: "2026-06-06")

    async def _macro_stub(market, **kw):
        return _macro({"position": "above_both", "trend": "uptrend", "slope": 1.0, "breadth": 0.60, "dd": 0})
    monkeypatch.setattr(mv, "compute_market_macro", _macro_stub)

    # prev (5일 전) + today 스냅샷 미리 적재 → 순환매 strong 발생
    persist_sector_rs("2026-06-01", "KOSPI", [_rs("2차전지", 8.0), _rs("방산", 5.0)])
    persist_sector_rs("2026-06-06", "KOSPI", [_rs("방산", 8.0), _rs("2차전지", 6.0)])

    result = await mv.build_market_view("KOSPI")
    assert result.rotation.strength == "strong"
    assert result.rotation.method == "hybrid"
    assert result.rotation.agreement == "agree"
    assert result.confidence == 80


# ---------------------------------------------------------------------------
# M3 — get_cached_one_liner + formatter prepend + analyst hook
# ---------------------------------------------------------------------------


def test_get_cached_one_liner_reads_db(isolated_db: Database):
    view = MarketView(
        date="2026-06-06", market="KOSPI", regime="strong_bull",
        leading_sectors=[], fading_sectors=[], rotation=Rotation(direction="—"),
        entry_posture="aggressive", one_liner="오늘 시장: 강한 강세 · 진입 공격",
        confidence=70, reasons=[],
    )
    mv.upsert_market_view(view)
    assert mv.get_cached_one_liner("KOSPI", "2026-06-06") == "오늘 시장: 강한 강세 · 진입 공격"


def test_get_cached_one_liner_none_when_absent(isolated_db: Database):
    assert mv.get_cached_one_liner("KOSPI", "2026-06-06") is None


def test_get_cached_one_liner_respects_prepend_toggle(isolated_db: Database, monkeypatch):
    view = MarketView(
        date="2026-06-06", market="KOSPI", regime="sideways", leading_sectors=[],
        fading_sectors=[], rotation=Rotation(direction="—"), entry_posture="neutral",
        one_liner="오늘 시장: 횡보 · 진입 중립", confidence=50, reasons=[],
    )
    mv.upsert_market_view(view)
    # prepend.enabled=False → None
    monkeypatch.setattr(mv, "load_market_view_config",
                        lambda: {**mv._DEFAULT_CONFIG, "prepend": {"enabled": False}})
    assert mv.get_cached_one_liner("KOSPI", "2026-06-06") is None


@pytest.mark.asyncio
async def test_formatter_prepends_market_view(monkeypatch):
    """format_answer 가 시장관 1줄을 답변 머리에 붙인다 (LLM mock)."""
    from core.intent import formatter as fmt

    monkeypatch.setattr(
        "collectors.market_view.get_cached_one_liner",
        lambda *a, **k: "오늘 시장: 강한 강세 · 주도 반도체 · 진입 공격",
    )

    async def _fake_llm(*a, **k):
        return {"content": "삼성전자는 지금 보류가 좋아요.", "model": "x", "tokens_in": 1,
                "tokens_out": 1, "cost_usd": 0.0, "raw": {}}
    monkeypatch.setattr(fmt, "call_llm", _fake_llm)

    result = await fmt.format_answer(
        "삼성전자 살까?",
        [{"id": "stock_analyst", "text": "보류 권고", "metadata": {}}],
        [],
    )
    assert result.text.startswith("📊 오늘 시장: 강한 강세 · 주도 반도체 · 진입 공격")
    assert "삼성전자는 지금 보류가 좋아요." in result.text


def test_market_view_prefix_empty_on_failure(monkeypatch):
    """캐시 부재/예외 시 prefix 빈 문자열 (답변 막지 않음)."""
    from core.intent import formatter as fmt

    def _boom(*a, **k):
        raise RuntimeError("db down")
    monkeypatch.setattr("collectors.market_view.get_cached_one_liner", _boom)
    assert fmt._market_view_prefix() == ""


@pytest.mark.asyncio
async def test_maybe_build_market_view_md_flag_off():
    """reads_market_view=False → None (market_state_analyzer 외 분석가는 미주입)."""
    from core.inference.run_analyst import AnalystSpec, _maybe_build_market_view_md
    from pathlib import Path

    spec = AnalystSpec(
        id="stock_analyst", display_name="x", learning_dept="", reads=[],
        canon_categories=[], persona_path=Path("x"), model=None, max_tokens=4000,
        temperature=0.4, response_rules=None, reads_market_view=False,
    )
    md, meta = await _maybe_build_market_view_md(spec)
    assert md is None
    assert meta == {"market_view_failures": []}


@pytest.mark.asyncio
async def test_maybe_build_market_view_md_flag_on(monkeypatch):
    """reads_market_view=True → render md + metadata (build_market_view mock)."""
    from core.inference.run_analyst import AnalystSpec, _maybe_build_market_view_md
    from pathlib import Path

    fake_view = MarketView(
        date="2026-06-06", market="KOSPI", regime="strong_bull",
        leading_sectors=[{"sector": "반도체", "rs_score": 8.0, "rs_change_nd": 1.0}],
        fading_sectors=[], rotation=Rotation(direction="2차전지→반도체", strength="mild", method="hybrid", agreement="agree"),
        entry_posture="aggressive", one_liner="오늘 시장: 강한 강세 · 주도 반도체 · 진입 공격",
        confidence=80, reasons=["근거"],
    )

    async def _fake_build(market="KOSPI", **kw):
        return fake_view
    monkeypatch.setattr("collectors.market_view.build_market_view", _fake_build)

    spec = AnalystSpec(
        id="market_state_analyzer", display_name="x", learning_dept="", reads=[],
        canon_categories=[], persona_path=Path("x"), model=None, max_tokens=4000,
        temperature=0.4, response_rules=None, reads_market_view=True,
    )
    md, meta = await _maybe_build_market_view_md(spec)
    assert md is not None
    assert "[7] 시장관 종합" in md
    assert "반도체" in md
    assert meta["market_view"]["entry_posture"] == "aggressive"
    assert meta["market_view"]["rotation_agreement"] == "agree"
