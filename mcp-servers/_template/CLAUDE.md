# {MCP_NAME} MCP Server ({mcp-id})

## 역할
(외부 데이터/서비스 연결 역할 1-2문장)

## 제공 도구 (Tools)
| 도구 이름 | 용도 | 입력 | 출력 |
|---|---|---|---|
| `get_*` | ... | ... | ... |

## 안전장치
- (예: KIS 주문 API 는 KIS_IS_PAPER=true 일 때만 실행)
- (Rate limit, 재시도 정책 등)

## 실행
```bash
uv run python -m mcp_servers.{mcp_id}.src.server
```

## .mcp.json 등록 예시
```json
{
  "mcpServers": {
    "{mcp-id}": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_servers.{mcp_id}.src.server"],
      "env": {
        "SOME_API_KEY": "${SOME_API_KEY}"
      }
    }
  }
}
```
