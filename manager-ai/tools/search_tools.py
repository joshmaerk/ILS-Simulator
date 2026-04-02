"""
Web search tool using Azure AI Foundry's built-in Bing Grounding Tool.
The BingGroundingTool is configured at the agent level and handled
automatically by the Foundry runtime – no custom handler needed.
"""

from __future__ import annotations

from azure.ai.projects.models import BingGroundingTool

from config.settings import Settings


def build_bing_tool(settings: Settings) -> BingGroundingTool:
    """
    Return a BingGroundingTool configured with the Bing Search connection.
    Pass `bing_tool.definitions` to the agent's tools list.
    """
    return BingGroundingTool(connection_id=settings.bing_connection_id)
