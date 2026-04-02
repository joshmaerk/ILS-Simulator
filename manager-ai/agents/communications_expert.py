from __future__ import annotations

from agents.base_agent import BaseExpertAgent
from tools.graph_tools import EMAIL_SCHEMAS, SHAREPOINT_SCHEMAS


class CommunicationsExpertAgent(BaseExpertAgent):
    NAME = "communications_expert"
    DESCRIPTION = "Textentwürfe, Kernbotschaften, Stakeholder-Kommunikation, Führungskommunikation, Krisenkommunikation"

    def _get_tools(self) -> list:
        return [*EMAIL_SCHEMAS, *SHAREPOINT_SCHEMAS]
