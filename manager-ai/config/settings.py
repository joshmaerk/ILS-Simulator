from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    In production, secrets are injected via Key Vault references in App Service.
    Locally, use a .env file.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ----------------------------------------------------------
    # Azure AI Foundry
    # ----------------------------------------------------------
    azure_ai_project_endpoint: str = Field(
        ..., description="Azure AI Foundry project endpoint URL"
    )
    azure_openai_deployment: str = Field(
        default="gpt-4o", description="Primary model deployment name"
    )
    azure_openai_mini_deployment: str = Field(
        default="gpt-4o-mini", description="Lightweight model for routing/classification"
    )
    bing_connection_id: str = Field(
        ..., description="Resource ID of the Bing Search connection in AI Foundry"
    )

    # ----------------------------------------------------------
    # Azure Cosmos DB
    # ----------------------------------------------------------
    cosmos_endpoint: str = Field(..., description="Cosmos DB account endpoint URL")
    cosmos_database: str = Field(default="manager-ai")
    cosmos_sessions_container: str = Field(default="sessions")
    cosmos_profiles_container: str = Field(default="user_profiles")
    cosmos_agent_registry_container: str = Field(default="agent_registry")

    # ----------------------------------------------------------
    # Microsoft Graph
    # ----------------------------------------------------------
    graph_tenant_id: str = Field(..., description="Azure AD tenant ID")
    graph_client_id: str = Field(..., description="App registration client ID for Graph")
    graph_client_secret: str = Field(..., description="App registration client secret")

    # ----------------------------------------------------------
    # Teams Bot
    # ----------------------------------------------------------
    bot_app_id: str = Field(..., description="Bot App Registration client ID")
    bot_app_password: str = Field(..., description="Bot App Registration password")
    bot_port: int = Field(default=3978, description="Local dev port")

    # ----------------------------------------------------------
    # Manager context
    # ----------------------------------------------------------
    manager_user_id: str = Field(
        default="", description="AAD Object ID of the manager for Graph API calls"
    )
    manager_name: str = Field(default="Manager")

    # ----------------------------------------------------------
    # Telemetry
    # ----------------------------------------------------------
    applicationinsights_connection_string: str = Field(
        default="", description="Application Insights connection string (optional)"
    )

    # ----------------------------------------------------------
    # Runtime
    # ----------------------------------------------------------
    environment: str = Field(default="development")

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @property
    def log_level(self) -> str:
        return "WARNING" if self.is_production else "DEBUG"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance. Call once at startup."""
    return Settings()
