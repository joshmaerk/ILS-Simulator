"""
Abstract base class for all expert agents.
Handles agent creation, caching (via Cosmos DB), and running messages.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import RunStatus

from config.settings import Settings
from memory.cosmos_memory import CosmosMemory

logger = logging.getLogger(__name__)

# Timeout for a single agent run (seconds)
AGENT_RUN_TIMEOUT = 45


class BaseExpertAgent(ABC):
    """
    Base class for all expert agents.

    Subclasses must define:
    - NAME: str – unique agent name (matches key in SYSTEM_PROMPTS)
    - DESCRIPTION: str – one-line description used in routing
    - _get_tools() -> list – returns list of tool definition dicts
    """

    NAME: str = ""
    DESCRIPTION: str = ""

    def __init__(
        self,
        client: AIProjectClient,
        settings: Settings,
        cosmos: CosmosMemory,
    ) -> None:
        self._client = client
        self._settings = settings
        self._cosmos = cosmos
        self._agent_id: str | None = None

    async def get_or_create_agent_id(self) -> str:
        """
        Return the Azure AI Foundry agent ID.
        Loads from Cosmos DB cache first; creates new agent if not found.
        """
        if self._agent_id:
            return self._agent_id

        cached_id = await self._cosmos.get_agent_id(self.NAME)
        if cached_id:
            self._agent_id = cached_id
            logger.debug("Loaded agent '%s' from cache: %s", self.NAME, cached_id)
            return self._agent_id

        agent = self._client.agents.create_agent(
            model=self._settings.azure_openai_deployment,
            name=self.NAME,
            instructions=self._get_system_prompt(),
            tools=self._get_tools(),
        )
        self._agent_id = agent.id
        await self._cosmos.save_agent_id(self.NAME, agent.id)
        logger.info("Created agent '%s': %s", self.NAME, agent.id)
        return self._agent_id

    def _get_system_prompt(self) -> str:
        from config.agent_prompts import SYSTEM_PROMPTS
        prompt = SYSTEM_PROMPTS.get(self.NAME, "")
        if not prompt:
            logger.warning("No system prompt found for agent '%s'", self.NAME)
        return prompt

    @abstractmethod
    def _get_tools(self) -> list:
        """Return list of tool definition dicts for this agent."""
        ...

    async def run(self, thread_id: str, message: str) -> str:
        """
        Add a message to the thread and run the agent.
        Returns the agent's text response.
        """
        agent_id = await self.get_or_create_agent_id()

        self._client.agents.create_message(
            thread_id=thread_id,
            role="user",
            content=message,
        )

        run = self._client.agents.create_and_process_run(
            thread_id=thread_id,
            agent_id=agent_id,
        )

        if run.status == RunStatus.FAILED:
            error_msg = run.last_error.message if run.last_error else "Unknown error"
            logger.error("Agent '%s' run failed: %s", self.NAME, error_msg)
            raise RuntimeError(f"Agent '{self.NAME}' failed: {error_msg}")

        messages = self._client.agents.list_messages(thread_id=thread_id)
        last_message = messages.get_last_text_message_by_role("assistant")
        if not last_message:
            return f"[{self.NAME}]: Keine Antwort erhalten."

        response = last_message.text.value
        return self.format_response(response)

    def format_response(self, raw: str) -> str:
        """
        Optional post-processing of the agent response.
        Subclasses can override to add attribution headers, formatting, etc.
        """
        return raw
