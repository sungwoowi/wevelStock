"""관심종목 funnel read view — 체계적 종목 관리 (TRADE-PLAN-LIFECYCLE 후속).

**IA (2026-06-16 사용자 정정)**: 거래대금/거래량 양봉 상위 = 단순 **후보 바스킷(소스)**.
거기서 골라 **장기(A)·단기(B) 트랙별로** 진입 → 매수대기 → 관심 분류하고, **종목별 매매 시계열
시나리오·전략**(trade_plan / conditional_entry)을 붙인다. 즉 주축은 **트랙 × 단계**, 바스킷은 출처 칩.

조립(신규 테이블 0): 후보 union = `universe_membership` 두 list_type(최근 N일 rolling).
단계 = `load_active_recommendations` 최신 rec funnel_stage (트랙별·승급/감쇠 현재 부합). 관심도 트랙별
(rec 없으면 양 트랙 관심). read-only · LLM·네트워크 0.
"""
from __future__ import annotations

from typing import Any

from collectors.universe_membership import get_list_members, get_stock_name
from core.account.desk_view import _funnel_stage_of, _watching_hint
from core.strategist.recommendation import load_active_recommendations

_LIST_LABELS = {"trade_value": "거래대금 상위", "volume_bull": "거래량 상위"}
_TRACK_LABELS = {"A": "장기", "B": "단기"}
_TRACK_STAGES = ("entering", "watching")  # 트랙별 = 골라서 진입/매수대기 된 것만 (관심은 공용)
_CONCEPT_ORDER = ("leader", "pullback", "base", "unknown")
_CONCEPT_LABELS = {"leader": "주도주", "pullback": "눌림", "base": "바닥·소외", "unknown": "미분류"}


def _rec_index(within_days: int) -> dict[tuple[str, str], Any]:
    """(track, ticker) → 최신 권고 (load_active_recommendations 는 이미 (track,ticker) 최신 1건)."""
    return {(rec.track, rec.ticker): rec for rec in load_active_recommendations(within_days=within_days)}


def _build_item(
    ticker: str, meta: dict[str, Any], sources: list[str], rec: Any
) -> dict[str, Any]:
    """후보 1종 × 한 트랙 → 표시 item (단계 + 소스 바스킷 + 매매 시계열 시나리오 필드)."""
    name = meta.get("name") or get_stock_name(ticker) or ticker
    item: dict[str, Any] = {
        "ticker": ticker,
        "display_name": name,
        "sources": sources,                 # ["trade_value", "volume_bull"]
        "is_dual": len(sources) >= 2,        # 거래대금 ∩ 거래량 양봉 교집합(둘 다)
        "concept": meta.get("concept") or "unknown",  # 차트 컨셉(주도주/눌림/바닥)
        "rank": meta.get("rank"),
        "change_pct": meta.get("change_pct"),
        "funnel_stage": "interest",
        "verdict": None,
        "entry_price": None,
        "stop_loss": None,
        "target_prices": [],
        "watching_entry": None,
        "watching_label": "",
        "stage_scenario": None,             # LLM 발행 진입 시나리오(매수대기/진입)
        "scaled_buy": None,
        "scaled_sell": None,
    }
    if rec is not None:
        stage, _reason = _funnel_stage_of(rec)
        we, wl = _watching_hint(rec)
        plan = rec.data.get("trade_plan") or {}
        item.update(
            funnel_stage=stage,
            verdict=rec.verdict,
            entry_price=rec.entry_price,
            stop_loss=rec.stop_loss,
            target_prices=rec.target_prices,
            watching_entry=we,
            watching_label=wl,
            stage_scenario=rec.data.get("stage_scenario"),
            scaled_buy=plan.get("scaled_buy"),
            scaled_sell=plan.get("scaled_sell"),
        )
    return item


