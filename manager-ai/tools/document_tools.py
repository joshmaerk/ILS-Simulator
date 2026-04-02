"""
Document analysis tool.
Enables agents to process uploaded files via Azure AI Foundry's
built-in FileSearchTool (vector store backed).
"""

from __future__ import annotations

import logging
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import FileSearchTool, VectorStoreDataSource

logger = logging.getLogger(__name__)


async def upload_document_to_vector_store(
    client: AIProjectClient,
    file_path: str | Path,
    vector_store_name: str = "manager-ai-docs",
) -> tuple[str, str]:
    """
    Upload a document to an AI Foundry vector store.

    Returns:
        (file_id, vector_store_id) tuple
    """
    file_path = Path(file_path)
    with file_path.open("rb") as f:
        uploaded_file = client.agents.upload_file_and_poll(
            file=f,
            purpose="assistants",
        )
    logger.info("Uploaded file %s -> %s", file_path.name, uploaded_file.id)

    # Create or retrieve the vector store
    vector_store = client.agents.create_vector_store_and_poll(
        file_ids=[uploaded_file.id],
        name=vector_store_name,
    )
    logger.info("Vector store: %s", vector_store.id)
    return uploaded_file.id, vector_store.id


def build_file_search_tool(vector_store_ids: list[str]) -> FileSearchTool:
    """
    Return a FileSearchTool for the given vector store IDs.
    Pass `tool.definitions` to the agent's tools list and
    `tool.resources` to the agent's tool_resources.
    """
    return FileSearchTool(vector_store_ids=vector_store_ids)
