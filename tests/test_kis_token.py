"""connectors.kis.client — OAuth 토큰 관리 단위 테스트.

대상 (2026-06-11 chart_refresh 배치 전수 실패 회귀 방지):
- 만료시각을 **KST** 로 파싱 (UTC 오인 → 9 시간 늦은 만료 캐싱 버그)
- 만료 마진 (만료 10 분 전 선제 재발급)
- "기간이 만료된 token" 응답 시 강제 재발급 후 1 회 재시도

모든 KIS API 호출 mock. 실 API 호출 0.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from connectors.kis.client import _KST, KISClient


class _FakeResp:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def json(self) -> dict[str, Any]:
        return self._payload


class _FakeHTTP:
    """httpx.AsyncClient 대역. post=토큰 발급, get=데이터 호출 스크립트."""

    def __init__(
        self,
        token_payloads: list[dict[str, Any]],
        get_payloads: list[dict[str, Any]],
    ) -> None:
        self._token_payloads = token_payloads
        self._get_payloads = get_payloads
        self.post_calls = 0
        self.get_calls = 0

    async def post(self, url: str, json: dict | None = None) -> _FakeResp:
        payload = self._token_payloads[min(self.post_calls, len(self._token_payloads) - 1)]
        self.post_calls += 1
        return _FakeResp(payload)

    async def get(
        self, url: str, headers: dict | None = None, params: dict | None = None
    ) -> _FakeResp:
        payload = self._get_payloads[min(self.get_calls, len(self._get_payloads) - 1)]
        self.get_calls += 1
        return _FakeResp(payload)

    async def aclose(self) -> None:
        return None


@pytest.fixture(autouse=True)
def _reset_token_cache():
    KISClient.reset_token_cache()
    yield
    KISClient.reset_token_cache()


@pytest.fixture(autouse=True)
def _no_sleep(monkeypatch):
    """토큰 발급 후 2s sleep / rate-limit sleep 제거 (테스트 속도)."""
    async def _noop(*_a, **_k) -> None:
        return None

    monkeypatch.setattr("connectors.kis.client.asyncio.sleep", _noop)


def _token_payload(expire_kst: str) -> dict[str, Any]:
    return {"access_token": f"tok-{expire_kst}", "access_token_token_expired": expire_kst}


@pytest.mark.asyncio
async def test_expiry_parsed_as_kst(monkeypatch):
    """만료시각은 KST 로 파싱되어야 한다 (UTC 오인 금지)."""
    expire_kst = "2099-01-01 18:00:00"
    http = _FakeHTTP(
        token_payloads=[_token_payload(expire_kst)],
        get_payloads=[{"rt_cd": "0", "output": {"stck_prpr": "100"}}],
    )
    async with KISClient() as kis:
        kis._client = http  # type: ignore[assignment]
        kis._app_key = "APPKEY"  # _token_is_fresh 가 key 일치 요구
        await kis._ensure_token()

    expected = datetime.strptime(expire_kst, "%Y-%m-%d %H:%M:%S").replace(tzinfo=_KST)
    assert KISClient._shared_token_expires == expected
    # KST 18:00 == UTC 09:00 (UTC 오인 시 18:00Z 가 되어 9 시간 차이)
    assert KISClient._shared_token_expires.astimezone(timezone.utc).hour == 9


@pytest.mark.asyncio
async def test_kst_token_already_expired_triggers_reissue(monkeypatch):
    """KST 만료시각이 현재(UTC) 기준 이미 지났으면 재발급해야 한다.

    이전 버그: KST 18:00 을 UTC 18:00 으로 오인 → 9 시간 늦게 만료 캐싱 →
    실제 만료된 토큰을 계속 재사용 (배치 전수 실패).
    """
    now_utc = datetime.now(timezone.utc)
    # 1 시간 전(UTC)에 만료된 KST 시각
    past_kst = (now_utc.astimezone(_KST) - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    # 미래 만료 (재발급 결과)
    future_kst = (now_utc.astimezone(_KST) + timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S")

    http = _FakeHTTP(
        token_payloads=[_token_payload(past_kst), _token_payload(future_kst)],
        get_payloads=[{"rt_cd": "0"}],
    )
    async with KISClient() as kis:
        kis._client = http  # type: ignore[assignment]
        kis._app_key = "APPKEY"
        t1 = await kis._ensure_token()  # 만료 토큰 발급
        assert not KISClient._token_is_fresh("APPKEY")  # 즉시 stale 판정
        t2 = await kis._ensure_token()  # 재발급되어야 함

    assert t1 != t2
    assert http.post_calls == 2


@pytest.mark.asyncio
async def test_expired_token_error_refreshes_and_retries(monkeypatch):
    """KIS 가 '기간이 만료된 token' 을 반환하면 재발급 후 1 회 재시도해 성공해야 한다."""
    base = datetime.now(timezone.utc).astimezone(_KST) + timedelta(hours=10)
    future_a = base.strftime("%Y-%m-%d %H:%M:%S")
    future_b = (base + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
    http = _FakeHTTP(
        token_payloads=[_token_payload(future_a), _token_payload(future_b)],
        get_payloads=[
            {"rt_cd": "1", "msg1": "기간이 만료된 token 입니다."},  # 1차: 만료 에러
            {"rt_cd": "0", "output": {"stck_prpr": "100"}},        # 2차: 성공
        ],
    )
    async with KISClient() as kis:
        kis._client = http  # type: ignore[assignment]
        kis._app_key = "APPKEY"
        data = await kis._get("/x", tr_id="T", params={})

    assert data.get("rt_cd") == "0"
    assert http.get_calls == 2     # 재시도 발생
    assert http.post_calls == 2    # 토큰 강제 재발급


@pytest.mark.asyncio
async def test_refresh_margin(monkeypatch):
    """만료 10 분 전이면 fresh 가 아니어야 한다 (선제 재발급)."""
    soon_kst = (datetime.now(timezone.utc).astimezone(_KST) + timedelta(minutes=5)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    http = _FakeHTTP(
        token_payloads=[_token_payload(soon_kst)],
        get_payloads=[{"rt_cd": "0"}],
    )
    async with KISClient() as kis:
        kis._client = http  # type: ignore[assignment]
        kis._app_key = "APPKEY"
        await kis._ensure_token()

    # 5 분 후 만료 → 마진(10 분) 안쪽이므로 stale
    assert not KISClient._token_is_fresh("APPKEY")
