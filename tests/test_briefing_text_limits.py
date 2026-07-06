"""브리핑 텍스트 한계 처리 (2026-07-07 사용자 제보 — "말을 하다가 끊겼어").

원인 2겹:
  ① render 하드 슬라이스(`reason[:80]`)가 문장 중간을 싹둑 — 텔레그램 한도 아님.
  ② `_send_telegram` 에 4096자 분할이 없어 초과 메시지는 통째로 실패(파일 폴백행).
수리 = 문장 경계 클립(+말줄임 표기) + 텔레그램 분할 연속 발송.
"""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, patch

import pytest

os.environ.setdefault("TESTING", "1")

from core.briefing.render import render_positions


# ---------------------------------------------------------------------------
# ① render — 문장 경계 클립 (하드 슬라이스 폐지)
# ---------------------------------------------------------------------------
_LONG_REASON = (
    "필라델피아 반도체 지수(SOX)의 강한 반등과 마이크론, 샌디스크 등 칩 플레이어들의 "
    "강세는 국내 반도체 대형주에 긍정적인 영향을 미칠 것으로 예상됩니다. "
    "특히 지난주 조정으로 인한 저가 매수 기회로 활용 가능하며, 장기적인 관점에서 "
    "월봉 7MA를 타고 오르는 추세가 유효합니다."
)


def _positions_data(reason: str) -> dict:
    return {
        "positions_advice": [
            {"ticker": "005930", "name": "삼성전자", "verdict": "HOLD", "reason": reason}
        ],
        "new_candidates": [
            {"sector": "반도체", "ticker": "000660", "name": "SK하이닉스", "reason": reason}
        ],
        "principles": {},
    }


def test_candidate_reason_not_cut_mid_sentence():
    """신규 후보 reason — 문장 경계에서 끝나거나 말줄임(…) 표기 (중간 뚝 끊김 금지).

    2026-07-07 레이아웃 분리 후: 이유는 종목명 다음 └ 줄에 위치.
    """
    text = render_positions(_positions_data(_LONG_REASON))
    lines = text.splitlines()
    idx = next(i for i, l in enumerate(lines) if "SK하이닉스" in l)
    reason_line = lines[idx + 1]
    assert "└" in reason_line
    assert reason_line.rstrip().endswith(("다.", "…")), reason_line
    assert len(reason_line) > 80  # 기존 80자 슬라이스보다 충분히 길게


def test_short_reason_untouched():
    """짧은 reason 은 그대로 (클립 미발동)."""
    text = render_positions(_positions_data("실적 호조."))
    assert "실적 호조." in text
    assert "…" not in text.split("신규 매수 후보")[1].splitlines()[1]


# ---------------------------------------------------------------------------
# ② _send_telegram — 4096 초과 분할 연속 발송
# ---------------------------------------------------------------------------
async def test_telegram_long_message_split(monkeypatch):
    """4096자 초과 메시지 → 줄 경계로 분할해 순차 발송, 전부 200 이면 True."""
    from core.notification import service as svc

    monkeypatch.setattr(svc, "env", lambda k: {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}.get(k))
    sent: list[str] = []

    class _Resp:
        status_code = 200
        text = "ok"

    class _Client:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None):
            sent.append(json["text"])
            return _Resp()

    monkeypatch.setattr(svc.httpx, "AsyncClient", _Client)

    long_msg = "\n".join(f"{i:04d} 줄 내용입니다" for i in range(600))  # > 4096자
    ok = await svc._send_telegram(long_msg)
    assert ok is True
    assert len(sent) >= 2, "분할 발송 안 됨"
    assert all(len(s) <= 4096 for s in sent)
    # 내용 보존 (이어서 마저 발송)
    assert "0000 줄 내용입니다" in sent[0]
    assert "0599 줄 내용입니다" in sent[-1]


# ---------------------------------------------------------------------------
# ②-b 가상매매 보유 배선 — briefing 이 레거시 sim_positions 만 읽어 '보유 없음' 나오던 구멍
# ---------------------------------------------------------------------------
def test_load_positions_includes_paper_holdings(monkeypatch):
    """account_positions(가상매매 정본) 보유가 briefing positions 에 합류 (2026-07-07).

    실측: 삼성전자우/SK하이닉스/테스 보유 중인데 브리핑은 '보유 없음' — 레거시
    watch/sim_positions 만 읽던 배선 구멍.
    """
    from pipelines.market_briefing_pre.stages import load_positions as lp

    class _FakeDB:
        def fetch_all(self, sql, params=()):
            if "account_positions" in sql:
                return [{"account_id": "kr_long"}]
            return []  # 레거시 watch/sim 빈 값

    monkeypatch.setattr(lp, "get_db", lambda: _FakeDB())
    monkeypatch.setattr(
        "core.account.holdings.get_holdings",
        lambda aid, **k: [{
            "account_id": aid, "ticker": "005935", "display_name": "삼성전자우",
            "track": "A", "shares": 26.15, "avg_price": 218500.0, "weight": 0.057,
            "tranche_count": 1, "eval_price": 224000.0, "priced": True,
            "unrealized_pnl_krw": 143000.0, "unrealized_pct": 2.52,
            "realized_pnl_krw": 0.0, "opened_at": "2026-06-17", "holding_days": 20,
        }],
    )
    paper = lp._load_paper_holdings()
    assert len(paper) == 1
    h = paper[0]
    assert h["name"] == "삼성전자우"
    assert h["unrealized_pct"] == 2.52
    assert h["holding_days"] == 20


