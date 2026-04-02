"""
Unit tests for MemoryManager.
"""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from memory.memory_manager import MemoryManager
from memory.schemas import SessionDocument, UserProfileDocument, MemoryFact


@pytest.mark.asyncio
async def test_get_or_create_thread_id_creates_new_when_missing(mock_cosmos):
    """Should create a new thread if no session exists."""
    mock_cosmos.get_session = AsyncMock(return_value=None)
    mock_thread = MagicMock()
    mock_thread.id = "new-thread-id"

    async def create_thread():
        return mock_thread

    manager = MemoryManager(mock_cosmos)
    thread_id = await manager.get_or_create_thread_id(
        user_id="user-1",
        conversation_id="conv-1",
        create_foundry_thread_fn=create_thread,
    )

    assert thread_id == "new-thread-id"
    mock_cosmos.upsert_session.assert_called_once()


@pytest.mark.asyncio
async def test_get_or_create_thread_id_returns_existing(mock_cosmos):
    """Should return existing thread ID from session."""
    existing_session = SessionDocument(
        id="conv-1",
        userId="user-1",
        conversation_id="conv-1",
        foundry_thread_id="existing-thread",
    )
    mock_cosmos.get_session = AsyncMock(return_value=existing_session)

    manager = MemoryManager(mock_cosmos)
    thread_id = await manager.get_or_create_thread_id(
        user_id="user-1",
        conversation_id="conv-1",
    )

    assert thread_id == "existing-thread"
    mock_cosmos.upsert_session.assert_not_called()


@pytest.mark.asyncio
async def test_get_context_injection_empty_for_missing_profile(mock_cosmos):
    """Should return empty string if user has no profile."""
    mock_cosmos.get_user_profile = AsyncMock(return_value=None)

    manager = MemoryManager(mock_cosmos)
    context = await manager.get_context_injection("unknown-user")

    assert context == ""


@pytest.mark.asyncio
async def test_get_context_injection_returns_summary(mock_cosmos):
    """Should return context summary for existing profile."""
    profile = UserProfileDocument(
        id="user-1",
        userId="user-1",
        display_name="Max Mustermann",
        role="VP Engineering",
    )
    mock_cosmos.get_user_profile = AsyncMock(return_value=profile)

    manager = MemoryManager(mock_cosmos)
    context = await manager.get_context_injection("user-1")

    assert "Max Mustermann" in context
    assert "VP Engineering" in context


@pytest.mark.asyncio
async def test_append_fact_persists(mock_cosmos):
    """append_fact should create profile and upsert with new fact."""
    mock_cosmos.get_user_profile = AsyncMock(return_value=None)
    created_profile = UserProfileDocument(id="user-1", userId="user-1")
    mock_cosmos.create_default_profile = AsyncMock(return_value=created_profile)

    manager = MemoryManager(mock_cosmos)
    await manager.append_fact("user-1", "project", "Projekt Alpha läuft")

    mock_cosmos.upsert_user_profile.assert_called_once()


def test_user_profile_add_fact_deduplicates():
    """Adding the same fact twice should not duplicate it."""
    profile = UserProfileDocument(id="u1", userId="u1")
    fact = MemoryFact(category="project", content="Projekt Alpha")
    profile.add_fact(fact)
    profile.add_fact(fact)  # duplicate

    assert len([f for f in profile.facts if f.content == "Projekt Alpha"]) == 1
