"""Anchor 산출 — WAVE-ALPHA-001 sub-cycle 14.2 정식.

stock_analyst α 3 timeframe (daily/weekly/monthly) 발행을 위한 anchor A·B·C 결정.

흐름 (canon WA1·WA2·WA3·WA5·WX1 정합):
  1. compute_alpha_3tf(ticker, cutoff_date=None) = 진입점
  2. 각 timeframe (daily/weekly/monthly) 에 대해:
     a. manual_anchors DB SELECT — 사용자 직접 박은 anchor 우선 (source='manual')
     b. extract_swing_candidates(ohlcv, timeframe) — Stage 1 결정론 rolling local extrema
     c. llm_call_cache (type='anchor_selection') 조회 — cache_key = "ticker|tf|cutoff"
     d. select_anchors_via_llm(...) — Stage 2 Haiku 4.5 직관 (temperature=0.0, JSON)
     e. Stage 2 실패 시 (WE6) = 결정론 candidate 마지막 3 개 (source='deterministic_fallback')
  3. anchor A·B·C + current (cutoff 종가) → scoring.alpha() / interpret_alpha /
     progress_to_b / duration_ratio 산출
  4. 반환: dict[timeframe → AlphaResult]

cutoff_date 인자 = 백테스팅 친화 (canon WX1) — None 시 라이브 모드 (현재).
"""
from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal

import pandas as pd

from collectors.charts import load_ohlcv_from_db
from collectors.scoring import (
    Anchor,
    AlphaLabel,
    TIMEFRAME_LIMITS,
    alpha as compute_alpha_value,
    duration_ratio as compute_duration_ratio,
    interpret_alpha,
    progress_to_b as compute_progress_to_b,
)
from core.db import get_db
from core.llm.client import call_llm, parse_json_response
from core.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

AnchorSource = Literal["manual", "llm_stage2", "deterministic_fallback", "unavailable"]
CandidateKind = Literal["high", "low"]
Candidate = tuple[date, float, CandidateKind]


@dataclass
class AlphaResult:
    """단일 timeframe α 산출 결과 — canon WF·WL·WE 정합 풀세트.

    Fields:
        timeframe: "daily" | "weekly" | "monthly"
        value:     alpha() 산출 α (또는 None — k1_flat / 산출 불가)
        label:     interpret_alpha() 5단계 (또는 None)
        anchor_a/b/c: (date, price) 각각 — None 가능 (unavailable 시)
        current:   (date, price) — α 계산 시점 종가
        progress_to_b: current / B (None 가능)
        duration_ratio: days(C→cur) / days(A→B) (None 가능)
        source:    'manual' | 'llm_stage2' | 'deterministic_fallback' | 'unavailable'
        reason:    소스/실패 사유 (LLM reasoning 또는 fallback 라벨)
    """

    timeframe: str
    value: float | None
    label: AlphaLabel | None
    anchor_a: Anchor | None
    anchor_b: Anchor | None
    anchor_c: Anchor | None
    current: Anchor | None
    progress_to_b: float | None
    duration_ratio: float | None
    source: AnchorSource
    reason: str | None


# ---------------------------------------------------------------------------
# Stage 1 — extract_swing_candidates (결정론 rolling local extrema)
# ---------------------------------------------------------------------------


def _resample_ohlcv(ohlcv: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    """daily DataFrame → weekly (W-FRI) / monthly (ME) resample.

    daily 시 그대로 반환.
    """
    if timeframe == "daily":
        return ohlcv
    rule = {"weekly": "W-FRI", "monthly": "ME"}.get(timeframe)
    if rule is None:
        raise ValueError(f"timeframe must be daily/weekly/monthly, got {timeframe!r}")
    agg = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }
    keep = [c for c in agg if c in ohlcv.columns]
    return ohlcv[keep].resample(rule).agg({k: agg[k] for k in keep}).dropna(subset=["close"])


def _window_for_timeframe(timeframe: str) -> int:
    """timeframe 별 rolling local extrema window (bar 단위)."""
    return {"daily": 20, "weekly": 8, "monthly": 3}.get(timeframe, 20)


