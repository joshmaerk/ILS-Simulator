"""
aiohttp web application entry point.
Registers the Bot Framework adapter and exposes /api/messages.
Run locally with: python -m bot.app
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import Any

from aiohttp import web
from aiohttp.web import Request, Response, json_response
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings
from botbuilder.core.integration import aiohttp_error_middleware
from botbuilder.schema import Activity
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

from agents import build_agent_registry
from bot.bot_handler import ManagerBot
from config.settings import get_settings
from graph.calendar_service import CalendarService
from graph.email_service import EmailService
from graph.graph_client import build_graph_client
from graph.sharepoint_service import SharePointService
from memory.cosmos_memory import CosmosMemory
from memory.memory_manager import MemoryManager
from orchestrator.orchestrator_agent import OrchestratorAgent
from orchestrator.router import IntentRouter
from tools.graph_tools import GraphToolHandler

# Configure logging
settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


async def create_app() -> web.Application:
    """
    Application factory.
    Wires up all dependencies and returns a configured aiohttp Application.
    """
    # ----------------------------------------------------------
    # Azure AI Foundry client
    # ----------------------------------------------------------
    credential = DefaultAzureCredential()
    ai_client = AIProjectClient(
        endpoint=settings.azure_ai_project_endpoint,
        credential=credential,
    )

    # ----------------------------------------------------------
    # Cosmos DB memory
    # ----------------------------------------------------------
    cosmos = CosmosMemory(settings)
    await cosmos.init()
    memory = MemoryManager(cosmos)

    # ----------------------------------------------------------
    # Microsoft Graph
    # ----------------------------------------------------------
    graph_client = build_graph_client(settings)
    tenant_domain = f"{settings.graph_tenant_id}.sharepoint.com"

    calendar_service = CalendarService(graph_client, settings.manager_user_id)
    email_service = EmailService(graph_client, settings.manager_user_id)
    sharepoint_service = SharePointService(graph_client, tenant_domain)

    graph_handler = GraphToolHandler(calendar_service, email_service, sharepoint_service)

    # ----------------------------------------------------------
    # Agents + Orchestrator
    # ----------------------------------------------------------
    agents = build_agent_registry(ai_client, settings, cosmos)
    router = IntentRouter(ai_client, settings)
    orchestrator = OrchestratorAgent(ai_client, agents, memory, router)

    # ----------------------------------------------------------
    # Bot Framework Adapter
    # ----------------------------------------------------------
    adapter_settings = BotFrameworkAdapterSettings(
        app_id=settings.bot_app_id,
        app_password=settings.bot_app_password,
    )
    adapter = BotFrameworkAdapter(adapter_settings)

    async def on_error(context, error):
        logger.exception("Unhandled bot error: %s", error)
        await context.send_activity("Ein unerwarteter Fehler ist aufgetreten.")

    adapter.on_turn_error = on_error

    bot = ManagerBot(orchestrator)

    # ----------------------------------------------------------
    # Route handler
    # ----------------------------------------------------------
    async def messages(req: Request) -> Response:
        if "application/json" not in req.headers.get("Content-Type", ""):
            return Response(status=415)

        body: dict[str, Any] = await req.json()
        activity = Activity().deserialize(body)
        auth_header = req.headers.get("Authorization", "")

        invoke_response = await adapter.process_activity(
            activity, auth_header, bot.on_turn
        )
        if invoke_response:
            return json_response(data=invoke_response.body, status=invoke_response.status)
        return Response(status=201)

    async def health(_: Request) -> Response:
        return json_response({"status": "ok", "service": "manager-ai-bot"})

    # ----------------------------------------------------------
    # Application
    # ----------------------------------------------------------
    app = web.Application(middlewares=[aiohttp_error_middleware])
    app.router.add_post("/api/messages", messages)
    app.router.add_get("/health", health)

    async def on_shutdown(application: web.Application) -> None:
        await cosmos.close()
        logger.info("Cosmos client closed")

    app.on_shutdown.append(on_shutdown)

    logger.info("Manager-AI Bot started. POST /api/messages | GET /health")
    return app


if __name__ == "__main__":
    app = asyncio.get_event_loop().run_until_complete(create_app())
    web.run_app(app, host="0.0.0.0", port=settings.bot_port)
