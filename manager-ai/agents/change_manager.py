from __future__ import annotations

from agents.base_agent import BaseExpertAgent
from tools.graph_tools import SHAREPOINT_SCHEMAS, EMAIL_SCHEMAS


class ChangeManagerAgent(BaseExpertAgent):
    NAME = "change_manager"
    DESCRIPTION = "Change Management, Veränderungsprozesse, Widerstände, Transformations-Roadmaps, ADKAR, Kotter"

    def _get_tools(self) -> list:
        return [*SHAREPOINT_SCHEMAS, *EMAIL_SCHEMAS]
