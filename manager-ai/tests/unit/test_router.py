"""
Unit tests for the IntentRouter.
"""

from __future__ import annotations

import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from orchestrator.router import IntentRouter, AGENT_REGISTRY


def test_agent_registry_completeness():
    """All 10 expert agents must be registered."""
    expected = {
        "strategist", "change_manager", "communications_expert", "controller",
        "hr_developer", "leadership_coach", "project_manager", "program_manager",
        "legal_advisor", "innovation_scout",
    }
    assert set(AGENT_REGISTRY.keys()) == expected


def test_agent_registry_descriptions_not_empty():
    """Every agent must have a non-empty description."""
    for name, desc in AGENT_REGISTRY.items():
        assert desc.strip(), f"Agent '{name}' has empty description"


@pytest.mark.asyncio
async def test_classify_returns_valid_agents(mock_settings, mock_ai_client):
    """Router should return valid agent names from the registry."""
    # Make the mock AI client return a valid JSON array
    mock_last_msg = MagicMock()
    mock_last_msg.text.value = '["strategist", "controller"]'
    mock_messages = MagicMock()
    mock_messages.get_last_text_message_by_role = MagicMock(return_value=mock_last_msg)
    mock_ai_client.agents.list_messages = MagicMock(return_value=mock_messages)

    router = IntentRouter(mock_ai_client, mock_settings)
    result = await router.classify("Wie ist unser Budget für Q3?")

    assert isinstance(result, list)
    assert all(name in AGENT_REGISTRY for name in result)
    assert len(result) <= 3


@pytest.mark.asyncio
async def test_classify_falls_back_on_error(mock_settings, mock_ai_client):
    """Router should return ['strategist'] as fallback on exception."""
    mock_ai_client.agents.create_agent = MagicMock(side_effect=Exception("API error"))

    router = IntentRouter(mock_ai_client, mock_settings)
    result = await router.classify("Some message")

    assert result == ["strategist"]


@pytest.mark.asyncio
async def test_classify_filters_invalid_names(mock_settings, mock_ai_client):
    """Router should filter out any hallucinated agent names."""
    mock_last_msg = MagicMock()
    mock_last_msg.text.value = '["strategist", "fake_agent", "controller"]'
    mock_messages = MagicMock()
    mock_messages.get_last_text_message_by_role = MagicMock(return_value=mock_last_msg)
    mock_ai_client.agents.list_messages = MagicMock(return_value=mock_messages)

    router = IntentRouter(mock_ai_client, mock_settings)
    result = await router.classify("Test")

    assert "fake_agent" not in result
    assert all(name in AGENT_REGISTRY for name in result)