def watchlist_funnel_view(
    *, limit: int = 60, within_days: int = 30, list_window_days: int = 10
) -> dict[str, Any]:
    """관심종목 페이지 — 후보 바스킷(소스 요약) + 트랙별(장기/단기) 단계 그룹(진입▸매수대기▸관심).

    리스트 멤버십 = 최근 list_window_days rolling union(큐레이션). 단계 = 트랙별 최신 rec(승급/감쇠).
    각 item 에 소스 바스킷 + 매매 시계열 시나리오 필드.
    """
    # 1) 후보 풀 = 두 바스킷 union. 리스트별 멤버 1회 조회 → 소스 집합·메타·바스킷 상세(날짜 그룹) 공유.
    sources_of: dict[str, set[str]] = {}
    meta_of: dict[str, dict[str, Any]] = {}
    members_by_list: dict[str, list[dict[str, Any]]] = {}
    for lt in ("trade_value", "volume_bull"):
        members = get_list_members(lt, within_days=list_window_days, limit=limit)
        members_by_list[lt] = members
        for m in members:
            tk = m["ticker"]
            sources_of.setdefault(tk, set()).add(lt)
            meta_of.setdefault(tk, m)

    # 2) 트랙별 최신 권고 인덱스.
    idx = _rec_index(within_days)

    # 3) 트랙(장기/단기) = **골라서 진입/매수대기 된 것만**. 관심은 공용(아래 4).
    track_buckets: dict[str, dict[str, list[dict[str, Any]]]] = {
        tr: {s: [] for s in _TRACK_STAGES} for tr in ("A", "B")
    }
    progressed: set[str] = set()  # 어느 트랙에서든 진입/매수대기 된 종목
    for tk, srcs in sources_of.items():
        for tr in ("A", "B"):
            rec = idx.get((tr, tk))
            if rec is None:
                continue
            stage, _reason = _funnel_stage_of(rec)
            if stage in _TRACK_STAGES:
                track_buckets[tr][stage].append(_build_item(tk, meta_of[tk], sorted(srcs), rec))
                progressed.add(tk)
    tracks = [
        {
            "track": tr,
            "label": _TRACK_LABELS[tr],
            "stages": [{"stage": s, "count": len(track_buckets[tr][s]), "items": track_buckets[tr][s]} for s in _TRACK_STAGES],
        }
        for tr in ("A", "B")
    ]

    # 4) 관심 = 공용 1곳 (어느 트랙에서도 진입/대기 안 된 후보). 컨셉(주도주/눌림/바닥)별 분류.
    by_concept: dict[str, list[dict[str, Any]]] = {c: [] for c in _CONCEPT_ORDER}
    for tk, srcs in sources_of.items():
        if tk in progressed:
            continue
        any_rec = idx.get(("A", tk)) or idx.get(("B", tk))  # 점수 태그용(있으면)
        item = _build_item(tk, meta_of[tk], sorted(srcs), any_rec)
        item["funnel_stage"] = "interest"  # 트랙 미배정 후보
        by_concept.setdefault(item["concept"], []).append(item)
    interest = {
        "count": sum(len(v) for v in by_concept.values()),
        "concepts": [
            {"concept": c, "label": _CONCEPT_LABELS.get(c, c), "count": len(by_concept[c]), "items": by_concept[c]}
            for c in _CONCEPT_ORDER if by_concept.get(c)
        ],
    }

    # 4) 바스킷 = 후보 소스. 멤버를 날짜별 그룹(최신 날짜 우선) + **올바른 정렬**로 노출(펼침용).
    #    거래대금 상위 = 실 거래대금(trade_amount) 내림차순 (KIS rank 는 시장별 로컬값이라 충돌 — 사용 X).
    #    거래량 양봉 = KIS 거래량 순위(rank) 오름차순 (큐레이션 탈락분은 구멍). 표시 번호는 프론트가 순차.
    baskets: list[dict[str, Any]] = []
    for lt in ("trade_value", "volume_bull"):
        members = members_by_list.get(lt, [])
        by_date: dict[str, list[dict[str, Any]]] = {}
        for m in members:
            tk = m["ticker"]
            by_date.setdefault(m.get("date") or "", []).append({
                "ticker": tk,
                "display_name": m.get("name") or get_stock_name(tk) or tk,
                "rank": m.get("rank"),
                "change_pct": m.get("change_pct"),
                "trade_amount": m.get("trade_amount"),
                "volume": m.get("volume"),
                "is_dual": len(sources_of.get(tk, ())) >= 2,  # 거래대금 ∩ 거래량 교집합
            })
        for items in by_date.values():
            if lt == "trade_value":
                items.sort(key=lambda x: x.get("trade_amount") or 0, reverse=True)
            else:
                items.sort(key=lambda x: x.get("rank") if x.get("rank") is not None else 9999)
        dates = [
            {"date": d, "count": len(its), "items": its}
            for d, its in sorted(by_date.items(), reverse=True)
        ]
        baskets.append({
            "list_type": lt,
            "label": _LIST_LABELS[lt],
            "count": len(members),
            "latest_date": dates[0]["date"] if dates else None,
            "dates": dates,
        })
    return {"baskets": baskets, "tracks": tracks, "interest": interest}


