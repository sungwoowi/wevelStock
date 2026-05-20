"""INFRA-FUNDAMENTAL-DATA-001 — compose.build_pipeline_prompt 의 [5] fundamental 블록 주입 검증.

chart_data_md ([4]) 패턴 미러. chart 직후 RAG 직전 위치 + 빈 값 silent skip +
cache_control 없음 (24h 갱신).
"""
from __future__ import annotations

import pytest

from core.knowledge.compose import build_pipeline_prompt


_FUND_MD = (
    "## [5] 펀더멘털 데이터 (INFRA-FUNDAMENTAL-DATA-001)\n\n"
    "**Ticker**: 005930 | EPS TTM=9512"
)
_CHART_MD = (
    "## [4] 차트 데이터 (INFRA-CHART-DATA-001)\n\n"
    "**Ticker**: 005930 | open=80,500"
)


async def test_fundamental_data_md_kwarg_injects_block() -> None:
    bundle = await build_pipeline_prompt(
        context_id="test_ctx",
        persona_path=None,
        include_shared_canon=False,
        include_memory=False,
        market_snapshot_md=None,
        chart_data_md=None,
        fundamental_data_md=_FUND_MD,
        response_rules=None,
    )
    matched = [
        b for b in bundle.blocks
        if "INFRA-FUNDAMENTAL-DATA-001" in b.get("text", "")
    ]
    assert len(matched) == 1
    # cache_control 없음 (24h 갱신, 변동 가능)
    assert "cache_control" not in matched[0]
    # 본문 보존
    assert "005930" in matched[0]["text"]
    assert "EPS TTM=9512" in matched[0]["text"]


async def test_fundamental_data_md_none_skips_block() -> None:
    bundle = await build_pipeline_prompt(
        context_id="test_ctx",
        persona_path=None,
        include_shared_canon=False,
        include_memory=False,
        market_snapshot_md=None,
        chart_data_md=None,
        fundamental_data_md=None,
        response_rules=None,
    )
    for b in bundle.blocks:
        assert "INFRA-FUNDAMENTAL-DATA-001" not in b.get("text", "")


async def test_chart_and_fundamental_order_4_then_5() -> None:
    """[4] chart → [5] fundamental → [6] RAG 순서. RAG 는 query 없으니 빈 자리."""
    bundle = await build_pipeline_prompt(
        context_id="test_ctx",
        persona_path=None,
        include_shared_canon=False,
        include_memory=False,
        market_snapshot_md="### USD/KRW 1487",
        chart_data_md=_CHART_MD,
        fundamental_data_md=_FUND_MD,
        response_rules=None,
    )
    blocks = bundle.blocks
    chart_idx = next(
        i for i, b in enumerate(blocks)
        if "INFRA-CHART-DATA-001" in b.get("text", "")
    )
    fund_idx = next(
        i for i, b in enumerate(blocks)
        if "INFRA-FUNDAMENTAL-DATA-001" in b.get("text", "")
    )
    assert fund_idx == chart_idx + 1


async def test_fundamental_data_md_empty_string_skips_block() -> None:
    """빈 문자열 → 주입 X (falsy)."""
    bundle = await build_pipeline_prompt(
        context_id="test_ctx",
        persona_path=None,
        include_shared_canon=False,
        include_memory=False,
        market_snapshot_md=None,
        chart_data_md=None,
        fundamental_data_md="",
        response_rules=None,
    )
    for b in bundle.blocks:
        assert "INFRA-FUNDAMENTAL-DATA-001" not in b.get("text", "")
