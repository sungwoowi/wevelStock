"""KOSPI200 야간선물 실측 준비/검증 프로브 (INFRA-MARKET-ASSETS-002 Part C).

NOT a pytest — 실 KIS 호출. TESTING=1 금지.

목적:
  ① KIS 선물 시세 종목코드가 작동하는지 (연결선물 자동 최근월물).
  ② 응답에서 어떤 필드가 현재가/전일대비율인지 raw 로 확인 (index_futures_price 파서 검증).
  ③ 야간(18:00~05:00 KST) 세션이면 야간가, 주간(09:00~15:45)이면 주간가 — 둘 다 코드 검증엔 유효.

체크리스트 (밤 실측 전 확인):
  ① 실계좌 .env  — KIS_IS_PAPER=false + 실전 앱키/시크릿. 모의계좌(paper)는 선물 시세 제한 가능.
  ② 시세 권한    — EGW/권한 에러 시 KIS 개발자센터에서 '국내선물옵션 시세' 사용 신청.
  ③ 종목코드     — 연결선물 후보부터 시도. 다 막히면 HTS(영웅문 등)에서 KOSPI200 최근월물 단축코드 확인 후
                   `KIS_KOSPI200_FUTURES_SYMBOL=<코드>` 로 지정.
  ④ 야간 실측    — 18:00 이후 다시 실행. 작동 코드를 .env `KIS_KOSPI200_FUTURES_SYMBOL` 에 박으면
                   compute_market_macro('KOSPI') 가 자동으로 kospi200_night_change_pct 채움.

사용:
  uv run python scripts/_kospi200_night_probe.py
  (특정 코드 강제) KIS_KOSPI200_FUTURES_SYMBOL=101W09 uv run python scripts/_kospi200_night_probe.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_KST = ZoneInfo("Asia/Seoul")

# 후보 종목코드 — 연결선물(시스템이 최근월물 자동 반환) 우선.
#   101000 = KOSPI200 선물 연결선물 (상품 101 + 연결 000) 추정.
#   105000 = KOSPI200 미니선물 연결 (참고용).
# env 지정 코드가 있으면 그것부터 시도.
_DEFAULT_CANDIDATES = ["101000", "105000"]


def hr(t: str) -> None:
    print("\n" + "=" * 70 + f"\n{t}\n" + "=" * 70)


def _session_label(now: datetime) -> str:
    """현재 KST 시각으로 어느 세션인지 라벨."""
    hm = now.hour * 60 + now.minute
    if 9 * 60 <= hm <= 15 * 60 + 45:
        return "주간장 (09:00~15:45) — 주간 선물가. 코드 검증엔 유효, 야간가 아님."
    if hm >= 18 * 60 or hm <= 5 * 60:
        return "야간장 (18:00~05:00) — ★야간 선물가★ 실측 타이밍."
    return "장 휴식 (15:45~18:00 등) — 시세 정체/직전값 가능."


async def main() -> None:
    from connectors.kis import KISClient

    now = datetime.now(_KST)
    hr("[A] 환경 체크 — KIS 키 / 계좌 종류 / 세션 시각")
    print(f"현재 KST: {now:%Y-%m-%d %H:%M}  →  {_session_label(now)}")

    env_symbol = os.getenv("KIS_KOSPI200_FUTURES_SYMBOL", "").strip()
    candidates = ([env_symbol] if env_symbol else []) + _DEFAULT_CANDIDATES
    print(f"시도할 종목코드 후보: {candidates}  (env 지정={env_symbol or '없음'})")

    async with KISClient() as kis:
        print(f"KIS configured = {kis.configured}")
        if not kis.configured:
            print("⚠ KIS_APP_KEY/SECRET 미설정 — .env 확인 필요. 중단.")
            return
        is_paper = os.getenv("KIS_IS_PAPER", "true").lower() == "true"
        print(f"KIS_IS_PAPER   = {is_paper}  "
              f"({'⚠ 모의계좌 — 선물 시세 제한 가능, 실계좌 권장' if is_paper else '실계좌 OK'})")

        hr("[B] 종목코드별 실 호출 — raw output1 + 파서 결과")
        winner = None
        for code in candidates:
            print(f"\n── 코드 {code} ──")
            try:
                raw = await kis._get(
                    "/uapi/domestic-futureoption/v1/quotations/inquire-price",
                    tr_id="FHMIF10000000",
                    params={"FID_COND_MRKT_DIV_CODE": "F", "FID_INPUT_ISCD": code},
                )
            except Exception as exc:  # noqa: BLE001
                print(f"  예외: {exc}")
                continue

            rt = raw.get("rt_cd")
            print(f"  rt_cd={rt}  msg1={raw.get('msg1')}")
            if rt != "0":
                print("  → 실패 (권한 EGW / 잘못된 코드 / 시세 미제공). 다음 후보로.")
                continue

            o = raw.get("output1") or raw.get("output") or {}
            # 현재가/전일대비 관련 필드만 추려 출력 (필드명 확인용)
            interesting = {
                k: v for k, v in o.items()
                if any(t in k for t in ("prpr", "prdy", "ctrt", "vrss", "hgpr", "lwpr"))
            }
            print(f"  현재가/등락 관련 필드: {interesting}")
            parsed = await kis.index_futures_price(code)
            print(f"  index_futures_price() 파서 결과: {parsed}")
            if parsed.get("change_pct") is not None:
                winner = (code, parsed)
                print(f"  ✅ 작동 — change_pct={parsed['change_pct']}")
                break

        hr("[C] 결론")
        if winner:
            code, parsed = winner
            print(f"작동 종목코드 = {code}  (현재가 {parsed.get('price')}, "
                  f"전일대비 {parsed.get('change_pct')}%)")
            print(f"→ .env 에 다음 추가하면 야간 cron 이 자동 적재:")
            print(f"    KIS_KOSPI200_FUTURES_SYMBOL={code}")
            if "주간장" in _session_label(now):
                print("→ 지금은 주간가. 18:00 이후 같은 코드로 재실행하면 야간가 확인 가능.")
        else:
            print("작동 코드 없음. 점검: ① 실계좌 .env 인가 ② 국내선물옵션 시세 신청했나")
            print("③ HTS 에서 KOSPI200 최근월물 단축코드 확인 후 KIS_KOSPI200_FUTURES_SYMBOL 로 지정")
            print("→ 끝내 불가면 SPEC 대로 백로그 강등 (yfinance 불가 + KIS 권한 한계).")


if __name__ == "__main__":
    asyncio.run(main())
