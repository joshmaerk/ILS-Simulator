"""
Integration tests for the OrchestratorAgent.
Uses mocked Azure SDK clients.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from orchestrator.orchestrator_agent import OrchestratorAgent
from orchestrator.router import IntentRouter
from memory.memory_manager import MemoryManager
from agents.base_agent import BaseExpertAgent


class MockExpertAgent(BaseExpertAgent):
    NAME = "strategist"
    DESCRIPTION = "Mock strategist for testing"

    def __init__(self, response: str = "Mock strategic response"):
        self._response = response

    def _get_tools(self) -> list:
        return []

    async def run(self, thread_id: str, message: str) -> str:
        return self._response

    async def get_or_create_agent_id(self) -> str:
        return "mock-agent-id"


@pytest.mark.asyncio
async def test_dispatch_returns_response(mock_cosmos):
    """Orchestrator should return a consolidated response."""
    mock_memory = AsyncMock(spec=MemoryManager)
    mock_memory.get_or_create_thread_id = AsyncMock(return_value="thread-1")
    mock_memory.get_context_injection = AsyncMock(return_value="")
    mock_memory.summarize_and_persist = AsyncMock()

    mock_router = AsyncMock(spec=IntentRouter)
    mock_router.classify = AsyncMock(return_value=["strategist"])

    agents = {"strategist": MockExpertAgent("Strategic advice here")}

    orchestrator = OrchestratorAgent(
        client=MagicMock(),
        agents=agents,
        memory=mock_memory,
        router=mock_router,
    )

    result = await orchestrator.dispatch(
        user_id="user-1",
        conversation_id="conv-1",
        message="Was ist unsere langfristige Strategie?",
    )

    assert "Strategic advice here" in result
    mock_memory.get_or_create_thread_id.assert_called_once()
    mock_router.classify.assert_called_once()


@pytest.mark.asyncio
async def test_dispatch_handles_agent_failure(mock_cosmos):
    """Orchestrator should handle agent failures gracefully."""
    class FailingAgent(MockExpertAgent):
        async def run(self, thread_id: str, message: str) -> str:
            raise RuntimeError("Agent unavailable")

    mock_memory = AsyncMock(spec=MemoryManager)
    mock_memory.get_or_create_thread_id = AsyncMock(return_value="thread-1")
    mock_memory.get_context_injection = AsyncMock(return_value="")
    mock_memory.summarize_and_persist = AsyncMock()

    mock_router = AsyncMock(spec=IntentRouter)
    mock_router.classify = AsyncMock(return_value=["strategist"])

    orchestrator = OrchestratorAgent(
        client=MagicMock(),
        agents={"strategist": FailingAgent()},
        memory=mock_memory,
        router=mock_router,
    )

    result = await orchestrator.dispatch("user-1", "conv-1", "test")

    # Should return an error message, not raise
    assert isinstance(result, str)
    assert len(result) > 0


@pytest.mark.asyncio
async def test_dispatch_with_multiple_agents():
    """Orchestrator should fan out to multiple agents and consolidate."""
    mock_memory = AsyncMock(spec=MemoryManager)
    mock_memory.get_or_create_thread_id = AsyncMock(return_value="thread-1")
    mock_memory.get_context_injection = AsyncMock(return_value="")
    mock_memory.summarize_and_persist = AsyncMock()

    mock_router = AsyncMock(spec=IntentRouter)
    mock_router.classify = AsyncMock(return_value=["strategist", "controller"])

    class ControllerAgent(MockExpertAgent):
        NAME = "controller"

        async def run(self, thread_id: str, message: str) -> str:
            return "Budget analysis: Q3 is on track"

    agents = {
        "strategist": MockExpertAgent("Long-term strategy recommendation"),
        "controller": ControllerAgent("Budget analysis: Q3 is on track"),
    }

    orchestrator = OrchestratorAgent(
        client=MagicMock(),
        agents=agents,
        memory=mock_memory,
        router=mock_router,
    )

    result = await orchestrator.dispatch("user-1", "conv-1", "Strategie und Budget Q3?")

    # Both responses should appear in the consolidated answer
    assert "Long-term strategy" in result
    assert "Budget analysis" in result