_STAGE_KR = {"entered": "진입", "watching": "매수대기"}


def _menu_line(item: dict[str, Any]) -> str:
    """메뉴 한 줄 — 이름(코드) + 등락 + 컨셉/교집합 태그 (LLM 입력이라 코드 병기 OK)."""
    name = item.get("display_name") or item.get("ticker", "?")
    chg = item.get("change_pct")
    chg_s = f" {chg:+.1f}%" if isinstance(chg, (int, float)) else ""
    tags = [_CONCEPT_LABELS.get(item.get("concept"), None)]
    if item.get("is_dual"):
        tags.append("거래대금∩거래량 교집합")
    tag_s = f" [{'·'.join(t for t in tags if t)}]" if any(tags) else ""
    return f"- {name}({item.get('ticker')}){chg_s}{tag_s}"


def render_candidate_menu_md(*, limit_per_group: int = 8) -> str | None:
    """장전 브리핑 `new_candidates` 용 결정론 후보 메뉴 (DB read·LLM 0).

    브리핑 LLM 이 근거 데이터 없이 학습 지식 속 유명 대형주(삼성전자·한미반도체류)로
    회귀하던 문제의 구조 수리 (2026-07-07) — 전일 시장이 실제로 보여준 후보
    (거래대금/거래량 큐레이션 × 차트 컨셉 × funnel 단계)를 메뉴로 주입, 트레이드플랜
    메뉴·cited_scores 구조 주입과 같은 패턴. 후보 0 이면 None (주입 생략, graceful).
    """
    try:
        view = watchlist_funnel_view()
    except Exception:  # noqa: BLE001 — 메뉴 실패가 브리핑을 막지 않음
        return None
    lines: list[str] = []
    # 1) 이미 funnel 단계에 오른 종목 (전략가 판단 有) — 최우선 후보
    for tr in view.get("tracks") or []:
        for st in tr.get("stages") or []:
            items = (st.get("items") or [])[:limit_per_group]
            if not items:
                continue
            stage_kr = _STAGE_KR.get(st.get("stage"), st.get("stage", "?"))
            lines.append(f"### {tr.get('label', tr.get('track', '?'))} 트랙 · {stage_kr}")
            lines.extend(_menu_line(it) for it in items)
    # 2) 관심 공용 — 컨셉(주도주/눌림/바닥)별
    for grp in (view.get("interest") or {}).get("concepts") or []:
        items = (grp.get("items") or [])[:limit_per_group]
        if not items:
            continue
        lines.append(f"### 관심 · {grp.get('label', grp.get('concept', '?'))}")
        lines.extend(_menu_line(it) for it in items)
    if not lines:
        return None
    return "\n".join(lines)
