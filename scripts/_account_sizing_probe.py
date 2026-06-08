"""ACCOUNT-MANAGER-001 (RB-MS1) 라이브 probe — 실 config/accounts.yaml 로 비중 산정 end-to-end.

결정론(LLM·네트워크 0). 실 config 로더 + size_position + render 를 4 시나리오로 실증.
usage: uv run python scripts/_account_sizing_probe.py
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from core.account.portfolio import get_account, get_account_state  # noqa: E402
from core.account.sizing import render_position_sizing_md, size_position  # noqa: E402


def _probe(title: str, *, account_id: str, rec: dict, entry_posture: str,
           extension: float | None, extreme: str = "none") -> None:
    acct = get_account(account_id)
    assert acct is not None, f"계좌 정의 없음: {account_id}"
    state = get_account_state(account_id)
    out = size_position(
        recommendation=rec, account=acct, state=state,
        entry_posture=entry_posture, extension=extension, extreme=extreme,
    )
    print(f"\n=== {title} ===")
    print(render_position_sizing_md(out))
    print(f"  [raw] verdict={'blocked' if out.blocked else 'sized'} "
          f"weight={out.target_weight:.3f} R={out.risk_fraction:.3f} caps={out.applied_caps}")


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass

    print("ACCOUNT-MANAGER-001 비중 산정 probe (실 config/accounts.yaml)")

    # A. Track A 좋은 타점 (저과열) — front-load, 캡 미적용
    _probe(
        "A. 국장 중장기 · 좋은 타점 (저과열)",
        account_id="kr_long",
        rec={"recommendation_id": "REC-20260609-005930-A", "ticker": "005930", "track": "A",
             "entry_price": 78000.0, "stop_loss": 70000.0,
             "cited_scores": {"s_score": 8.0, "f_score": 7.5}},
        entry_posture="aggressive", extension=8.5,
    )

    # B. Track B 고확신 타이트 손절 — 단일/트레이딩 캡 축소
    _probe(
        "B. 국장 단기 · 고확신·타이트 손절",
        account_id="kr_swing",
        rec={"recommendation_id": "REC-20260609-000660-B", "ticker": "000660", "track": "B",
             "entry_price": 200000.0, "stop_loss": 194000.0,
             "cited_scores": {"t_score": 8.5, "buy_score": 8.0, "f_score": 7.5}},
        entry_posture="aggressive", extension=5.0,
    )

    # C. 손절 누락 → 하드 차단
    _probe(
        "C. 손절선 누락 (하드 차단)",
        account_id="kr_long",
        rec={"recommendation_id": "REC-20260609-035720-A", "ticker": "035720", "track": "A",
             "entry_price": 50000.0, "stop_loss": None,
             "cited_scores": {"s_score": 7.0}},
        entry_posture="neutral", extension=6.0,
    )

    # D. 미장 vix_panic → 신규 진입 동결
    _probe(
        "D. 미장 단기 · vix_panic 동결",
        account_id="us_swing",
        rec={"recommendation_id": "REC-20260609-NVDA-B", "ticker": "NVDA", "track": "B",
             "entry_price": 1000.0, "stop_loss": 950.0,
             "cited_scores": {"t_score": 8.0, "buy_score": 7.5, "f_score": 7.0}},
        entry_posture="defensive", extension=4.0, extreme="vix_panic",
    )

    print("\n✓ probe 완료 — 4 시나리오 결정론 산출")


if __name__ == "__main__":
    main()
