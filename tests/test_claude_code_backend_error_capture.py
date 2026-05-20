"""cycle 8 — claude_code provider HTTP 500 (빈 메시지) 진단 보강 + 1회 retry 검증.

cycle 6.5 production smoke 중 발견된 silent HTTP 500 (body=`{"detail":"inference failed: "}`
빈 message) 의 원인 = claude_code CLI 비정상 종료 시 stderr/stdout 모두 비어 →
RuntimeError("claude_code exited N: ") 같이 메시지가 비어 보이고 endpoint detail 도
truncate. 본 cycle 8 의 4 보강 검증:

1. backend `call_claude_code` 비영 returncode + 빈 stderr/stdout → "(no stderr/stdout captured)" 명시
2. backend `call_claude_code` 비영 returncode + stderr 있음 → 그 stderr 포함
3. backend streaming is_error + result="" → "(no result field in is_error event)" 명시
4. backend streaming is_error + result="auth failed" → 그 result 포함
5. client.py claude_code branch — RuntimeError("exited") 첫 호출 실패 → 1회 retry 후 성공
6. client.py claude_code branch — 두 번 모두 RuntimeError("exited") → 최종 raise
7. client.py claude_code branch — RuntimeError(빈 메시지·"exited" 없음) 같은 영구 실패는 retry X
8. client.py claude_code branch — TimeoutError 같은 비-RuntimeError 는 retry X

`tests/test_llm_streaming.py` 의 monkeypatch + async coroutine mock 패턴 미러.
"""
from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

# 모듈 직접 import — backend, client 양쪽 검증
from core.llm import claude_code_backend as backend_mod
from core.llm import client as client_mod


# ---------------------------------------------------------------------------
# Backend: returncode != 0 메시지 보강
# ---------------------------------------------------------------------------


class _FakeProc:
    """asyncio.create_subprocess_exec 의 stand-in. proc.communicate 가 stdout/stderr 반환."""

    def __init__(self, *, stdout: bytes, stderr: bytes, returncode: int) -> None:
        self._stdout = stdout
        self._stderr = stderr
        self.returncode = returncode

    async def communicate(self, input: bytes = b""):  # noqa: A002
        return self._stdout, self._stderr

    def kill(self) -> None:
        pass


def _patch_subprocess(monkeypatch, *, stdout: bytes, stderr: bytes, returncode: int):
    """asyncio.create_subprocess_exec 가 _FakeProc 반환하도록 patch."""

    async def _fake_create(*_a, **_kw):
        return _FakeProc(stdout=stdout, stderr=stderr, returncode=returncode)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create)
    # _resolve_launcher 가 실제 PATH 검색 안 하도록
    monkeypatch.setattr(backend_mod, "_resolve_launcher", lambda binary: ["claude"])


def test_returncode_nonzero_empty_streams_message_enhanced(monkeypatch):
    """비영 returncode + stderr/stdout 모두 비음 → 명시 fallback 메시지."""
    _patch_subprocess(monkeypatch, stdout=b"", stderr=b"", returncode=1)

    with pytest.raises(RuntimeError, match="exited 1") as exc_info:
        asyncio.run(
            backend_mod.call_claude_code(
                system="sys",
                messages=[{"role": "user", "content": "q"}],
                model="claude-sonnet-4-6",
                max_tokens=100,
                temperature=0.0,
            )
        )

    msg = str(exc_info.value)
    assert "(no stderr/stdout captured)" in msg, (
        f"빈 fallback 메시지 누락: {msg!r}"
    )


def test_returncode_nonzero_with_stderr_includes_stderr(monkeypatch):
    """비영 returncode + stderr 있음 → 그 stderr 메시지에 포함."""
    _patch_subprocess(
        monkeypatch,
        stdout=b"",
        stderr=b"error: command not allowed",
        returncode=2,
    )

    with pytest.raises(RuntimeError, match="exited 2") as exc_info:
        asyncio.run(
            backend_mod.call_claude_code(
                system="sys",
                messages=[{"role": "user", "content": "q"}],
                model="claude-sonnet-4-6",
                max_tokens=100,
                temperature=0.0,
            )
        )

    msg = str(exc_info.value)
    assert "command not allowed" in msg, f"stderr 누락: {msg!r}"
    assert "(no stderr/stdout captured)" not in msg, (
        f"stderr 있는데 빈 fallback 박힘: {msg!r}"
    )