# ---------------------------------------------------------------------------
# ③ 신규 후보 결정론 메뉴 — LLM 학습 지식 회귀(유명 대형주만 추천) 구조 수리
# ---------------------------------------------------------------------------
_FAKE_VIEW = {
    "tracks": [
        {"track": "B", "label": "단기", "stages": [
            {"stage": "watching", "count": 1, "items": [
                {"ticker": "131970", "display_name": "테스나", "concept": "leader",
                 "change_pct": 5.2, "is_dual": True, "sources": ["trade_value", "volume_bull"]},
            ]},
        ]},
    ],
    "interest": {"count": 2, "concepts": [
        {"concept": "leader", "label": "주도주", "items": [
            {"ticker": "036930", "display_name": "피케이홀딩스... 아님 주성엔지니어링", "concept": "leader",
             "change_pct": 3.1, "is_dual": False, "sources": ["trade_value"]},
        ]},
        {"concept": "pullback", "label": "눌림", "items": [
            {"ticker": "000660", "display_name": "SK하이닉스", "concept": "pullback",
             "change_pct": -1.2, "is_dual": False, "sources": ["trade_value"]},
        ]},
    ]},
}


def test_candidate_menu_md_from_curation(monkeypatch):
    """메뉴 = 큐레이션 실측 종목 (코드 병기 — LLM 입력) + 컨셉/단계 라벨."""
    import core.watchlist_view as wv

    monkeypatch.setattr(wv, "watchlist_funnel_view", lambda **k: _FAKE_VIEW)
    md = wv.render_candidate_menu_md()
    assert md is not None
    assert "테스나(131970)" in md
    assert "주도주" in md and "눌림" in md
    assert "매수대기" in md or "watching" not in md  # 단계 라벨은 한국어


def test_candidate_menu_md_empty_returns_none(monkeypatch):
    import core.watchlist_view as wv

    monkeypatch.setattr(
        wv, "watchlist_funnel_view",
        lambda **k: {"tracks": [], "interest": {"count": 0, "concepts": []}},
    )
    assert wv.render_candidate_menu_md() is None


def test_briefing_prompt_includes_candidate_menu():
    """briefing 유저 프롬프트에 후보 메뉴 섹션 주입 (템플릿 {candidates_menu})."""
    from pipelines.market_briefing_pre.stages.analyze import _format_user_prompt

    out = _format_user_prompt(
        overnight_us={}, macro={}, night_futures={}, news=[],
        positions={}, principles={},
        candidates_menu="- 테스나(131970) +5.2% [주도주]",
    )
    assert "테스나(131970)" in out


def test_log_fallback_strips_html_links():
    """텔레그램용 <a> 링크가 DB 로그·파일 폴백에는 plain 으로 — 웹앱 알림 탭 태그 노출 방지."""
    from core.notification.service import _strip_html_for_log

    html_msg = '1. ⬆️‼️ <a href="http://n/1">나스닥 반등</a>\n   └ 긍정적'
    plain = _strip_html_for_log(html_msg)
    assert "<a" not in plain and "</a>" not in plain
    assert "나스닥 반등" in plain
    assert "http://n/1" in plain  # 링크 자체는 보존 (텍스트로)


def test_format_message_preserves_anchor_tags():
    """_format_message — body 전체 escape 속에서 render 가 심은 <a> 링크만 보존.

    (기존엔 전부 escape → 태그 원문이 텔레그램에 노출될 뻔한 함정.)
    """
    from core.notification.service import _format_message

    body = '1. ⬆️‼️ <a href="http://n/1">나스닥 &amp; 반등</a>\n2. 일반 <괄호> 텍스트'
    msg = _format_message("market_briefing_pre", "제목", body)
    assert '<a href="http://n/1">나스닥 &amp; 반등</a>' in msg  # 링크 태그 생존
    assert "&lt;괄호&gt;" in msg  # 그 외 <> 는 여전히 escape (HTML 파손 방지)


async def test_telegram_short_message_single_post(monkeypatch):
    from core.notification import service as svc

    monkeypatch.setattr(svc, "env", lambda k: {"TELEGRAM_BOT_TOKEN": "t", "TELEGRAM_CHAT_ID": "c"}.get(k))
    sent: list[str] = []

    class _Resp:
        status_code = 200
        text = "ok"

    class _Client:
        def __init__(self, *a, **k): ...
        async def __aenter__(self): return self
        async def __aexit__(self, *a): return False
        async def post(self, url, json=None):
            sent.append(json["text"])
            return _Resp()

    monkeypatch.setattr(svc.httpx, "AsyncClient", _Client)
    ok = await svc._send_telegram("짧은 메시지")
    assert ok is True and len(sent) == 1
