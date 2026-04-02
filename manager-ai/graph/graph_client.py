"""
Authenticated Microsoft Graph client.
Uses ClientSecretCredential (app-only, client credentials flow).
"""

from __future__ import annotations

import logging
from functools import cached_property

from azure.identity import ClientSecretCredential
from msgraph import GraphServiceClient
from msgraph.generated.models.o_data_errors.o_data_error import ODataError

from config.settings import Settings

logger = logging.getLogger(__name__)

# Microsoft Graph scopes for app-only access
GRAPH_SCOPES = ["https://graph.microsoft.com/.default"]


def build_graph_client(settings: Settings) -> GraphServiceClient:
    """
    Build and return an authenticated Microsoft Graph client.
    Uses ClientSecretCredential (app registration with client secret).
    """
    credential = ClientSecretCredential(
        tenant_id=settings.graph_tenant_id,
        client_id=settings.graph_client_id,
        client_secret=settings.graph_client_secret,
    )
    client = GraphServiceClient(
        credentials=credential,
        scopes=GRAPH_SCOPES,
    )
    logger.info("Graph client initialized for tenant %s", settings.graph_tenant_id)
    return client
