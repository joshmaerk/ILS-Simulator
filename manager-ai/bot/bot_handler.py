"""
Teams Bot activity handler.
Receives messages from Teams, delegates to the OrchestratorAgent,
and sends back responses.
"""

from __future__ import annotations

import logging

from botbuilder.core import ActivityHandler, CardFactory, TurnContext
from botbuilder.schema import Activity, ActivityTypes

from orchestrator.orchestrator_agent import OrchestratorAgent

logger = logging.getLogger(__name__)

WELCOME_MESSAGE = (
    "Hallo! Ich bin dein KI-Management-Assistent. "
    "Ich verbinde dich mit Experten für Strategie, Change Management, "
    "Kommunikation, Controlling, Personalentwicklung, Leadership, "
    "Projektmanagement, Recht und Innovation.\n\n"
    "Wie kann ich dir heute helfen?"
)


class ManagerBot(ActivityHandler):
    """
    Main Bot Framework activity handler.
    Handles incoming Teams messages and dispatches them to the Orchestrator.
    """

    def __init__(self, orchestrator: OrchestratorAgent) -> None:
        super().__init__()
        self._orchestrator = orchestrator

    async def on_message_activity(self, turn_context: TurnContext) -> None:
        """Handle a new message from the user."""
        user_id = turn_context.activity.from_property.id
        conversation_id = turn_context.activity.conversation.id
        message = (turn_context.activity.text or "").strip()

        # Remove @mention prefix if present (Teams channels add it)
        if turn_context.activity.entities:
            for entity in turn_context.activity.entities:
                if entity.type == "mention":
                    mention_text = entity.additional_properties.get("text", "")
                    if mention_text:
                        message = message.replace(mention_text, "").strip()

        if not message:
            await turn_context.send_activity("Bitte stelle eine Frage oder beschreibe dein Anliegen.")
            return

        logger.info("Message from user %s in conversation %s", user_id, conversation_id)

        # Send typing indicator
        typing_activity = Activity(type=ActivityTypes.typing)
        await turn_context.send_activity(typing_activity)

        try:
            answer = await self._orchestrator.dispatch(
                user_id=user_id,
                conversation_id=conversation_id,
                message=message,
            )
        except Exception as exc:
            logger.exception("Orchestrator error for user %s: %s", user_id, exc)
            answer = (
                "Es ist ein Fehler aufgetreten. Bitte versuche es erneut oder "
                "kontaktiere den Administrator."
            )

        await turn_context.send_activity(answer)

    async def on_members_added_activity(self, members_added, turn_context: TurnContext) -> None:
        """Greet new users when they join the conversation."""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(WELCOME_MESSAGE)
