"""Telegram 봇 (BRIEFING-ON-DEMAND-001).

FastAPI lifespan 에서 `build_application()` + `run_polling_forever(app)` 조합으로
long-polling 태스크 기동. 토큰 미설정 시 `build_application()` 이 None 반환하여
봇만 비활성화 (API 는 정상).
"""
from server.telegram.bot import build_application, run_polling_forever

__all__ = ["build_application", "run_polling_forever"]