def extract_swing_candidates(
    ohlcv: pd.DataFrame,
    timeframe: str,
    *,
    min_gap_bars: int | None = None,
    max_candidates: int = 12,
) -> list[Candidate]:
    """Stage 1 결정론 — rolling window local high/low candidate 추출.

    canon WA5 (3 timeframe 차등 임계) + WX1 (결정론 백테스팅 친화) 정합.

    알고리즘:
      1. timeframe 별 resample (weekly W-FRI / monthly ME)
      2. rolling(window=W, center=True).max() == high → swing high candidate
         rolling(window=W, center=True).min() == low  → swing low candidate
      3. min_gap_bars (default = max(5, window//2)) 적용 — 인접 candidate 약한 쪽 제거
      4. 최근 max_candidates 만 반환 (Stage 2 LLM 입력 길이 제한)

    Args:
        ohlcv: load_ohlcv_from_db() 반환 DataFrame (index=date, columns include high/low/close)
        timeframe: 'daily' | 'weekly' | 'monthly'
        min_gap_bars: candidate 간 최소 bar gap. None 시 window // 2 또는 5 중 큰 값.
        max_candidates: 반환 candidate 최대 수 (Stage 2 입력 길이 제한)

    Returns:
        list of (date, price, 'high'|'low') ASC by date. 빈 list 가능.
    """
    if timeframe not in ("daily", "weekly", "monthly"):
        raise ValueError(f"timeframe must be daily/weekly/monthly, got {timeframe!r}")
    if ohlcv is None or len(ohlcv) == 0:
        return []

    df = _resample_ohlcv(ohlcv, timeframe)
    if len(df) < 10:
        return []

    window = _window_for_timeframe(timeframe)
    if min_gap_bars is None:
        min_gap_bars = max(5, window // 2)

    # high/low 가 없으면 close 로 대체 (resample 후 누락 가드)
    high = df["high"] if "high" in df.columns else df["close"]
    low = df["low"] if "low" in df.columns else df["close"]

    rolling_max = high.rolling(window=window, center=True, min_periods=max(2, window // 2)).max()
    rolling_min = low.rolling(window=window, center=True, min_periods=max(2, window // 2)).min()

    raw: list[Candidate] = []
    for idx in df.index:
        try:
            rmax = rolling_max.loc[idx]
            rmin = rolling_min.loc[idx]
            hv = float(high.loc[idx])
            lv = float(low.loc[idx])
        except (KeyError, ValueError, TypeError):
            continue
        if pd.isna(rmax) or pd.isna(rmin):
            continue
        d = idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])
        if hv >= float(rmax) - 1e-9:
            raw.append((d, hv, "high"))
        elif lv <= float(rmin) + 1e-9:
            raw.append((d, lv, "low"))

    if not raw:
        return []

    # min_gap_bars 필터 — 같은 kind 가 인접하면 더 강한 (high=큰값, low=작은값) 채택
    raw.sort(key=lambda c: c[0])
    filtered: list[Candidate] = []
    bar_index = {d: i for i, d in enumerate(df.index.date) if hasattr(df.index, "date")}
    # 간단화: 날짜 차이를 bar 가 아닌 일수로 근사. timeframe 별 bar 일수 ≈ {daily:1, weekly:7, monthly:30}
    bar_days = {"daily": 1, "weekly": 7, "monthly": 30}[timeframe]
    min_gap_days = max(1, min_gap_bars * bar_days)

    for cand in raw:
        if not filtered:
            filtered.append(cand)
            continue
        last = filtered[-1]
        gap_days = (cand[0] - last[0]).days
        if gap_days >= min_gap_days:
            filtered.append(cand)
            continue
        # 같은 kind 면 강한 쪽 채택, 다른 kind 면 추가 (전환점 보존)
        if cand[2] == last[2]:
            if cand[2] == "high" and cand[1] > last[1]:
                filtered[-1] = cand
            elif cand[2] == "low" and cand[1] < last[1]:
                filtered[-1] = cand
        else:
            filtered.append(cand)

    return filtered[-max_candidates:]


# ---------------------------------------------------------------------------
# Stage 2 — select_anchors_via_llm (Haiku 4.5 직관 + 3 단 캐싱)
# ---------------------------------------------------------------------------


_STAGE2_MODEL_DEFAULT = "claude-haiku-4-5"


def _anchor_cache_key(ticker: str, timeframe: str, cutoff_date: date) -> str:
    """canon WE5 / 14.1 cache_key 정의."""
    return f"{ticker}|{timeframe}|{cutoff_date.isoformat()}"


def _get_cached_anchor(input_hash: str, *, ttl_days: int = 30) -> dict | None:
    """llm_call_cache type='anchor_selection' 조회. TTL 30 일 (anchor 는 안정적)."""
    db = get_db()
    row = db.fetch_one(
        "SELECT response_json, created_at FROM llm_call_cache "
        "WHERE input_hash = ? AND type = 'anchor_selection'",
        (input_hash,),
    )
    if row is None:
        return None
    try:
        created = datetime.fromisoformat(row["created_at"])
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) - created > timedelta(days=ttl_days):
            return None
        return json.loads(row["response_json"])
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def _store_cached_anchor(
    input_hash: str,
    response: dict,
    *,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    cost_usd: float = 0.0,
    ttl_days: int = 30,
) -> None:
    """llm_call_cache 에 type='anchor_selection' 으로 저장."""
    db = get_db()
    with db.connect() as conn:
        conn.execute(
            """
            INSERT INTO llm_call_cache
                (input_hash, model, response_json, tokens_in, tokens_out, cost_usd, ttl_days, created_at, type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'anchor_selection')
            ON CONFLICT(input_hash) DO UPDATE SET
                response_json = excluded.response_json,
                tokens_in     = excluded.tokens_in,
                tokens_out    = excluded.tokens_out,
                cost_usd      = excluded.cost_usd,
                created_at    = excluded.created_at,
                type          = 'anchor_selection'
            """,
            (
                input_hash,
                model,
                json.dumps(response, ensure_ascii=False),
                tokens_in,
                tokens_out,
                cost_usd,
                ttl_days,
                datetime.now(timezone.utc).isoformat(),
            ),
        )


def _format_candidates_prompt(
    ticker: str, timeframe: str, candidates: list[Candidate]
) -> str:
    """LLM 입력 — candidate list 마크다운 표 + WA1·WA2·WA3 anchor 정의 요약."""
    rows = ["idx | date       | price     | kind",
            "----|------------|-----------|-----"]
    for i, (d, p, k) in enumerate(candidates):
        rows.append(f"{i:>3} | {d.isoformat()} | {p:>9,.2f} | {k}")
    table = "\n".join(rows)
    return f"""당신은 WAVE-ALPHA 프레임워크의 anchor 선택자입니다. 다음 candidate 중 A·B·C 3 개 anchor 를 골라주세요.

종목: {ticker} | timeframe: {timeframe}

anchor 정의 (canon WA1·WA2·WA3):
- A = 1차 발산 시작점 (장기 바닥 후 첫 상승 진입, 'low' kind 권장)
- B = 1차 발산 정점 (A 이후 첫 강한 'high' kind)
- C = 1차 되돌림 저점 = 2차 발산 시작점 (B 이후 'low' kind)

조건:
- A.date < B.date < C.date (시간 순서)
- A 와 C 는 low, B 는 high 가 자연스럽지만 절대 강제 X (LLM 직관 우선)
- 가장 최근 의미 있는 1차-2차 사이클을 우선

Candidates:
```
{table}
```

JSON 형식으로만 응답 (다른 텍스트 금지):
{{
  "A_idx": <int>,
  "B_idx": <int>,
  "C_idx": <int>,
  "reasoning": "<한 문장으로 선택 근거>"
}}"""


async def select_anchors_via_llm(
    ticker: str,
    timeframe: str,
    candidates: list[Candidate],
    *,
    cutoff_date: date | None = None,
    model: str = _STAGE2_MODEL_DEFAULT,
    skip_cache: bool = False,
) -> dict | None:
    """Stage 2 — Haiku 4.5 직관으로 anchor A·B·C 인덱스 선택.

    캐싱: llm_call_cache type='anchor_selection', cache_key = "ticker|tf|cutoff"
    TTL 30일. cutoff_date None 시 = today() KST (라이브 모드).

    Args:
        ticker: 종목코드
        timeframe: 'daily' | 'weekly' | 'monthly'
        candidates: extract_swing_candidates() 반환 list
        cutoff_date: 백테스팅 시점 (None = 라이브)
        model: LLM 모델 (기본 Haiku 4.5)
        skip_cache: True 면 캐시 skip (테스트용)

    Returns:
        {"A_idx": int, "B_idx": int, "C_idx": int, "reasoning": str} 또는 None (실패).
    """
    if len(candidates) < 3:
        return None

    cutoff = cutoff_date or date.today()
    cache_key = _anchor_cache_key(ticker, timeframe, cutoff)
    input_hash = hashlib.sha256(cache_key.encode("utf-8")).hexdigest()

    if not skip_cache:
        cached = _get_cached_anchor(input_hash)
        if cached is not None:
            log.debug("anchor_cache_hit", ticker=ticker, tf=timeframe, cutoff=cutoff.isoformat())
            return cached

    prompt = _format_candidates_prompt(ticker, timeframe, candidates)

    try:
        resp = await call_llm(
            system="You are a deterministic anchor selector. Output only valid JSON.",
            messages=[{"role": "user", "content": prompt}],
            model=model,
            max_tokens=512,
            temperature=0.0,
            # Gemini-2.5 thinking 비활성 — thinking 토큰의 max_output 예산 잠식으로
            # JSON 이 잘려 deterministic_fallback 으로 떨어지던 결함 해소 (2026-05-31).
            thinking_budget=0,
        )
        content = resp.get("content", "")
        result = parse_json_response(content)
    except Exception as e:  # noqa: BLE001
        log.warning(
            "anchor_llm_failed",
            ticker=ticker,
            tf=timeframe,
            error_type=type(e).__name__,
            error=str(e),
        )
        return None

    # 유효성 검증
    if not isinstance(result, dict):
        return None
    try:
        a = int(result["A_idx"])
        b = int(result["B_idx"])
        c = int(result["C_idx"])
    except (KeyError, ValueError, TypeError):
        return None
    if not (0 <= a < b < c < len(candidates)):
        log.warning("anchor_llm_invalid_order", ticker=ticker, tf=timeframe, a=a, b=b, c=c, n=len(candidates))
        return None

    validated = {
        "A_idx": a,
        "B_idx": b,
        "C_idx": c,
        "reasoning": str(result.get("reasoning", ""))[:500],
    }

    if not skip_cache:
        _store_cached_anchor(
            input_hash,
            validated,
            model=model,
            tokens_in=int(resp.get("tokens_in", 0)),
            tokens_out=int(resp.get("tokens_out", 0)),
            cost_usd=float(resp.get("cost_usd", 0.0)),
        )
    return validated


# ---------------------------------------------------------------------------
# Manual override — manual_anchors DB SELECT
# ---------------------------------------------------------------------------


def load_manual_anchors(
    ticker: str, timeframe: str
) -> tuple[Anchor, Anchor, Anchor] | None:
    """manual_anchors 테이블 SELECT — 사용자 직접 박은 anchor.

    Returns:
        (anchor_a, anchor_b, anchor_c) 또는 None (없음).
    """
    db = get_db()
    try:
        row = db.fetch_one(
            "SELECT anchor_a_date, anchor_a_price, anchor_b_date, anchor_b_price, "
            "anchor_c_date, anchor_c_price FROM manual_anchors "
            "WHERE ticker = ? AND timeframe = ?",
            (ticker, timeframe),
        )
    except Exception as e:  # pragma: no cover — DB 부재 환경
        log.warning("manual_anchors_load_failed", ticker=ticker, error=str(e))
        return None
    if row is None:
        return None
    try:
        a = (date.fromisoformat(row["anchor_a_date"]), float(row["anchor_a_price"]))
        b = (date.fromisoformat(row["anchor_b_date"]), float(row["anchor_b_price"]))
        c = (date.fromisoformat(row["anchor_c_date"]), float(row["anchor_c_price"]))
    except (ValueError, TypeError, KeyError) as e:
        log.warning("manual_anchors_parse_failed", ticker=ticker, error=str(e))
        return None
    return a, b, c


# ---------------------------------------------------------------------------
# 진입점 — compute_alpha_3tf
# ---------------------------------------------------------------------------


def _unavailable(timeframe: str, reason: str) -> AlphaResult:
    return AlphaResult(
        timeframe=timeframe,
        value=None,
        label=None,
        anchor_a=None,
        anchor_b=None,
        anchor_c=None,
        current=None,
        progress_to_b=None,
        duration_ratio=None,
        source="unavailable",
        reason=reason,
    )


def _current_from_ohlcv(ohlcv: pd.DataFrame, cutoff_date: date | None) -> Anchor | None:
    """cutoff_date 이전 마지막 close → (date, price). 부재 시 None."""
    if ohlcv is None or len(ohlcv) == 0:
        return None
    df = ohlcv
    if cutoff_date is not None:
        # index 가 datetime → date 비교
        mask = pd.Series(
            [(idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])) <= cutoff_date
             for idx in df.index],
            index=df.index,
        )
        df = df[mask]
    if len(df) == 0:
        return None
    last_idx = df.index[-1]
    last_d = last_idx.date() if hasattr(last_idx, "date") else date.fromisoformat(str(last_idx)[:10])
    last_close = float(df["close"].iloc[-1])
    if last_close <= 0:
        return None
    return (last_d, last_close)


