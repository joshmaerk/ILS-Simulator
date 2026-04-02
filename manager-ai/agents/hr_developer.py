from __future__ import annotations

from agents.base_agent import BaseExpertAgent
from tools.graph_tools import SHAREPOINT_SCHEMAS


class HRDeveloperAgent(BaseExpertAgent):
    NAME = "hr_developer"
    DESCRIPTION = "Personalentwicklung, Talentmanagement, Entwicklungspläne, Kompetenzmodelle, Nachfolgeplanung"

    def _get_tools(self) -> list:
        return [*SHAREPOINT_SCHEMAS]
