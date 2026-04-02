"""
Pydantic models for Cosmos DB documents.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryFact(BaseModel):
    """A single persistent fact about the user or their work context."""

    fact_id: str = Field(default_factory=lambda: str(uuid4()))
    category: str  # e.g. "preference", "project", "decision", "person"
    content: str
    source_conversation: str | None = None
    created_at: datetime = Field(default_factory=_utcnow)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SessionDocument(BaseModel):
    """
    Short-lived session document stored in the 'sessions' Cosmos container.
    TTL = 24 hours (set at container level in Bicep).
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    userId: str  # partition key – must match Cosmos partition key path /userId
    conversation_id: str
    foundry_thread_id: str | None = None
    last_active: datetime = Field(default_factory=_utcnow)
    message_count: int = 0
    pending_context: dict[str, Any] = Field(default_factory=dict)

    def to_cosmos(self) -> dict:
        data = self.model_dump(mode="json")
        data["id"] = self.id
        return data


class UserProfileDocument(BaseModel):
    """
    Persistent user profile stored in the 'user_profiles' Cosmos container.
    No TTL – survives indefinitely.
    """

    id: str  # == userId (one document per user)
    userId: str  # partition key
    display_name: str = ""
    role: str = ""  # e.g. "VP Engineering", "Head of Operations"
    preferences: dict[str, str] = Field(default_factory=dict)
    # e.g. {"response_style": "bullet_points", "language": "de"}
    facts: list[MemoryFact] = Field(default_factory=list)
    active_projects: list[str] = Field(default_factory=list)
    active_initiatives: list[str] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)

    def to_cosmos(self) -> dict:
        data = self.model_dump(mode="json")
        data["id"] = self.id
        return data

    def add_fact(self, fact: MemoryFact) -> None:
        """Add a fact, replacing any existing fact with the same category+content."""
        self.facts = [
            f for f in self.facts
            if not (f.category == fact.category and f.content == fact.content)
        ]
        self.facts.append(fact)
        self.last_updated = _utcnow()

    def get_context_summary(self) -> str:
        """Return a compact context string to inject into agent prompts."""
        lines = []
        if self.display_name:
            lines.append(f"Nutzer: {self.display_name}")
        if self.role:
            lines.append(f"Rolle: {self.role}")
        if self.active_projects:
            lines.append(f"Aktive Projekte: {', '.join(self.active_projects)}")
        if self.active_initiatives:
            lines.append(f"Laufende Initiativen: {', '.join(self.active_initiatives)}")
        if self.preferences:
            prefs = "; ".join(f"{k}={v}" for k, v in self.preferences.items())
            lines.append(f"Präferenzen: {prefs}")
        if self.facts:
            fact_lines = [f"- [{f.category}] {f.content}" for f in self.facts[-10:]]
            lines.append("Bekannte Fakten:\n" + "\n".join(fact_lines))
        return "\n".join(lines)


class AgentRegistryDocument(BaseModel):
    """
    Caches the Azure AI Foundry agent ID for each expert agent.
    Prevents re-creating agents on every app restart.
    """

    id: str  # == agentName
    agentName: str  # partition key
    foundry_agent_id: str
    created_at: datetime = Field(default_factory=_utcnow)

    def to_cosmos(self) -> dict:
        data = self.model_dump(mode="json")
        data["id"] = self.id
        return data