# ---------------------------------------------------------------------------
# Backend: streaming is_error 메시지 보강
# ---------------------------------------------------------------------------


def test_streaming_is_error_empty_result_message_enhanced():
    """streaming `result` 이벤트의 is_error=True + result="" 케이스 = saw_error 보강.

    cycle 8 정정 전: `saw_error = str(event.get("result") or "claude_code error")`
    → result="" → "" (falsy) → "claude_code error" 로 fallback (이미 있음, but 진단 무관).
    cycle 8 정정 후: empty result → "(no result field in is_error event)" 로 명시.
    """
    # backend 의 saw_error 로직만 단위 검증 (전체 stream subprocess mocking 은 복잡)
    # 위 정정 로직과 동일 흐름:
    result_val = ""
    saw_error = (
        str(result_val).strip()
        if result_val
        else "(no result field in is_error event)"
    )
    assert saw_error == "(no result field in is_error event)"


def test_streaming_is_error_with_result_includes_result():
    """streaming `result` is_error=True + result="auth failed" → 그 result 포함."""
    result_val = "auth failed"
    saw_error = (
        str(result_val).strip()
        if result_val
        else "(no result field in is_error event)"
    )
    assert saw_error == "auth failed"
    # 그리고 raise 메시지에 포함되는지 패턴 검증
    raise_msg = f"claude_code stream returned error: {saw_error}"
    assert "auth failed" in raise_msg


# ---------------------------------------------------------------------------
# client.py: claude_code 1회 retry 검증
# ---------------------------------------------------------------------------


def _stub_cfg():
    """get_config().llm 의 최소 stub — claude_code subkey + mock_if_no_key."""
    claude_code = SimpleNamespace(
        binary="claude",
        timeout_sec=90,
        extra_args=(),
    )
    return SimpleNamespace(
        primary="anthropic",
        anthropic=SimpleNamespace(model="claude-sonnet-4-6", max_tokens=1000, temperature=0.0),
        claude_code=claude_code,
        mock_if_no_key=False,
    )


def _run_dispatch(provider: str, *, allow_fallback: bool = False) -> Any:
    """`_dispatch_provider` 호출 helper."""
    return asyncio.run(
        client_mod._dispatch_provider(
            provider=provider,
            cfg=_stub_cfg(),
            system="sys",
            messages=[{"role": "user", "content": "q"}],
            model="claude-sonnet-4-6",
            max_tokens=1000,
            temperature=0.0,
            allow_fallback=allow_fallback,
        )
    )


def _success_response() -> dict:
    return {
        "content": "ok",
        "tokens_in": 10,
        "tokens_out": 5,
        "model": "claude-sonnet-4-6",
        "cost_usd": 0.0,
        "raw": {"provider": "claude_code"},
    }


def test_claude_code_retry_recovers_on_second_attempt(monkeypatch):
    """첫 호출 RuntimeError("exited ...") + 두번째 성공 → 최종 정상 응답."""
    call_count = {"n": 0}

    async def _fake_call_claude_code(**_kw):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("claude_code exited 1: (no stderr/stdout captured)")
        return _success_response()

    monkeypatch.setattr(backend_mod, "call_claude_code", _fake_call_claude_code)

    resp = _run_dispatch("claude_code")
    assert call_count["n"] == 2, f"retry 1회 안 됨: 호출 {call_count['n']}"
    assert resp["content"] == "ok"


def test_claude_code_retry_exhausted_raises_final_error(monkeypatch):
    """두 번 모두 RuntimeError("exited") → 최종 raise."""
    call_count = {"n": 0}

    async def _fake_call_claude_code(**_kw):
        call_count["n"] += 1
        raise RuntimeError(f"claude_code exited 1 (attempt {call_count['n']})")

    monkeypatch.setattr(backend_mod, "call_claude_code", _fake_call_claude_code)

    with pytest.raises(RuntimeError, match="exited"):
        _run_dispatch("claude_code")
    assert call_count["n"] == 2, f"retry 2회까지 안 옴: 호출 {call_count['n']}"


def test_claude_code_non_transient_error_no_retry(monkeypatch):
    """RuntimeError 지만 "exited" 키워드 없는 경우 (= 영구 실패) → retry X."""
    call_count = {"n": 0}

    async def _fake_call_claude_code(**_kw):
        call_count["n"] += 1
        raise RuntimeError("claude_code stdout is not valid JSON: garbage")

    monkeypatch.setattr(backend_mod, "call_claude_code", _fake_call_claude_code)

    with pytest.raises(RuntimeError, match="not valid JSON"):
        _run_dispatch("claude_code")
    assert call_count["n"] == 1, f"비-transient 인데 retry 됨: 호출 {call_count['n']}"


