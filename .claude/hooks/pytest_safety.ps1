$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$raw = [Console]::In.ReadToEnd()
if (-not $raw) { exit 0 }
try { $data = $raw | ConvertFrom-Json } catch { exit 0 }
$cmd = $data.tool_input.command
if (-not $cmd) { exit 0 }

# 따옴표/here-string 인자 제거 후 검사 — 커밋 메시지 등 인용 문자열 안의 "pytest" 단어를
# 명령으로 오인하던 오탐 방지. (TESTING 확인은 아래에서 원본 $cmd 로 — '1' 따옴표 보존)
$scan = $cmd
$scan = [regex]::Replace($scan, "@'[\s\S]*?'@", ' ')   # PS here-string @'...'@
$scan = [regex]::Replace($scan, '@"[\s\S]*?"@', ' ')   # PS here-string @"..."@
$scan = [regex]::Replace($scan, "'[^']*'", ' ')        # 작은따옴표 인자
$scan = [regex]::Replace($scan, '"[^"]*"', ' ')        # 큰따옴표 인자

# pytest 호출 감지: bare pytest / python -m pytest / uv run pytest (인용 제거된 $scan 기준)
$is_pytest = ($scan -match '(^|[\s;&|])pytest(\s|$)') `
          -or ($scan -match '\bpython\s+(-\S+\s+)*-m\s+pytest\b') `
          -or ($scan -match '\buv\s+run\s+(?:[^|;&]+\s+)?pytest\b')
if (-not $is_pytest) { exit 0 }

# TESTING=1 acknowledgment 검사 (POSIX 'TESTING=1 ...' 또는 PS '$env:TESTING=''1''; ...')
$has_testing = ($cmd -match '(?<![\w.])TESTING\s*=\s*[''"]?1[''"]?') `
            -or ($cmd -match '\$env:TESTING\s*=\s*[''"]1[''"]')
if ($has_testing) { exit 0 }

[Console]::Error.WriteLine('[hook BLOCKED] pytest 호출에 TESTING=1 acknowledgment 가 없습니다.')
[Console]::Error.WriteLine('실제 외부 API (Telegram/KIS/Gemini/Anthropic) 호출 사고 방지를 위해 다음 중 하나로 재시도하세요:')
[Console]::Error.WriteLine('  PowerShell: $env:TESTING=''1''; pytest ...')
[Console]::Error.WriteLine('  POSIX bash: TESTING=1 pytest ...')
[Console]::Error.WriteLine('테스트/conftest.py 가 TESTING=1 일 때 실 API 호출을 mock 처리하도록 보장하세요.')
exit 2
