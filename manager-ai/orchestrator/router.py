"""
Intent classification router.
Uses a lightweight gpt-4o-mini call to identify which expert agents
should handle a given user message.
"""

from __future__ import annotations

import json
import logging
import re

from azure.ai.projects import AIProjectClient

from config.settings import Settings

logger = logging.getLogger(__name__)

# Registry of all agents with their routing descriptions
AGENT_REGISTRY: dict[str, str] = {
    "strategist": "Langfristige Strategie, Wettbewerbsanalyse, Marktpositionierung, SWOT, strategische Roadmaps",
    "change_manager": "Change Management, Veränderungsprozesse, Widerstände, Transformations-Roadmaps",
    "communications_expert": "Textentwürfe, Kernbotschaften, Stakeholder-Kommunikation, Führungskommunikation, Krisenkommunikation",
    "controller": "Budget, KPIs, Reporting, Abweichungsanalyse, Forecasting, Investitionsrechnung",
    "hr_developer": "Personalentwicklung, Talentmanagement, Entwicklungspläne, Kompetenzmodelle, Nachfolgeplanung",
    "leadership_coach": "Führungsberatung, Konfliktlösung, Team-Dynamik, Coaching, Motivation, Resilienz",
    "project_manager": "Projektplanung, Meilensteine, Risikomanagement, Ressourcen, Scrum, Kanban",
    "program_manager": "Portfolio-Steuerung, Programm-Governance, Abhängigkeiten, PMO, Priorisierung",
    "legal_advisor": "Compliance, Vertragsrecht, DSGVO, Arbeitsrecht, Corporate Governance, Haftung",
    "innovation_scout": "Technologie-Trends, Disruption, Innovationsmanagement, KI, digitale Geschäftsmodelle",
}

_ROUTER_INSTRUCTIONS = """
Du bist ein Routing-Classifier für ein Management-KI-System.
Gegeben eine Anfrage einer Führungskraft: Wähle die 1–3 am besten geeigneten Agenten aus.

Verfügbare Agenten:
{agent_list}

Antworte NUR mit einem JSON-Array der Agentennamen, z.B.:
["strategist", "controller"]

Keine Erklärung, kein Text außer dem JSON-Array.
"""


class IntentRouter:
    """
    Classifies user messages to identify which expert agents to invoke.
    Maintains a cached router agent in AI Foundry.
    """

    def __init__(self, client: AIProjectClient, settings: Settings) -> None:
        self._client = client
        self._settings = settings
        self._router_agent_id: str | None = None

    def _build_instructions(self) -> str:
        agent_list = "\n".join(
            f"- {name}: {desc}" for name, desc in AGENT_REGISTRY.items()
        )
        return _ROUTER_INSTRUCTIONS.format(agent_list=agent_list)

    async def _get_router_agent_id(self) -> str:
        if self._router_agent_id:
            return self._router_agent_id
        agent = self._client.agents.create_agent(
            model=self._settings.azure_openai_mini_deployment,
            name="__router__",
            instructions=self._build_instructions(),
        )
        self._router_agent_id = agent.id
        logger.info("Router agent created: %s", agent.id)
        return self._router_agent_id

    async def classify(self, message: str) -> list[str]:
        """
        Return a list of 1–3 agent names that should handle the message.
        Falls back to ["strategist"] on any error.
        """
        try:
            agent_id = await self._get_router_agent_id()
            thread = self._client.agents.create_thread()
            self._client.agents.create_message(
                thread_id=thread.id,
                role="user",
                content=message,
            )
            self._client.agents.create_and_process_run(
                thread_id=thread.id,
                agent_id=agent_id,
            )
            messages = self._client.agents.list_messages(thread_id=thread.id)
            last = messages.get_last_text_message_by_role("assistant")
            if not last:
                return ["strategist"]

            raw = last.text.value.strip()
            match = re.search(r"\[.*?\]", raw, re.DOTALL)
            if match:
                names: list[str] = json.loads(match.group())
                valid = [n for n in names if n in AGENT_REGISTRY]
                if valid:
                    logger.debug("Routing '%s' -> %s", message[:60], valid)
                    return valid[:3]

        except Exception as exc:
            logger.warning("Router failed, using default: %s", exc)

        return ["strategist"]
