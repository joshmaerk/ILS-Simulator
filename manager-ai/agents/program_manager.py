from __future__ import annotations

from agents.base_agent import BaseExpertAgent
from tools.graph_tools import CALENDAR_SCHEMAS, SHAREPOINT_SCHEMAS


class ProgramManagerAgent(BaseExpertAgent):
    NAME = "program_manager"
    DESCRIPTION = "Portfolio-Steuerung, Programm-Governance, Abhängigkeiten, PMO, Benefits Realization, Priorisierung"

    def _get_tools(self) -> list:
        return [*CALENDAR_SCHEMAS, *SHAREPOINT_SCHEMAS]
