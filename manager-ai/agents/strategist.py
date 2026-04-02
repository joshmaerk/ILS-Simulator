from __future__ import annotations

from agents.base_agent import BaseExpertAgent
from tools.search_tools import build_bing_tool
from tools.graph_tools import SHAREPOINT_SCHEMAS


class StrategistAgent(BaseExpertAgent):
    NAME = "strategist"
    DESCRIPTION = "Langfristige Strategie, Wettbewerbsanalyse, Marktpositionierung, SWOT, strategische Roadmaps"

    def _get_tools(self) -> list:
        bing = build_bing_tool(self._settings)
        return [*bing.definitions, *SHAREPOINT_SCHEMAS]
