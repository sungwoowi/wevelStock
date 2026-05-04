$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
$raw = [Console]::In.ReadToEnd()
if (-not $raw) { exit 0 }
try { $data = $raw | ConvertFrom-Json } catch { exit 0 }
$cmd = $data.tool_input.command
if (-not $cmd) { exit 0 }

# pytest 호출 감지: bare pytest / python -m pytest / uv run pytest
$is_pytest = ($cmd -match '(^|[\s;&|])pytest(\s|$)') `
          -or ($cmd -match '\bpython\s+(-\S+\s+)*-m\s+pytest\b') `
          -or ($cmd -match '\buv\s+run\s+(?:[^|;&]+\s+)?pytest\b')
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
