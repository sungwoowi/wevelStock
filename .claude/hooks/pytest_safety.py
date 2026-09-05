#!/usr/bin/env python3
"""pytest_safety — PreToolUse 훅: TESTING=1 acknowledgment 없는 pytest 호출 차단.

실제 외부 API (Telegram/KIS/Gemini/Anthropic) 실호출 사고 방지.
사고 전적: 테스트가 mock 없이 실 BOT_TOKEN 으로 사용자 카톡에 스팸 발송
(BRIEFING-ON-DEMAND-001 v1).

크로스 플랫폼 (Windows PowerShell / macOS·Linux bash 양쪽).
의존성 없음 — 표준 라이브러리만 사용하므로 어떤 python3 로도 실행 가능.
"""

from __future__ import annotations

import json
import re
import sys

# 인용 문자열 제거용 패턴. 커밋 메시지 등 인용 안의 "pytest" 를
# 명령으로 오인하던 오탐을 막는다.
_QUOTE_STRIPPERS: tuple[re.Pattern[str], ...] = (
    re.compile(r"@'[\s\S]*?'@"),  # PowerShell here-string @'...'@
    re.compile(r'@"[\s\S]*?"@'),  # PowerShell here-string @"..."@
    re.compile(r"'[^']*'"),  # 작은따옴표 인자
    re.compile(r'"[^"]*"'),  # 큰따옴표 인자
)

# bash heredoc: <<EOF / <<-'EOF' / <<"EOF" ... 종료 라벨까지.
# macOS·Linux 에서 다중 라인 문자열의 기본 수단이라 반드시 벗겨야 한다.
_HEREDOC = re.compile(
    r"<<-?\s*(['\"]?)(?P<label>[A-Za-z_][A-Za-z0-9_]*)\1[\s\S]*?^\s*(?P=label)\s*$",
    re.MULTILINE,
)

# pytest 호출 감지 (인용 제거된 텍스트 기준)
_PYTEST_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(^|[\s;&|])pytest(\s|$)"),
    re.compile(r"\bpython\s+(-\S+\s+)*-m\s+pytest\b"),
    re.compile(r"\buv\s+run\s+(?:[^|;&]+\s+)?pytest\b"),
)

# TESTING=1 acknowledgment (POSIX 'TESTING=1 ...' 또는 PS '$env:TESTING=''1''; ...')
_TESTING_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?<![\w.])TESTING\s*=\s*['\"]?1['\"]?"),
    re.compile(r"\$env:TESTING\s*=\s*['\"]1['\"]"),
)

_BLOCK_MESSAGE = """[hook BLOCKED] pytest 호출에 TESTING=1 acknowledgment 가 없습니다.
실제 외부 API (Telegram/KIS/Gemini/Anthropic) 호출 사고 방지를 위해 다음 중 하나로 재시도하세요:
  POSIX bash: TESTING=1 pytest ...
  PowerShell: $env:TESTING='1'; pytest ...
테스트/conftest.py 가 TESTING=1 일 때 실 API 호출을 mock 처리하도록 보장하세요."""


def strip_quoted(command: str) -> str:
    """인용 문자열·heredoc 을 공백으로 치환해 오탐을 제거한다."""
    scan = _HEREDOC.sub(" ", command)
    for pattern in _QUOTE_STRIPPERS:
        scan = pattern.sub(" ", scan)
    return scan


def is_pytest_call(command: str) -> bool:
    scan = strip_quoted(command)
    return any(pattern.search(scan) for pattern in _PYTEST_PATTERNS)


def has_testing_ack(command: str) -> bool:
    """원본 command 기준 — 인용 제거 시 '1' 따옴표가 사라지기 때문."""
    return any(pattern.search(command) for pattern in _TESTING_PATTERNS)


def main() -> int:
    # 한글 차단 메시지가 콘솔 기본 인코딩(Windows cp949 등)에서 깨지지 않도록 강제.
    for stream in (sys.stdin, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    raw = sys.stdin.read()
    if not raw:
        return 0
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = (data.get("tool_input") or {}).get("command")
    if not command:
        return 0

    if not is_pytest_call(command):
        return 0
    if has_testing_ack(command):
        return 0

    print(_BLOCK_MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
