"""
High-level memory management for the Manager-AI system.

Responsibilities:
- Map Teams conversation IDs to Azure AI Foundry thread IDs
- Inject long-term user context into agent threads
- Persist new facts and insights from conversations
"""

from __future__ import annotations

import logging
from uuid import uuid4

from memory.cosmos_memory import CosmosMemory
from memory.schemas import MemoryFact, SessionDocument, UserProfileDocument

logger = logging.getLogger(__name__)


class MemoryManager:
    """
    Orchestrates session state and user profile memory.
    """

    def __init__(self, cosmos: CosmosMemory) -> None:
        self._cosmos = cosmos

    async def get_or_create_thread_id(
        self,
        user_id: str,
        conversation_id: str,
        create_foundry_thread_fn=None,
    ) -> str:
        """
        Return the Foundry thread ID for this conversation.
        If none exists, create a new thread via `create_foundry_thread_fn` and persist it.
        """
        session = await self._cosmos.get_session(user_id, conversation_id)

        if session and session.foundry_thread_id:
            return session.foundry_thread_id

        # Create a new Foundry thread
        if create_foundry_thread_fn:
            thread = await create_foundry_thread_fn()
            thread_id = thread.id
        else:
            thread_id = str(uuid4())  # fallback for testing without real Foundry

        new_session = SessionDocument(
            id=conversation_id,
            userId=user_id,
            conversation_id=conversation_id,
            foundry_thread_id=thread_id,
        )
        await self._cosmos.upsert_session(new_session)
        logger.info("Created new Foundry thread %s for conversation %s", thread_id, conversation_id)
        return thread_id

    async def get_context_injection(self, user_id: str) -> str:
        """
        Return a compact context string to prepend to agent messages.
        Loaded from the user's persistent profile.
        """
        profile = await self._cosmos.get_user_profile(user_id)
        if not profile:
            return ""
        summary = profile.get_context_summary()
        if not summary:
            return ""
        return (
            f"[Nutzerkontext – bitte berücksichtigen]\n{summary}\n"
            f"[Ende Nutzerkontext]"
        )

    async def get_or_create_profile(
        self, user_id: str, display_name: str = ""
    ) -> UserProfileDocument:
        profile = await self._cosmos.get_user_profile(user_id)
        if not profile:
            profile = await self._cosmos.create_default_profile(user_id, display_name)
        return profile

    async def append_fact(
        self,
        user_id: str,
        category: str,
        content: str,
        source_conversation: str | None = None,
    ) -> None:
        """Add a persistent fact to the user's profile."""
        profile = await self.get_or_create_profile(user_id)
        fact = MemoryFact(
            category=category,
            content=content,
            source_conversation=source_conversation,
        )
        profile.add_fact(fact)
        await self._cosmos.upsert_user_profile(profile)

    async def update_session_activity(
        self, user_id: str, conversation_id: str
    ) -> None:
        """Increment message count and update last_active timestamp."""
        session = await self._cosmos.get_session(user_id, conversation_id)
        if session:
            from datetime import datetime, timezone
            session.message_count += 1
            session.last_active = datetime.now(timezone.utc)
            await self._cosmos.upsert_session(session)

    async def summarize_and_persist(
        self,
        user_id: str,
        conversation_id: str,
        user_message: str,
        assistant_response: str,
    ) -> None:
        """
        Extract key facts from the conversation turn and persist them.
        Currently uses simple heuristics; can be enhanced with an LLM extractor.
        """
        await self.update_session_activity(user_id, conversation_id)

        # Simple heuristic: persist project names mentioned
        # A more sophisticated implementation would call the LLM to extract entities
        keywords_to_categories = {
            "projekt": "project",
            "initiative": "project",
            "programm": "project",
            "budget": "decision",
            "entscheidung": "decision",
            "strategie": "decision",
        }
        lower_msg = user_message.lower()
        for keyword, category in keywords_to_categories.items():
            if keyword in lower_msg and len(user_message) < 200:
                await self.append_fact(
                    user_id=user_id,
                    category=category,
                    content=f"Thema: {user_message[:150]}",
                    source_conversation=conversation_id,
                )
                break  # only one fact per turn from heuristics
