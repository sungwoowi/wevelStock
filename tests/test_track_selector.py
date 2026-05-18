"""STRATEGY-TRACK-001 — Track Selector 라우팅 단위 테스트.

대상:
- `_scan_strategists()`: manifest input_routing 추출 + `_` prefix 디렉토리 skip
- `select_tracks(user_input, target_meta=None)`:
  * 명시 단축어 매칭 (long: → track_a / swing: → track_b / both: → 모두)
  * 대소문자 무관
  * 단축어 없음 + target_meta 없음 → fallback (Track A)
  * auto.conditions v1 placeholder (target_meta 있어도 v1 = skip)

실제 `agents/strategists/track_a/` + `agents/strategists/track_b/` 매니페스트를 read.
fixture 없이 real 데이터로 검증 (manifest 자체가 SPEC 권위).
"""
from __future__ import annotations

import importlib
from pathlib import Path

import pytest

selector_mod = importlib.import_module("core.strategist.track_selector")
select_tracks = selector_mod.select_tracks
_scan_strategists = selector_mod._scan_strategists


@pytest.fixture(autouse=True)
def _clear_selector_cache():
    """각 테스트마다 _scan_strategists_cached 캐시 클리어 (manifest 변경 반영)."""
    selector_mod._scan_strategists_cached.cache_clear()
    yield
    selector_mod._scan_strategists_cached.cache_clear()


# ---------------------------------------------------------------------------
# _scan_strategists — manifest 인식
# ---------------------------------------------------------------------------


def test_scan_strategists_finds_track_a_and_b() -> None:
    """실 agents/strategists/ 에서 Track A + Track B manifest 인식."""
    strategists = _scan_strategists()
    assert "track_a" in strategists
    assert "track_b" in strategists


def test_scan_strategists_track_a_routing() -> None:
    """Track A 의 input_routing 정합 — long: / core: / wave: + fallback=true."""
    strategists = _scan_strategists()
    routing = strategists["track_a"]
    assert "long:" in routing["shortcuts"]
    assert "core:" in routing["shortcuts"]
    assert "wave:" in routing["shortcuts"]
    assert routing["fallback"] is True


def test_scan_strategists_track_b_routing() -> None:
    """Track B 의 input_routing 정합 — swing: / short: / trigger: + fallback=false."""
    strategists = _scan_strategists()
    routing = strategists["track_b"]
    assert "swing:" in routing["shortcuts"]
    assert "short:" in routing["shortcuts"]
    assert "trigger:" in routing["shortcuts"]
    assert routing["fallback"] is False


