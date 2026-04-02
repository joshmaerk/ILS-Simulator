"""
Agent registry factory.
Builds a dict[name -> BaseExpertAgent] for use by the Orchestrator.
"""

from __future__ import annotations

from azure.ai.projects import AIProjectClient

from agents.base_agent import BaseExpertAgent
from agents.change_manager import ChangeManagerAgent
from agents.communications_expert import CommunicationsExpertAgent
from agents.controller import ControllerAgent
from agents.hr_developer import HRDeveloperAgent
from agents.innovation_scout import InnovationScoutAgent
from agents.leadership_coach import LeadershipCoachAgent
from agents.legal_advisor import LegalAdvisorAgent
from agents.program_manager import ProgramManagerAgent
from agents.project_manager import ProjectManagerAgent
from agents.strategist import StrategistAgent
from config.settings import Settings
from memory.cosmos_memory import CosmosMemory


def build_agent_registry(
    client: AIProjectClient,
    settings: Settings,
    cosmos: CosmosMemory,
) -> dict[str, BaseExpertAgent]:
    """
    Instantiate all expert agents and return them keyed by NAME.
    """
    agent_classes = [
        StrategistAgent,
        ChangeManagerAgent,
        CommunicationsExpertAgent,
        ControllerAgent,
        HRDeveloperAgent,
        LeadershipCoachAgent,
        ProjectManagerAgent,
        ProgramManagerAgent,
        LegalAdvisorAgent,
        InnovationScoutAgent,
    ]
    return {
        cls.NAME: cls(client=client, settings=settings, cosmos=cosmos)
        for cls in agent_classes
    }