def _build_result(
    timeframe: str,
    anchor_a: Anchor,
    anchor_b: Anchor,
    anchor_c: Anchor,
    current: Anchor,
    source: AnchorSource,
    reason: str | None,
) -> AlphaResult:
    """anchor 3 + current → α + label + progress + duration 풀세트."""
    try:
        value = compute_alpha_value(anchor_a, anchor_b, anchor_c, current)
    except (ValueError, TypeError) as e:
        log.warning("alpha_compute_failed", tf=timeframe, error=str(e))
        return AlphaResult(
            timeframe=timeframe,
            value=None,
            label=None,
            anchor_a=anchor_a,
            anchor_b=anchor_b,
            anchor_c=anchor_c,
            current=current,
            progress_to_b=None,
            duration_ratio=None,
            source=source,
            reason=f"alpha_error:{type(e).__name__}",
        )
    label = interpret_alpha(value, timeframe)
    try:
        prog = compute_progress_to_b(current[1], anchor_b[1])
    except (ValueError, TypeError):
        prog = None
    try:
        dur = compute_duration_ratio(anchor_a[0], anchor_b[0], anchor_c[0], current[0])
    except (ValueError, TypeError):
        dur = None
    return AlphaResult(
        timeframe=timeframe,
        value=value,
        label=label,
        anchor_a=anchor_a,
        anchor_b=anchor_b,
        anchor_c=anchor_c,
        current=current,
        progress_to_b=prog,
        duration_ratio=dur,
        source=source,
        reason=reason,
    )