def test_scan_strategists_skips_underscore_dirs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`_` prefix 디렉토리 (예: _template) 는 skip."""
    # 임시 디렉토리에 정상 + _ prefix 두 개 만들고 STRATEGISTS_DIR 교체
    (tmp_path / "track_real").mkdir()
    (tmp_path / "track_real" / "manifest.yaml").write_text(
        "id: track_real\ninput_routing:\n  shortcuts:\n    explicit: ['real:']\n  fallback: true\n",
        encoding="utf-8",
    )
    (tmp_path / "_template").mkdir()
    (tmp_path / "_template" / "manifest.yaml").write_text(
        "id: should_not_be_seen\ninput_routing:\n  shortcuts:\n    explicit: ['nope:']\n  fallback: true\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(selector_mod, "STRATEGISTS_DIR", tmp_path)
    selector_mod._scan_strategists_cached.cache_clear()

    strategists = _scan_strategists()
    assert "track_real" in strategists
    assert "should_not_be_seen" not in strategists


def test_scan_strategists_missing_dir_returns_empty(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """STRATEGISTS_DIR 자체가 존재 안 하면 빈 dict."""
    missing = tmp_path / "does_not_exist"
    monkeypatch.setattr(selector_mod, "STRATEGISTS_DIR", missing)
    selector_mod._scan_strategists_cached.cache_clear()
    assert _scan_strategists() == {}


# ---------------------------------------------------------------------------
# select_tracks — 단축어 매칭
# ---------------------------------------------------------------------------


def test_select_tracks_long_routes_to_track_a() -> None:
    assert select_tracks("long: 삼성전자 어때") == ["track_a"]


def test_select_tracks_core_routes_to_track_a() -> None:
    assert select_tracks("core: 카카오") == ["track_a"]


def test_select_tracks_swing_routes_to_track_b() -> None:
    assert select_tracks("swing: 삼성전자") == ["track_b"]


def test_select_tracks_short_routes_to_track_b() -> None:
    assert select_tracks("short: 카카오") == ["track_b"]


def test_select_tracks_trigger_routes_to_track_b() -> None:
    assert select_tracks("trigger: NAVER") == ["track_b"]


# ---------------------------------------------------------------------------
# select_tracks — both:
# ---------------------------------------------------------------------------


def test_select_tracks_both_routes_to_all() -> None:
    """both: 단축어 → 모든 전략가 (정렬, fallback 여부 무관)."""
    result = select_tracks("both: 삼성전자")
    assert "track_a" in result
    assert "track_b" in result
    # 정렬된 순서
    assert result == sorted(result)


# ---------------------------------------------------------------------------
# select_tracks — 대소문자 무관
# ---------------------------------------------------------------------------


def test_select_tracks_uppercase_shortcut() -> None:
    """SWING: / LONG: 등 대문자도 매칭 (lowercase 정규화)."""
    assert select_tracks("SWING: 카카오") == ["track_b"]
    assert select_tracks("Long: 삼성전자") == ["track_a"]
    assert select_tracks("BOTH: 삼성전자") == sorted(["track_a", "track_b"])


def test_select_tracks_leading_whitespace_stripped() -> None:
    """앞 공백 제거 후 매칭."""
    assert select_tracks("   swing: 카카오") == ["track_b"]
    assert select_tracks("\n\tlong: 삼성전자") == ["track_a"]


# ---------------------------------------------------------------------------
# select_tracks — fallback
# ---------------------------------------------------------------------------


def test_select_tracks_no_shortcut_falls_back_to_track_a() -> None:
    """단축어 없음 + target_meta 없음 → fallback (Track A 만)."""
    assert select_tracks("삼성전자 어때") == ["track_a"]


def test_select_tracks_empty_input_falls_back() -> None:
    """빈 입력도 fallback (Track A)."""
    assert select_tracks("") == ["track_a"]


# ---------------------------------------------------------------------------
# select_tracks — auto.conditions (v1 placeholder)
# ---------------------------------------------------------------------------


def test_select_tracks_target_meta_v1_placeholder() -> None:
    """v1 = target_meta 받아도 auto.conditions 평가 skip → fallback 으로 떨어짐.

    분석가 v2 페르소나 작성 후 활성. 본 테스트는 v1 placeholder 동작 검증.
    """
    target_meta = {
        "monthly_7ma_aligned": True,
        "any_trigger_fired": True,
        "market_cap": 5000000000000,
    }
    # auto.conditions 가 활성이면 ["track_a", "track_b"] 가 나와야 하지만 v1 = skip → fallback
    result = select_tracks("삼성전자 어때", target_meta=target_meta)
    assert result == ["track_a"]


def test_select_tracks_target_meta_empty_dict_falls_back() -> None:
    """빈 dict 도 fallback."""
    assert select_tracks("카카오", target_meta={}) == ["track_a"]


# ---------------------------------------------------------------------------
# select_tracks — 등록된 전략가 0개
# ---------------------------------------------------------------------------


def test_select_tracks_no_strategists_returns_empty(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """STRATEGISTS_DIR 안에 전략가가 0개면 빈 리스트."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    monkeypatch.setattr(selector_mod, "STRATEGISTS_DIR", empty_dir)
    selector_mod._scan_strategists_cached.cache_clear()

    assert select_tracks("long: 삼성전자") == []
    assert select_tracks("both: 카카오") == []
    assert select_tracks("아무거나") == []
