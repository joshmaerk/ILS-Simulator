"""
Microsoft Graph Calendar service.
Provides calendar operations for the manager's mailbox.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from msgraph import GraphServiceClient
from msgraph.generated.users.item.calendar_view.calendar_view_request_builder import (
    CalendarViewRequestBuilder,
)

logger = logging.getLogger(__name__)


class CalendarService:
    def __init__(self, client: GraphServiceClient, manager_user_id: str) -> None:
        self._client = client
        self._user_id = manager_user_id

    async def get_upcoming_events(self, days: int = 7) -> list[dict]:
        """Return upcoming calendar events for the next N days."""
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days)

        query_params = (
            CalendarViewRequestBuilder.CalendarViewRequestBuilderGetQueryParameters(
                start_date_time=now.isoformat(),
                end_date_time=end.isoformat(),
                select=["subject", "start", "end", "location", "organizer", "attendees"],
                orderby=["start/dateTime"],
                top=20,
            )
        )
        request_config = (
            CalendarViewRequestBuilder.CalendarViewRequestBuilderGetRequestConfiguration(
                query_parameters=query_params
            )
        )

        try:
            result = await (
                self._client.users.by_user_id(self._user_id)
                .calendar_view.get(request_configuration=request_config)
            )
            events = []
            if result and result.value:
                for evt in result.value:
                    events.append({
                        "subject": evt.subject or "",
                        "start": evt.start.date_time if evt.start else "",
                        "end": evt.end.date_time if evt.end else "",
                        "location": evt.location.display_name if evt.location else "",
                        "organizer": evt.organizer.email_address.name if evt.organizer else "",
                        "attendee_count": len(evt.attendees) if evt.attendees else 0,
                    })
            return events
        except Exception as exc:
            logger.error("Failed to fetch calendar events: %s", exc)
            return []

    async def find_free_slots(
        self, duration_minutes: int = 60, days_ahead: int = 5
    ) -> list[dict]:
        """Find free time slots for a meeting of given duration."""
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=days_ahead)

        from msgraph.generated.me.find_meeting_times.find_meeting_times_post_request_body import (
            FindMeetingTimesPostRequestBody,
        )
        from msgraph.generated.models.meeting_time_suggestion_result import (
            MeetingTimeSuggestionResult,
        )
        from msgraph.generated.models.time_constraint import TimeConstraint
        from msgraph.generated.models.time_slot import TimeSlot
        from msgraph.generated.models.date_time_time_zone import DateTimeTimeZone

        body = FindMeetingTimesPostRequestBody(
            meeting_duration=f"PT{duration_minutes}M",
            time_constraint=TimeConstraint(
                time_slots=[
                    TimeSlot(
                        start=DateTimeTimeZone(
                            date_time=now.isoformat(),
                            time_zone="UTC",
                        ),
                        end=DateTimeTimeZone(
                            date_time=end.isoformat(),
                            time_zone="UTC",
                        ),
                    )
                ]
            ),
        )

        try:
            result = await (
                self._client.users.by_user_id(self._user_id)
                .find_meeting_times.post(body)
            )
            slots = []
            if result and result.meeting_time_suggestions:
                for suggestion in result.meeting_time_suggestions[:5]:
                    if suggestion.meeting_time_slot:
                        slots.append({
                            "start": suggestion.meeting_time_slot.start.date_time,
                            "end": suggestion.meeting_time_slot.end.date_time,
                            "confidence": suggestion.confidence,
                        })
            return slots
        except Exception as exc:
            logger.error("Failed to find free slots: %s", exc)
            return []

    def format_events_for_agent(self, events: list[dict]) -> str:
        """Format events list as readable text for agent consumption."""
        if not events:
            return "Keine anstehenden Termine gefunden."
        lines = ["Anstehende Termine:"]
        for evt in events:
            lines.append(
                f"- {evt['subject']} | {evt['start']} | {evt['location'] or 'kein Ort'}"
            )
        return "\n".join(lines)
