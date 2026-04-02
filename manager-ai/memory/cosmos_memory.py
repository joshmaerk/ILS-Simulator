"""
Async Cosmos DB adapter for Manager-AI.
Provides CRUD operations for sessions, user profiles, and agent registry.
Uses DefaultAzureCredential (Managed Identity in production, CLI token locally).
"""

from __future__ import annotations

import logging
from typing import Any

from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential

from config.settings import Settings
from memory.schemas import (
    AgentRegistryDocument,
    SessionDocument,
    UserProfileDocument,
)

logger = logging.getLogger(__name__)


class CosmosMemory:
    """
    Thread-safe async Cosmos DB client wrapper.
    Call `await cosmos.init()` once at application startup,
    and `await cosmos.close()` on shutdown.
    """

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._credential: DefaultAzureCredential | None = None
        self._client: CosmosClient | None = None
        self._db = None
        self._sessions = None
        self._profiles = None
        self._agents = None

    async def init(self) -> None:
        """Initialize the Cosmos DB client and container references."""
        self._credential = DefaultAzureCredential()
        self._client = CosmosClient(
            url=self._settings.cosmos_endpoint,
            credential=self._credential,
        )
        self._db = self._client.get_database_client(self._settings.cosmos_database)
        self._sessions = self._db.get_container_client(
            self._settings.cosmos_sessions_container
        )
        self._profiles = self._db.get_container_client(
            self._settings.cosmos_profiles_container
        )
        self._agents = self._db.get_container_client(
            self._settings.cosmos_agent_registry_container
        )
        logger.info("CosmosMemory initialized")

    async def close(self) -> None:
        if self._client:
            await self._client.close()
        if self._credential:
            await self._credential.close()

    # ----------------------------------------------------------
    # Sessions
    # ----------------------------------------------------------

    async def get_session(self, user_id: str, conversation_id: str) -> SessionDocument | None:
        try:
            item = await self._sessions.read_item(
                item=conversation_id, partition_key=user_id
            )
            return SessionDocument(**item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_session(self, session: SessionDocument) -> None:
        await self._sessions.upsert_item(session.to_cosmos())

    # ----------------------------------------------------------
    # User Profiles
    # ----------------------------------------------------------

    async def get_user_profile(self, user_id: str) -> UserProfileDocument | None:
        try:
            item = await self._profiles.read_item(
                item=user_id, partition_key=user_id
            )
            return UserProfileDocument(**item)
        except CosmosResourceNotFoundError:
            return None

    async def upsert_user_profile(self, profile: UserProfileDocument) -> None:
        await self._profiles.upsert_item(profile.to_cosmos())

    async def create_default_profile(self, user_id: str, display_name: str = "") -> UserProfileDocument:
        profile = UserProfileDocument(
            id=user_id,
            userId=user_id,
            display_name=display_name,
        )
        await self.upsert_user_profile(profile)
        return profile

    # ----------------------------------------------------------
    # Agent Registry
    # ----------------------------------------------------------

    async def get_agent_id(self, agent_name: str) -> str | None:
        try:
            item = await self._agents.read_item(
                item=agent_name, partition_key=agent_name
            )
            return item.get("foundry_agent_id")
        except CosmosResourceNotFoundError:
            return None

    async def save_agent_id(self, agent_name: str, foundry_agent_id: str) -> None:
        doc = AgentRegistryDocument(
            id=agent_name,
            agentName=agent_name,
            foundry_agent_id=foundry_agent_id,
        )
        await self._agents.upsert_item(doc.to_cosmos())

    # ----------------------------------------------------------
    # Generic helpers
    # ----------------------------------------------------------

    async def query_items(
        self,
        container_name: str,
        query: str,
        parameters: list[dict[str, Any]] | None = None,
        partition_key: str | None = None,
    ) -> list[dict]:
        """Execute a parameterized SQL query against the given container."""
        container = self._db.get_container_client(container_name)
        kwargs: dict[str, Any] = {"query": query, "enable_cross_partition_query": True}
        if parameters:
            kwargs["parameters"] = parameters
        if partition_key:
            kwargs["partition_key"] = partition_key
            kwargs.pop("enable_cross_partition_query", None)
        results = []
        async for item in container.query_items(**kwargs):
            results.append(item)
        return results
