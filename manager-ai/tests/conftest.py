"""
Shared pytest fixtures for Manager-AI tests.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from config.settings import Settings


@pytest.fixture
def mock_settings() -> Settings:
    """Return a Settings instance with test values (no real Azure required)."""
    with patch.dict(
        "os.environ",
        {
            "AZURE_AI_PROJECT_ENDPOINT": "https://test.services.ai.azure.com/api/projects/test",
            "BING_CONNECTION_ID": "/subscriptions/test/connections/bing",
            "COSMOS_ENDPOINT": "https://test.documents.azure.com:443/",
            "GRAPH_TENANT_ID": "test-tenant",
            "GRAPH_CLIENT_ID": "test-client-id",
            "GRAPH_CLIENT_SECRET": "test-secret",
            "BOT_APP_ID": "test-bot-id",
            "BOT_APP_PASSWORD": "test-bot-password",
        },
    ):
        return Settings()


@pytest.fixture
def mock_cosmos():
    """Return a mock CosmosMemory instance."""
    cosmos = AsyncMock()
    cosmos.get_agent_id = AsyncMock(return_value=None)
    cosmos.save_agent_id = AsyncMock()
    cosmos.get_session = AsyncMock(return_value=None)
    cosmos.upsert_session = AsyncMock()
    cosmos.get_user_profile = AsyncMock(return_value=None)
    cosmos.upsert_user_profile = AsyncMock()
    cosmos.create_default_profile = AsyncMock()
    return cosmos


@pytest.fixture
def mock_ai_client():
    """Return a mock AIProjectClient."""
    client = MagicMock()
    client.agents = MagicMock()
    client.agents.create_agent = MagicMock(return_value=MagicMock(id="agent-123"))
    client.agents.create_thread = MagicMock(return_value=MagicMock(id="thread-456"))
    client.agents.create_message = MagicMock()
    mock_run = MagicMock()
    mock_run.status = "completed"
    mock_run.last_error = None
    client.agents.create_and_process_run = MagicMock(return_value=mock_run)
    mock_messages = MagicMock()
    mock_last_msg = MagicMock()
    mock_last_msg.text.value = "Test response from agent"
    mock_messages.get_last_text_message_by_role = MagicMock(return_value=mock_last_msg)
    client.agents.list_messages = MagicMock(return_value=mock_messages)
    return client