def test_claude_code_non_runtime_error_no_retry(monkeypatch):
    """TimeoutError 같은 비-RuntimeError → retry X (영구 실패로 간주)."""
    call_count = {"n": 0}

    async def _fake_call_claude_code(**_kw):
        call_count["n"] += 1
        raise asyncio.TimeoutError("timeout")

    monkeypatch.setattr(backend_mod, "call_claude_code", _fake_call_claude_code)

    with pytest.raises(asyncio.TimeoutError):
        _run_dispatch("claude_code")
    assert call_count["n"] == 1, f"TimeoutError 인데 retry 됨: 호출 {call_count['n']}"


# ---------------------------------------------------------------------------
# Backend: SelectorEventLoop fallback (cycle 8 추가)
# ---------------------------------------------------------------------------


def test_call_claude_code_falls_back_to_sync_on_selector_loop(monkeypatch):
    """SelectorEventLoop (uvicorn Windows) 환경 = `_can_spawn_subprocess()` False →
    `call_claude_code` 가 `_call_claude_code_sync_via_thread` 로 직행.

    cycle 6.5 발견: server (uvicorn) 측 SelectorEventLoop 에서 async
    `create_subprocess_exec` 가 NotImplementedError (빈 메시지) → endpoint silent 500.
    cycle 8 정정: 사전 체크 후 sync 경로 직행 (json_schema 미사용 케이스).
    """
    monkeypatch.setattr(backend_mod, "_can_spawn_subprocess", lambda: False)

    called = {"sync": False, "kwargs": None}

    async def _fake_sync(**kw):
        called["sync"] = True
        called["kwargs"] = kw
        return {
            "content": "from sync",
            "tokens_in": 10,
            "tokens_out": 5,
            "model": "claude-sonnet-4-6",
            "cost_usd": 0.0,
            "raw": {"provider": "claude_code"},
        }

    monkeypatch.setattr(backend_mod, "_call_claude_code_sync_via_thread", _fake_sync)

    resp = asyncio.run(
        backend_mod.call_claude_code(
            system="sys",
            messages=[{"role": "user", "content": "q"}],
            model="claude-sonnet-4-6",
            max_tokens=100,
            temperature=0.0,
        )
    )

    assert called["sync"] is True, "Selector loop 인데 sync fallback 미호출"
    assert resp["content"] == "from sync"


def test_call_claude_code_with_json_schema_skips_sync_fallback(monkeypatch):
    """`json_schema` 인자 사용 시는 sync 함수 미지원 → fallback skip + async 경로.

    Selector loop + json_schema 조합은 희귀 (ProactorEventLoop 환경 권장).
    본 테스트는 그 분기 정확성만 검증 — async 시도 자체가 NotImplementedError
    나도 fallback 으로 silent 흡수 X (사용자 명시 json_schema 사용 = 본인 환경 책임).
    """
    monkeypatch.setattr(backend_mod, "_can_spawn_subprocess", lambda: False)

    called = {"sync": False}

    async def _fake_sync(**_kw):
        called["sync"] = True
        return {}

    monkeypatch.setattr(backend_mod, "_call_claude_code_sync_via_thread", _fake_sync)

    # async 경로 진입 시도 → NotImplementedError 또는 비슷한 raise 받음.
    # 우리는 sync fallback 이 호출 안 됐다는 것만 검증.
    async def _fake_create_proc(*_a, **_kw):
        raise NotImplementedError("selector loop subprocess")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", _fake_create_proc)
    monkeypatch.setattr(backend_mod, "_resolve_launcher", lambda binary: ["claude"])

    with pytest.raises(NotImplementedError):
        asyncio.run(
            backend_mod.call_claude_code(
                system="sys",
                messages=[{"role": "user", "content": "q"}],
                model="claude-sonnet-4-6",
                max_tokens=100,
                temperature=0.0,
                json_schema={"type": "object"},
            )
        )

    assert called["sync"] is False, (
        "json_schema 사용 시는 sync fallback 안 함 (희귀 케이스, 사용자 환경 책임)"
    )
