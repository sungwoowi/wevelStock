"""KNOWLEDGE-SYNC-001 Phase 2 M3 — watchdog Observer + 60s debounce.

흐름:
1. `knowledge/reference/**` 를 watchdog 으로 recursive watch
2. 파일 이벤트 발생 시 path → dept 추출 (relative 첫 segment)
3. dept 단위로 threading.Timer 갱신 (60s debounce — 연속 push 묶음)
4. debounce 만료 시 `sync_dept(dept)` 호출 (M2 함수 재사용)

사용처 2곳 (같은 함수 호출):
- server lifespan startup (`server/main.py`) — 자동 등록
- `just knowledge-watch` standalone — `run_forever()` 진입점

CLI:
    uv run python -m core.knowledge.watcher
    uv run python -m core.knowledge.watcher --debounce 60
"""
from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path
from typing import Any, Callable

from core.knowledge.ingest import REFERENCE_ROOT
from core.knowledge.sync import sync_dept
from core.logging import get_logger

log = get_logger(__name__)


def _extract_dept(path: Path, reference_root: Path) -> str | None:
    """`knowledge/reference/<dept>/...` 에서 dept 추출. 외부 path / _prefix dept 는 None."""
    try:
        rel = Path(path).resolve().relative_to(reference_root.resolve())
    except (ValueError, OSError):
        return None
    parts = rel.parts
    if not parts:
        return None
    dept = parts[0]
    if dept.startswith("_"):
        return None
    return dept


class _Debouncer:
    """dept 단위 debounce. 새 이벤트 오면 기존 Timer 취소 + 재시작."""

    def __init__(
        self,
        delay: float,
        callback: Callable[[str], Any],
    ) -> None:
        self.delay = delay
        self.callback = callback
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def trigger(self, dept: str) -> None:
        """dept 에 대한 debounce 시작/재시작."""
        with self._lock:
            existing = self._timers.get(dept)
            if existing is not None:
                existing.cancel()
            timer = threading.Timer(self.delay, self._fire, args=(dept,))
            timer.daemon = True
            self._timers[dept] = timer
            timer.start()

    def _fire(self, dept: str) -> None:
        with self._lock:
            self._timers.pop(dept, None)
        try:
            log.info("watcher_debounce_fired", dept=dept)
            self.callback(dept)
        except Exception as e:  # noqa: BLE001 — callback 실패가 watcher 중단으로 전파되면 안 됨
            log.warning("watcher_callback_failed", dept=dept, error=str(e))

    def stop(self) -> None:
        """대기 중인 Timer 모두 취소 (shutdown 경로)."""
        with self._lock:
            for t in self._timers.values():
                t.cancel()
            self._timers.clear()

    def pending_depts(self) -> set[str]:
        with self._lock:
            return set(self._timers.keys())


def _build_handler(reference_root: Path, debouncer: _Debouncer) -> Any:
    """watchdog FileSystemEventHandler 인스턴스 생성. import 는 함수 내부."""
    from watchdog.events import FileSystemEvent, FileSystemEventHandler

    class _ReferenceChangeHandler(FileSystemEventHandler):
        def on_any_event(self, event: FileSystemEvent) -> None:  # type: ignore[override]
            if event.is_directory:
                return
            event_type = getattr(event, "event_type", "")
            paths: list[Path] = []
            src = getattr(event, "src_path", None)
            if src:
                paths.append(Path(src))
            if event_type == "moved":
                dest = getattr(event, "dest_path", None)
                if dest:
                    paths.append(Path(dest))
            for p in paths:
                dept = _extract_dept(p, reference_root)
                if dept is None:
                    continue
                log.debug(
                    "watcher_event",
                    event_type=event_type,
                    dept=dept,
                    path=str(p),
                )
                debouncer.trigger(dept)

    return _ReferenceChangeHandler()


def start_observer(
    reference_root: Path | None = None,
    *,
    debounce_seconds: float = 60.0,
    on_sync: Callable[[str], Any] | None = None,
) -> Any:
    """watchdog Observer 시작. server lifespan / standalone 양쪽 진입점.

    `on_sync` 는 debounce 만료 시 호출 (dept 인자, 기본은 `sync_dept(dept)`).
    Observer 반환 — 호출처가 `stop_observer(observer)` 로 정리.
    """
    from watchdog.observers import Observer

    ref = (reference_root or REFERENCE_ROOT).resolve()
    if not ref.exists():
        log.warning("watcher_reference_root_missing", path=str(ref))
        ref.mkdir(parents=True, exist_ok=True)

    callback = on_sync or (lambda dept: sync_dept(dept))
    debouncer = _Debouncer(debounce_seconds, callback)
    handler = _build_handler(ref, debouncer)
    observer = Observer()
    observer.schedule(handler, str(ref), recursive=True)
    observer.start()
    # 정리 경로에서 debouncer 도 함께 stop 하기 위해 observer 에 attach
    observer._wevel_debouncer = debouncer  # type: ignore[attr-defined]
    log.info(
        "watcher_started",
        reference_root=str(ref),
        debounce_seconds=debounce_seconds,
    )
    return observer


def stop_observer(observer: Any) -> None:
    """Observer + debouncer 정리. 멱등."""
    if observer is None:
        return
    try:
        debouncer = getattr(observer, "_wevel_debouncer", None)
        if debouncer is not None:
            debouncer.stop()
        observer.stop()
        observer.join(timeout=2.0)
        log.info("watcher_stopped")
    except Exception as e:  # noqa: BLE001
        log.warning("watcher_stop_failed", error=str(e))


def run_forever(
    reference_root: Path | None = None,
    *,
    debounce_seconds: float = 60.0,
) -> None:
    """standalone 진입점. `just knowledge-watch` 가 호출.

    Ctrl-C 까지 무한 대기. shutdown 시 Observer + Debouncer 정리.
    """
    ref = (reference_root or REFERENCE_ROOT).resolve()
    observer = start_observer(ref, debounce_seconds=debounce_seconds)
    print(f"[knowledge-watch] watching {ref}")
    print(f"[knowledge-watch] debounce={debounce_seconds}s · Ctrl-C to stop")
    try:
        while True:
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n[knowledge-watch] stopping...")
    finally:
        stop_observer(observer)


def _cli() -> None:
    parser = argparse.ArgumentParser(
        description="KNOWLEDGE-SYNC-001 M3 — watchdog Observer + 60s debounce.",
    )
    parser.add_argument(
        "--reference-root",
        type=Path,
        default=None,
        help="감시 루트 (default: knowledge/reference)",
    )
    parser.add_argument(
        "--debounce",
        type=float,
        default=60.0,
        help="debounce 초 (default: 60)",
    )
    args = parser.parse_args()
    run_forever(args.reference_root, debounce_seconds=args.debounce)


if __name__ == "__main__":
    _cli()
