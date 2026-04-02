"""
Microsoft Graph tools wrapped as Azure AI Foundry FunctionTool definitions.
Each tool definition includes a JSON schema for the AI agent and a callable handler.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from graph.calendar_service import CalendarService
from graph.email_service import EmailService
from graph.sharepoint_service import SharePointService

logger = logging.getLogger(__name__)


# ============================================================
# Tool definitions (JSON Schema for AI Foundry function calling)
# ============================================================

GET_CALENDAR_EVENTS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_calendar_events",
        "description": (
            "Ruft die anstehenden Kalendertermine des Managers für die nächsten N Tage ab. "
            "Nutze dieses Tool wenn nach Terminen, Meetings oder dem Kalender gefragt wird."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Anzahl der Tage in die Zukunft (Standard: 7)",
                    "default": 7,
                }
            },
            "required": [],
        },
    },
}

FIND_FREE_SLOTS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "find_free_slots",
        "description": (
            "Findet freie Zeitfenster im Kalender des Managers für ein Meeting "
            "der angegebenen Dauer."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "duration_minutes": {
                    "type": "integer",
                    "description": "Meetingdauer in Minuten (Standard: 60)",
                    "default": 60,
                },
                "days_ahead": {
                    "type": "integer",
                    "description": "Wie viele Tage vorausplanen (Standard: 5)",
                    "default": 5,
                },
            },
            "required": [],
        },
    },
}

GET_RECENT_EMAILS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_recent_emails",
        "description": (
            "Ruft die neuesten E-Mails aus dem Posteingang des Managers ab. "
            "Nutze dieses Tool wenn nach E-Mails, Nachrichten oder Kommunikation gefragt wird."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "count": {
                    "type": "integer",
                    "description": "Anzahl der E-Mails (Standard: 10, max: 25)",
                    "default": 10,
                }
            },
            "required": [],
        },
    },
}

SEARCH_EMAILS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_emails",
        "description": "Durchsucht E-Mails nach einem Suchbegriff.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Suchbegriff oder Betreff",
                }
            },
            "required": ["query"],
        },
    },
}

SEARCH_SHAREPOINT_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_sharepoint",
        "description": (
            "Durchsucht SharePoint und OneDrive nach Dokumenten. "
            "Nutze dieses Tool wenn nach Dateien, Dokumenten, Präsentationen oder "
            "gespeicherten Informationen gefragt wird."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Suchbegriff für Dokumente",
                },
                "count": {
                    "type": "integer",
                    "description": "Anzahl der Ergebnisse (Standard: 5)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}


# ============================================================
# Tool handler registry
# ============================================================

class GraphToolHandler:
    """
    Executes Graph tool calls made by AI agents.
    """

    def __init__(
        self,
        calendar: CalendarService,
        email: EmailService,
        sharepoint: SharePointService,
    ) -> None:
        self._calendar = calendar
        self._email = email
        self._sharepoint = sharepoint

    async def handle(self, tool_name: str, arguments: str | dict) -> str:
        """
        Dispatch a tool call to the appropriate Graph service.
        Returns a string result for the agent.
        """
        if isinstance(arguments, str):
            try:
                args: dict[str, Any] = json.loads(arguments)
            except json.JSONDecodeError:
                args = {}
        else:
            args = arguments

        handlers = {
            "get_calendar_events": self._get_calendar_events,
            "find_free_slots": self._find_free_slots,
            "get_recent_emails": self._get_recent_emails,
            "search_emails": self._search_emails,
            "search_sharepoint": self._search_sharepoint,
        }

        handler = handlers.get(tool_name)
        if not handler:
            return f"Unbekanntes Tool: {tool_name}"

        try:
            return await handler(**args)
        except Exception as exc:
            logger.error("Tool %s failed: %s", tool_name, exc)
            return f"Fehler beim Ausführen von {tool_name}: {exc}"

    async def _get_calendar_events(self, days: int = 7) -> str:
        events = await self._calendar.get_upcoming_events(days=days)
        return self._calendar.format_events_for_agent(events)

    async def _find_free_slots(
        self, duration_minutes: int = 60, days_ahead: int = 5
    ) -> str:
        slots = await self._calendar.find_free_slots(duration_minutes, days_ahead)
        if not slots:
            return "Keine freien Zeitfenster gefunden."
        lines = [f"Freie Zeitfenster ({duration_minutes} Min.):"]
        for slot in slots:
            lines.append(f"- {slot['start']} bis {slot['end']}")
        return "\n".join(lines)

    async def _get_recent_emails(self, count: int = 10) -> str:
        emails = await self._email.get_recent_emails(count=min(count, 25))
        return self._email.format_emails_for_agent(emails)

    async def _search_emails(self, query: str) -> str:
        emails = await self._email.search_emails(query)
        return self._email.format_emails_for_agent(emails)

    async def _search_sharepoint(self, query: str, count: int = 5) -> str:
        docs = await self._sharepoint.search_documents(query, count=count)
        return self._sharepoint.format_documents_for_agent(docs)


# ============================================================
# Convenience: tool schema lists per agent role
# ============================================================

ALL_GRAPH_SCHEMAS = [
    GET_CALENDAR_EVENTS_SCHEMA,
    FIND_FREE_SLOTS_SCHEMA,
    GET_RECENT_EMAILS_SCHEMA,
    SEARCH_EMAILS_SCHEMA,
    SEARCH_SHAREPOINT_SCHEMA,
]

CALENDAR_SCHEMAS = [GET_CALENDAR_EVENTS_SCHEMA, FIND_FREE_SLOTS_SCHEMA]
EMAIL_SCHEMAS = [GET_RECENT_EMAILS_SCHEMA, SEARCH_EMAILS_SCHEMA]
SHAREPOINT_SCHEMAS = [SEARCH_SHAREPOINT_SCHEMA]
