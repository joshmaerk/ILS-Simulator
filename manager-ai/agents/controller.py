from __future__ import annotations

from azure.ai.projects.models import CodeInterpreterTool

from agents.base_agent import BaseExpertAgent
from tools.graph_tools import SHAREPOINT_SCHEMAS
from tools.search_tools import build_bing_tool


class ControllerAgent(BaseExpertAgent):
    NAME = "controller"
    DESCRIPTION = "Budget, KPIs, Reporting, Abweichungsanalyse, Forecasting, Investitionsrechnung, Kostensteuerung"

    def _get_tools(self) -> list:
        bing = build_bing_tool(self._settings)
        code_interpreter = CodeInterpreterTool()
        return [*code_interpreter.definitions, *SHAREPOINT_SCHEMAS, *bing.definitions]
