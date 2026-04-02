"""
Orchestrator agent.
Receives every user message, routes to the right expert agents in parallel,
then consolidates their responses into a coherent final answer.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

from azure.ai.projects import AIProjectClient

from agents.base_agent import BaseExpertAgent
from memory.memory_manager import MemoryManager
from orchestrator.consolidator import consolidate_responses
from orchestrator.router import IntentRouter

logger = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    agent_name: str
    response: str
    error: str | None = None


class OrchestratorAgent:
    """
    Central coordinator for the multi-agent system.

    Flow per user message:
    1. Load or create Foundry thread for the conversation
    2. Inject long-term user context
    3. Classify intent -> select 1–3 expert agents
    4. Fan out to agents in parallel (asyncio.gather)
    5. Consolidate responses
    6. Persist memory
    """

    def __init__(
        self,
        client: AIProjectClient,
        agents: dict[str, BaseExpertAgent],
        memory: MemoryManager,
        router: IntentRouter,
    ) -> None:
        self._client = client
        self._agents = agents
        self._memory = memory
        self._router = router

    async def dispatch(
        self,
        user_id: str,
        conversation_id: str,
        message: str,
    ) -> str:
        """
        Process a user message and return a final answer string.
        """
        # 1. Get or create the Foundry thread
        thread_id = await self._memory.get_or_create_thread_id(
            user_id=user_id,
            conversation_id=conversation_id,
            create_foundry_thread_fn=self._create_foundry_thread,
        )

        # 2. Build enriched message with user context
        user_context = await self._memory.get_context_injection(user_id)
        enriched_message = (
            f"{user_context}\n\n{message}" if user_context else message
        )

        # 3. Route to relevant agents
        target_names = await self._router.classify(message)
        logger.info(
            "Routing message from %s -> agents: %s", user_id, target_names
        )

        # 4. Fan out to agents in parallel
        tasks = [
            self._run_agent_safe(name, thread_id, enriched_message)
            for name in target_names
            if name in self._agents
        ]
        if not tasks:
            logger.warning("No valid agents found for names: %s", target_names)
            return "Kein geeigneter Agent für diese Anfrage gefunden."

        results: list[DispatchResult] = await asyncio.gather(*tasks)

        # 5. Consolidate
        successful = {
            r.agent_name: r.response
            for r in results
            if r.error is None and r.response
        }
        if not successful:
            errors = [r.error for r in results if r.error]
            logger.error("All agents failed: %s", errors)
            return "Die Agenten konnten die Anfrage leider nicht verarbeiten. Bitte versuche es erneut."

        final_answer = consolidate_responses(successful)

        # 6. Persist memory (fire-and-forget, don't block the response)
        asyncio.ensure_future(
            self._memory.summarize_and_persist(
                user_id, conversation_id, message, final_answer
            )
        )

        return final_answer

    async def _create_foundry_thread(self):
        """Create a new Azure AI Foundry thread."""
        return self._client.agents.create_thread()

    async def _run_agent_safe(
        self, agent_name: str, thread_id: str, message: str
    ) -> DispatchResult:
        """Run a single agent, catching all exceptions."""
        try:
            response = await asyncio.wait_for(
                self._agents[agent_name].run(thread_id, message),
                timeout=45.0,
            )
            return DispatchResult(agent_name=agent_name, response=response)
        except asyncio.TimeoutError:
            logger.error("Agent '%s' timed out", agent_name)
            return DispatchResult(
                agent_name=agent_name,
                response="",
                error=f"Timeout nach 45 Sekunden",
            )
        except Exception as exc:
            logger.error("Agent '%s' failed: %s", agent_name, exc)
            return DispatchResult(
                agent_name=agent_name,
                response="",
                error=str(exc),
            )
