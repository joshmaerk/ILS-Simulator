from __future__ import annotations

from agents.base_agent import BaseExpertAgent
from tools.search_tools import build_bing_tool
from tools.graph_tools import SHAREPOINT_SCHEMAS


class InnovationScoutAgent(BaseExpertAgent):
    NAME = "innovation_scout"
    DESCRIPTION = "Technologie-Trends, Disruption, Innovationsmanagement, KI, Nachhaltigkeit, digitale Geschäftsmodelle"

    def _get_tools(self) -> list:
        bing = build_bing_tool(self._settings)
        return [*bing.definitions, *SHAREPOINT_SCHEMAS]