async def _compute_one(
    ticker: str,
    timeframe: str,
    ohlcv: pd.DataFrame,
    cutoff_date: date,
    *,
    skip_cache: bool = False,
) -> AlphaResult:
    """단일 timeframe — manual → Stage 1 + Stage 2 → fallback."""
    current = _current_from_ohlcv(ohlcv, cutoff_date)
    if current is None:
        return _unavailable(timeframe, "ohlcv_empty_after_cutoff")

    # 1) Manual override
    manual = load_manual_anchors(ticker, timeframe)
    if manual is not None:
        a, b, c = manual
        return _build_result(timeframe, a, b, c, current, source="manual", reason="manual_anchors DB")

    # 2) Stage 1 결정론 candidate
    df_for_stage1 = ohlcv
    if cutoff_date is not None:
        mask = pd.Series(
            [(idx.date() if hasattr(idx, "date") else date.fromisoformat(str(idx)[:10])) <= cutoff_date
             for idx in ohlcv.index],
            index=ohlcv.index,
        )
        df_for_stage1 = ohlcv[mask]
    candidates = extract_swing_candidates(df_for_stage1, timeframe)
    if len(candidates) < 3:
        return _unavailable(timeframe, f"insufficient_candidates:{len(candidates)}")

    # 3) Stage 2 LLM
    llm_result = await select_anchors_via_llm(
        ticker, timeframe, candidates, cutoff_date=cutoff_date, skip_cache=skip_cache
    )
    if llm_result is not None:
        a_idx, b_idx, c_idx = llm_result["A_idx"], llm_result["B_idx"], llm_result["C_idx"]
        a = (candidates[a_idx][0], candidates[a_idx][1])
        b = (candidates[b_idx][0], candidates[b_idx][1])
        c = (candidates[c_idx][0], candidates[c_idx][1])
        try:
            return _build_result(
                timeframe, a, b, c, current,
                source="llm_stage2",
                reason=llm_result.get("reasoning") or None,
            )
        except (ValueError, TypeError) as e:
            log.warning("llm_anchor_alpha_failed", ticker=ticker, tf=timeframe, error=str(e))

    # 4) E6 fallback — 결정론 candidate 마지막 3 개 (단 C < current 보장)
    # current 와 너무 가까운 trailing candidate 는 제외 — α 계산 시 days(C→current) > 0 강제.
    min_gap = max(1, TIMEFRAME_LIMITS[timeframe]["min_gap_days"] // 2)
    cur_date = current[0]
    usable = [c for c in candidates if (cur_date - c[0]).days >= min_gap]
    if len(usable) < 3:
        return _unavailable(
            timeframe,
            f"WE6 fallback failed: only {len(usable)} candidates ≥ {min_gap}d before current",
        )
    last3 = usable[-3:]
    a = (last3[0][0], last3[0][1])
    b = (last3[1][0], last3[1][1])
    c = (last3[2][0], last3[2][1])
    return _build_result(
        timeframe, a, b, c, current,
        source="deterministic_fallback",
        reason="WE6 fallback (Stage 2 실패 또는 무효 → 결정론 마지막 3 candidate, C < current 가드 적용)",
    )


async def compute_alpha_3tf(
    ticker: str,
    *,
    cutoff_date: date | None = None,
    skip_cache: bool = False,
) -> dict[str, AlphaResult]:
    """3 timeframe (daily/weekly/monthly) α 풀세트 산출 — WAVE-ALPHA-001 진입점.

    canon WA5 (3 timeframe 동시 산출) + WX1 (cutoff_date 백테스팅 친화) 정합.

    Args:
        ticker: 종목코드 ("005930" / "NVDA" / "0001" 등)
        cutoff_date: 백테스팅 시점. None = 라이브 모드 (today())
        skip_cache: 테스트용 cache bypass

    Returns:
        {"daily": AlphaResult, "weekly": AlphaResult, "monthly": AlphaResult}
        각 항목은 source 가 'manual'/'llm_stage2'/'deterministic_fallback'/'unavailable' 중 하나.
    """
    cutoff = cutoff_date or date.today()
    # 충분한 기간: monthly TIMEFRAME_LIMITS.max_history_years = 15 년 = ~5475 일
    # chart_ohlcv 실 적재는 보통 5 년이지만 limit 으로 안전하게 5000 일 (~14 년) 요청
    ohlcv = load_ohlcv_from_db(ticker, limit=5000)
    if len(ohlcv) == 0:
        log.info("alpha_3tf_no_ohlcv", ticker=ticker)
        return {
            tf: _unavailable(tf, "ohlcv_empty") for tf in ("daily", "weekly", "monthly")
        }

    results: dict[str, AlphaResult] = {}
    for tf in ("daily", "weekly", "monthly"):
        try:
            results[tf] = await _compute_one(ticker, tf, ohlcv, cutoff, skip_cache=skip_cache)
        except Exception as e:  # noqa: BLE001
            log.warning("alpha_3tf_compute_failed", ticker=ticker, tf=tf, error=str(e))
            results[tf] = _unavailable(tf, f"unexpected_error:{type(e).__name__}")
    return results


# ---------------------------------------------------------------------------
# Render — chart_data_md 다음 블록 [5] α 3 timeframe
# ---------------------------------------------------------------------------


def _fmt_anchor(a: Anchor | None) -> str:
    if a is None:
        return "null"
    d, p = a
    return f"{d.isoformat()} @ {p:,.2f}"


def _fmt_float(v: float | None, digits: int = 2) -> str:
    if v is None:
        return "null"
    return f"{v:.{digits}f}"


def render_alpha_3tf_md(results: dict[str, AlphaResult], ticker: str) -> str:
    """`[5] α 3 timeframe` 블록 — chart_data_md 다음 system prompt 주입.

    WAVE-ALPHA-001 § 11 + persona v4 § 4 가 인용할 데이터 풀세트.
    환각 가드 3중 정합: source 항상 명시 (manual / llm_stage2 / deterministic_fallback / unavailable).
    """
    lines: list[str] = []
    lines.append("## [5] α 3 timeframe (WAVE-ALPHA-001)")
    lines.append("")
    lines.append(f"**Ticker**: {ticker} | **canon**: WA1·WA2·WA3·WF1·WF2·WF3·WL1·WL2·WL3·WE1~WE7")
    lines.append("")
    lines.append("| Timeframe | α | label | A (anchor_a) | B (anchor_b) | C (anchor_c) | current | progress_to_b | duration_ratio | source |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for tf in ("daily", "weekly", "monthly"):
        r = results.get(tf)
        if r is None:
            lines.append(f"| {tf} | null | null | null | null | null | null | null | null | unavailable |")
            continue
        lines.append(
            f"| {tf} | {_fmt_float(r.value, 3)} | {r.label or 'null'} | "
            f"{_fmt_anchor(r.anchor_a)} | {_fmt_anchor(r.anchor_b)} | "
            f"{_fmt_anchor(r.anchor_c)} | {_fmt_anchor(r.current)} | "
            f"{_fmt_float(r.progress_to_b, 3)} | {_fmt_float(r.duration_ratio, 3)} | "
            f"{r.source} |"
        )
    lines.append("")

    # 소스 사유 (debugging + 환각 가드 3중 정합)
    reason_lines = []
    for tf in ("daily", "weekly", "monthly"):
        r = results.get(tf)
        if r is not None and r.reason:
            reason_lines.append(f"- {tf}: {r.source} — {r.reason}")
    if reason_lines:
        lines.append("### anchor 출처 사유")
        lines.extend(reason_lines)
        lines.append("")

    lines.append(
        "_anchor source = `manual` (사용자 직접 박음) / `llm_stage2` (Haiku 4.5 직관 캐시) / "
        "`deterministic_fallback` (LLM 실패 시 결정론 마지막 3 candidate) / `unavailable` (산출 불가)._"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# run_analyst.py metadata helper (cycle 13 _snapshot_extend_metadata 패턴 mirror)
# ---------------------------------------------------------------------------


def alpha_3tf_metadata(results: dict[str, AlphaResult]) -> dict[str, Any]:
    """run_analyst metadata 에 노출할 alpha_* 풀세트.

    canon WA5 (3 timeframe) + 환각 가드 3중 (source 노출) 정합.
    """
    out: dict[str, Any] = {}
    for tf in ("daily", "weekly", "monthly"):
        r = results.get(tf)
        key = f"alpha_{tf}"
        if r is None:
            out[key] = {"value": None, "label": None, "source": "unavailable", "reason": "missing"}
            continue
        out[key] = {
            "value": r.value,
            "label": r.label,
            "source": r.source,
            "reason": r.reason,
            "progress_to_b": r.progress_to_b,
            "duration_ratio": r.duration_ratio,
            "anchor_a_date": r.anchor_a[0].isoformat() if r.anchor_a else None,
            "anchor_b_date": r.anchor_b[0].isoformat() if r.anchor_b else None,
            "anchor_c_date": r.anchor_c[0].isoformat() if r.anchor_c else None,
        }
    return out
