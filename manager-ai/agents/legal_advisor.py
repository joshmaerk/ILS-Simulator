from __future__ import annotations

from agents.base_agent import BaseExpertAgent
from tools.search_tools import build_bing_tool
from tools.graph_tools import SHAREPOINT_SCHEMAS


class LegalAdvisorAgent(BaseExpertAgent):
    NAME = "legal_advisor"
    DESCRIPTION = "Compliance, Vertragsrecht, DSGVO, Arbeitsrecht, Corporate Governance, Haftung, M&A Grundlagen"

    def _get_tools(self) -> list:
        bing = build_bing_tool(self._settings)
        return [*bing.definitions, *SHAREPOINT_SCHEMAS]

    def format_response(self, raw: str) -> str:
        disclaimer = (
            "\n\n---\n*Hinweis: Diese Ausführungen sind rechtliche Orientierungshilfen "
            "und ersetzen keine verbindliche Rechtsberatung durch einen zugelassenen Anwalt.*"
        )
        if "Hinweis:" not in raw and "ersetzen keine" not in raw:
            return raw + disclaimer
        return raw
