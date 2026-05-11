"""KNOWLEDGE-SYNC-001 Phase 2 M3 — watcher.py unit + integration tests.

대상: `core.knowledge.watcher`
- `_extract_dept` 헬퍼 (dept 추출 + _ prefix skip + 외부 path None)
- `_Debouncer` (연속 trigger coalesce + dept 별 분리)
- `start_observer` 통합 (tmp reference dir 감시 → 파일 생성 → callback 호출)

debounce delay 는 0.1~0.2s 로 가속해서 테스트 시간을 짧게.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from core.knowledge import watcher as watcher_mod


def test_extract_dept_from_reference_path(tmp_path: Path) -> None:
    """`knowledge/reference/<dept>/<...>` 형식에서 dept 추출."""
    ref = tmp_path / "knowledge" / "reference"
    (ref / "wealth_compounding" / "macro").mkdir(parents=True)
    target = ref / "wealth_compounding" / "macro" / "x.md"
    target.write_text("hi", encoding="utf-8")

    assert watcher_mod._extract_dept(target, ref) == "wealth_compounding"


def test_extract_dept_skips_underscore_prefix(tmp_path: Path) -> None:
    """`_inbox/` 같은 _prefix dept 는 None (정책 일관성)."""
    ref = tmp_path / "knowledge" / "reference"
    (ref / "_inbox").mkdir(parents=True)
    target = ref / "_inbox" / "x.md"
    target.write_text("hi", encoding="utf-8")

    assert watcher_mod._extract_dept(target, ref) is None


def test_extract_dept_returns_none_for_outside_path(tmp_path: Path) -> None:
    """reference root 밖의 path 는 None — 잘못된 이벤트 무시."""
    ref = tmp_path / "knowledge" / "reference"
    ref.mkdir(parents=True)
    outside = tmp_path / "other_dir" / "x.md"
    outside.parent.mkdir(parents=True)
    outside.write_text("hi", encoding="utf-8")

    assert watcher_mod._extract_dept(outside, ref) is None


def test_debouncer_coalesces_rapid_events() -> None:
    """같은 dept 에 연속 trigger 시 callback 은 1번만 호출."""
    calls: list[str] = []
    lock = threading.Lock()

    def cb(dept: str) -> None:
        with lock:
            calls.append(dept)

    debouncer = watcher_mod._Debouncer(0.1, cb)
    try:
        debouncer.trigger("dept_a")
        debouncer.trigger("dept_a")
        debouncer.trigger("dept_a")
        time.sleep(0.3)
    finally:
        debouncer.stop()

    with lock:
        assert calls == ["dept_a"]


def test_debouncer_separates_dept_queues() -> None:
    """다른 dept 는 각자 별도 callback."""
    calls: list[str] = []
    lock = threading.Lock()

    def cb(dept: str) -> None:
        with lock:
            calls.append(dept)

    debouncer = watcher_mod._Debouncer(0.1, cb)
    try:
        debouncer.trigger("dept_a")
        debouncer.trigger("dept_b")
        time.sleep(0.3)
    finally:
        debouncer.stop()

    with lock:
        assert set(calls) == {"dept_a", "dept_b"}


def test_debouncer_stop_cancels_pending(monkeypatch: pytest.MonkeyPatch) -> None:
    """stop() 호출 시 대기 중 Timer 가 모두 취소 → callback 미발화."""
    calls: list[str] = []
    debouncer = watcher_mod._Debouncer(0.5, lambda d: calls.append(d))

    debouncer.trigger("dept_a")
    debouncer.trigger("dept_b")
    assert debouncer.pending_depts() == {"dept_a", "dept_b"}

    debouncer.stop()
    time.sleep(0.7)
    assert calls == []
    assert debouncer.pending_depts() == set()


def test_observer_dispatches_on_file_change(tmp_path: Path) -> None:
    """통합: tmp reference dir 감시 → 파일 생성 → 0.2s 후 callback 호출."""
    ref = tmp_path / "knowledge" / "reference"
    (ref / "wealth_compounding").mkdir(parents=True)

    calls: list[str] = []
    lock = threading.Lock()

    def cb(dept: str) -> None:
        with lock:
            calls.append(dept)

    observer = watcher_mod.start_observer(ref, debounce_seconds=0.2, on_sync=cb)
    try:
        target = ref / "wealth_compounding" / "x.md"
        target.write_text("새 자료", encoding="utf-8")

        # watchdog 이벤트 전파 + debounce 만료까지 polling (최대 3s)
        deadline = time.time() + 3.0
        while time.time() < deadline:
            with lock:
                if calls:
                    break
            time.sleep(0.05)
    finally:
        watcher_mod.stop_observer(observer)

    with lock:
        assert calls == ["wealth_compounding"], (
            f"watchdog callback 미호출 또는 dept 추출 실패: calls={calls}"
        )
