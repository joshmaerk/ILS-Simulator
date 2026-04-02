from __future__ import annotations

from agents.base_agent import BaseExpertAgent


class LeadershipCoachAgent(BaseExpertAgent):
    NAME = "leadership_coach"
    DESCRIPTION = "Führungsberatung, Konfliktlösung, Team-Dynamik, Coaching, psychologische Sicherheit, Motivation"

    def _get_tools(self) -> list:
        # Leadership coaching is primarily conversational – no external tools needed
        return []
