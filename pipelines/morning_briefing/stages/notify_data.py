"""Stage: notify_data — 순수 데이터 팩트만 텔레그램/파일로 발송.

이 메시지의 성격:
- 해석 없음, 수치만
- 출처 명시 (KIS / yfinance)
- 간결한 표 형식
"""
from __future__ import annotations

from typing import Any

from core.logging import get_logger
from core.notification import notify
from pipelines._base import Stage, StageContext, StageResult

log = get_logger(__name__)


def _fmt_pct(v: float | int | None) -> str:
    if v is None:
        return "?"
    try:
        return f"{float(v):+.2f}%"
    except (ValueError, TypeError):
        return "?"


def _fmt_num(v: Any, decimals: int = 2) -> str:
    if v is None or v == "":
        return "?"
    try:
        return f"{float(v):,.{decimals}f}"
    except (ValueError, TypeError):
        return str(v)


def _fmt_money_m(v: int | None) -> str:
    """백만원(M) 단위 입력값을 조/억 표기로 변환.

    단위 변환:
    - 1조 = 1,000,000 백만 (10^6 M)
    - 1억 = 100 백만 (10^2 M)
    """
    if not v:
        return "0"
    abs_v = abs(v)
    sign = "+" if v > 0 else "-"
    if abs_v >= 1_000_000:
        return f"{sign}{abs_v / 1_000_000:.2f}조"
    if abs_v >= 100:
        return f"{sign}{abs_v / 100:,.0f}억"
    return f"{sign}{abs_v}M원"


def _build_data_message(market_data: dict) -> str:
    lines: list[str] = []
    lines.append("[시장 데이터 스냅샷]")
    lines.append(f"출처: KIS + yfinance | 기준: {market_data.get('date', '?')}")
    lines.append("")

    # 국내지수
    dom = market_data.get("indices_domestic", {})
    kospi = dom.get("kospi", {})
    kosdaq = dom.get("kosdaq", {})
    lines.append("== 국내 지수 ==")
    lines.append(
        f"KOSPI  {_fmt_num(kospi.get('value'))} ({_fmt_pct(kospi.get('change_pct'))})"
    )
    lines.append(
        f"KOSDAQ {_fmt_num(kosdaq.get('value'))} ({_fmt_pct(kosdaq.get('change_pct'))})"
    )
    lines.append("")

    # 해외지수
    ov = market_data.get("indices_overseas", {})
    if ov and not ov.get("error"):
        lines.append("== 해외 지수 ==")
        for name, label in [
            ("nasdaq", "나스닥"),
            ("philly_semi", "필라델피아반도체"),
            ("sp500", "S&P500"),
            ("dow", "다우"),
            ("gold", "금"),
            ("dxy", "달러인덱스"),
            ("us_10y", "미10년물"),
            ("vix", "VIX"),
        ]:
            v = ov.get(name, {})
            if "price" in v:
                lines.append(f"{label} {_fmt_num(v['price'])} ({_fmt_pct(v['change_pct'])})")
        lines.append("")

    # 수급
    inv = market_data.get("investor_flow", {})
    for mkt, label in [("kospi", "KOSPI 외국인+기관 상위30 합산"), ("kosdaq", "KOSDAQ 외국인+기관 상위30 합산")]:
        agg = inv.get(mkt, {}).get("aggregated", {})
        if agg.get("count"):
            frgn = agg.get("foreign_net_amount_m_sum", 0)
            orgn = agg.get("institution_net_amount_m_sum", 0)
            finv = agg.get("fin_invest_net_amount_m_sum", 0)
            lines.append(f"== {label} ==")
            lines.append(
                f"외국인 {_fmt_money_m(frgn)} / 기관 {_fmt_money_m(orgn)} / 금융투자 {_fmt_money_m(finv)}"
            )
            lines.append("")

    # 강세 섹터
    strong = market_data.get("strong_sectors", [])
    if strong:
        lines.append(f"== 강세 섹터 ({len(strong)}) ==")
        for s in strong[:8]:
            lines.append(f"{s.get('name', '?')} {_fmt_pct(s.get('change_pct'))}")
        lines.append("")

    # 주도주
    ls = market_data.get("leading_stocks", {})
    stats = ls.get("stats", {})
    for mkt, label, limit in [("kospi", "KOSPI 주도주", 10), ("kosdaq", "KOSDAQ 주도주", 5)]:
        stocks = ls.get(mkt, [])
        if stocks:
            matched = stats.get(f"{mkt}_matched", 0)
            filled = stats.get(f"{mkt}_fill", 0)
            suffix = f" (조건충족 {matched} + 거래대금 채움 {filled})" if filled else f" (조건충족 {matched})"
            lines.append(f"== {label} {limit}개{suffix} ==")
            for s in stocks:
                mark = "*" if s.get("match") == "meets_criteria" else " "
                tier = f" [{s.get('cap_tier')}]" if s.get("cap_tier") else ""
                lines.append(
                    f"{mark}{s.get('name', '?')}({s.get('ticker', '')}) "
                    f"{_fmt_pct(s.get('change_pct'))}{tier}"
                )
            lines.append("")

    return "\n".join(lines).rstrip()


class NotifyDataStage(Stage):
    stage_id = "notify_data"
    stage_type = "act"

    async def run(self, ctx: StageContext) -> StageResult:
        market_data = ctx.get_stage_data("collect_market")
        if not market_data:
            return StageResult(
                stage_id=self.stage_id,
                status="warning",
                data={"skipped": True, "reason": "no market data"},
            )

        body = _build_data_message(market_data)

        result = await notify(
            team_id=ctx.pipeline_id,
            level="info",
            title=f"[{ctx.date}] 시장 데이터",
            body=body,
            related_run_id=ctx.run_id,
            related_target="global",
        )

        log.info(
            "data_notified",
            pipeline=ctx.pipeline_id,
            channel=result.get("channel"),
        )

        return StageResult(
            stage_id=self.stage_id,
            status="ok",
            data={
                "channel": result.get("channel"),
                "telegram_ok": result.get("telegram_ok", False),
                "char_count": len(body),
            },
        )
