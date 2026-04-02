"""
Microsoft Graph Email service.
Provides email read and search operations.
"""

from __future__ import annotations

import logging

from msgraph import GraphServiceClient
from msgraph.generated.users.item.messages.messages_request_builder import (
    MessagesRequestBuilder,
)

logger = logging.getLogger(__name__)


class EmailService:
    def __init__(self, client: GraphServiceClient, manager_user_id: str) -> None:
        self._client = client
        self._user_id = manager_user_id

    async def get_recent_emails(self, count: int = 10, folder: str = "inbox") -> list[dict]:
        """Return the most recent emails from a mailbox folder."""
        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            select=["subject", "from", "receivedDateTime", "isRead", "importance", "bodyPreview"],
            top=count,
            orderby=["receivedDateTime desc"],
        )
        request_config = (
            MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
                query_parameters=query_params
            )
        )

        try:
            result = await (
                self._client.users.by_user_id(self._user_id)
                .mail_folders.by_mail_folder_id(folder)
                .messages.get(request_configuration=request_config)
            )
            emails = []
            if result and result.value:
                for msg in result.value:
                    emails.append({
                        "subject": msg.subject or "(kein Betreff)",
                        "from": msg.from_.email_address.address if msg.from_ else "",
                        "from_name": msg.from_.email_address.name if msg.from_ else "",
                        "received": str(msg.received_date_time or ""),
                        "is_read": msg.is_read,
                        "importance": str(msg.importance or "normal"),
                        "preview": msg.body_preview or "",
                    })
            return emails
        except Exception as exc:
            logger.error("Failed to fetch emails: %s", exc)
            return []

    async def search_emails(self, query: str, count: int = 5) -> list[dict]:
        """Search emails using KQL query string."""
        query_params = MessagesRequestBuilder.MessagesRequestBuilderGetQueryParameters(
            search=f'"{query}"',
            select=["subject", "from", "receivedDateTime", "bodyPreview"],
            top=count,
        )
        request_config = (
            MessagesRequestBuilder.MessagesRequestBuilderGetRequestConfiguration(
                query_parameters=query_params
            )
        )
        try:
            result = await (
                self._client.users.by_user_id(self._user_id)
                .messages.get(request_configuration=request_config)
            )
            emails = []
            if result and result.value:
                for msg in result.value:
                    emails.append({
                        "subject": msg.subject or "",
                        "from": msg.from_.email_address.address if msg.from_ else "",
                        "received": str(msg.received_date_time or ""),
                        "preview": msg.body_preview or "",
                    })
            return emails
        except Exception as exc:
            logger.error("Failed to search emails: %s", exc)
            return []

    def format_emails_for_agent(self, emails: list[dict]) -> str:
        """Format email list as readable text for agent consumption."""
        if not emails:
            return "Keine E-Mails gefunden."
        lines = ["Aktuelle E-Mails:"]
        for email in emails:
            read_flag = "" if email.get("is_read") else "[Ungelesen] "
            lines.append(
                f"- {read_flag}{email['subject']} | Von: {email['from_name']} | {email['received'][:10]}"
            )
            if email.get("preview"):
                lines.append(f"  Vorschau: {email['preview'][:100]}...")
        return "\n".join(lines)
