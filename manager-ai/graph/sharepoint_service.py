"""
Microsoft Graph SharePoint service.
Provides document search and content retrieval.
"""

from __future__ import annotations

import logging

from msgraph import GraphServiceClient

logger = logging.getLogger(__name__)


class SharePointService:
    def __init__(self, client: GraphServiceClient, tenant_domain: str) -> None:
        self._client = client
        self._tenant_domain = tenant_domain  # e.g. "contoso.sharepoint.com"

    async def search_documents(self, query: str, count: int = 5) -> list[dict]:
        """Search SharePoint/OneDrive documents using Microsoft Search."""
        from msgraph.generated.search.query.query_post_request_body import (
            QueryPostRequestBody,
        )
        from msgraph.generated.models.search_request import SearchRequest
        from msgraph.generated.models.entity_type import EntityType

        body = QueryPostRequestBody(
            requests=[
                SearchRequest(
                    entity_types=[EntityType.DriveItem, EntityType.ListItem],
                    query={"query_string": {"query": query}},
                    size=count,
                    fields=["name", "webUrl", "lastModifiedDateTime", "summary"],
                )
            ]
        )

        try:
            result = await self._client.search.query.post(body)
            documents = []
            if result and result.value:
                for hit_container in result.value:
                    if hit_container.hits_containers:
                        for container in hit_container.hits_containers:
                            if container.hits:
                                for hit in container.hits:
                                    documents.append({
                                        "name": hit.resource.additional_data.get("name", ""),
                                        "url": hit.resource.additional_data.get("webUrl", ""),
                                        "modified": hit.resource.additional_data.get(
                                            "lastModifiedDateTime", ""
                                        ),
                                        "summary": hit.summary or "",
                                    })
            return documents
        except Exception as exc:
            logger.error("SharePoint search failed: %s", exc)
            return []

    async def get_site_pages(self, site_id: str, count: int = 10) -> list[dict]:
        """List pages from a SharePoint site."""
        try:
            result = await (
                self._client.sites.by_site_id(site_id)
                .pages.get()
            )
            pages = []
            if result and result.value:
                for page in result.value[:count]:
                    pages.append({
                        "name": page.name or "",
                        "title": page.title or "",
                        "web_url": page.web_url or "",
                        "last_modified": str(page.last_modified_date_time or ""),
                    })
            return pages
        except Exception as exc:
            logger.error("Failed to list site pages: %s", exc)
            return []

    def format_documents_for_agent(self, documents: list[dict]) -> str:
        """Format document list as readable text for agent consumption."""
        if not documents:
            return "Keine Dokumente gefunden."
        lines = ["Gefundene Dokumente:"]
        for doc in documents:
            lines.append(f"- {doc['name']} | {doc['url']}")
            if doc.get("summary"):
                lines.append(f"  {doc['summary'][:150]}")
        return "\n".join(lines)
