from __future__ import annotations

from agents.base_agent import BaseExpertAgent
from tools.graph_tools import CALENDAR_SCHEMAS, SHAREPOINT_SCHEMAS


class ProjectManagerAgent(BaseExpertAgent):
    NAME = "project_manager"
    DESCRIPTION = "Projektplanung, Meilensteine, Risikomanagement, Ressourcen, Scrum, Kanban, Earned Value"

    def _get_tools(self) -> list:
        return [*CALENDAR_SCHEMAS, *SHAREPOINT_SCHEMAS]
