"""Production 채팅 임원 종합 기본 승격 — executive_mode 해석 검증 (2026-07-18).

config chat.executive_mode_default 가 미명시 요청의 기본값을 결정하고,
요청 payload 의 명시값(R&D Off/Flash/Pro 토글)이 항상 우선하는지 검증.
"""
from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("TESTING", "1")

from core.config.schema import RuntimeConfig
from server.api.production_chat import (
    ChatMessage,
    ProductionChatRequest,
    _resolve_executive_mode,
)


def _req(**kwargs) -> ProductionChatRequest:
    return ProductionChatRequest(
        messages=[ChatMessage(role="user", content="삼성전자 어때?")], **kwargs
    )


class TestSchemaDefault:
    def test_chat_config_default_is_executive(self) -> None:
        assert RuntimeConfig().chat.executive_mode_default is True

    def test_request_field_default_is_none(self) -> None:
        """미명시 = None (config 위임). False 하드코딩으로 회귀하면 임원 승격이 무효."""
        assert _req().executive_mode is None


class TestResolveExecutiveMode:
    def test_none_follows_config_true(self) -> None:
        cfg = RuntimeConfig()
        cfg.chat.executive_mode_default = True
        with patch("server.api.production_chat.get_config", return_value=cfg):
            assert _resolve_executive_mode(_req()) is True

    def test_none_follows_config_false(self) -> None:
        cfg = RuntimeConfig()
        cfg.chat.executive_mode_default = False
        with patch("server.api.production_chat.get_config", return_value=cfg):
            assert _resolve_executive_mode(_req()) is False

    def test_explicit_false_overrides_config_true(self) -> None:
        """R&D 토글 Off — config 기본이 임원이어도 formatter 로 강제 가능."""
        cfg = RuntimeConfig()
        cfg.chat.executive_mode_default = True
        with patch("server.api.production_chat.get_config", return_value=cfg):
            assert _resolve_executive_mode(_req(executive_mode=False)) is False

    def test_explicit_true_overrides_config_false(self) -> None:
        cfg = RuntimeConfig()
        cfg.chat.executive_mode_default = False
        with patch("server.api.production_chat.get_config", return_value=cfg):
            assert _resolve_executive_mode(_req(executive_mode=True)) is True
