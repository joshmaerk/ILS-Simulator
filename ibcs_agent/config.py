"""
Configuration management for the IBCS Feedback Agent.

Reads from environment variables (via .env file) or config.yaml.
All Azure credentials and model settings are configured here — nothing is hardcoded.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from dotenv import load_dotenv

# Load .env file if present (local development)
_env_path = Path(__file__).parent / ".env"
if _env_path.exists():
    load_dotenv(_env_path)
else:
    load_dotenv()  # Try default locations


@dataclass
class AzureConfig:
    """Azure AI Foundry and Azure OpenAI configuration."""

    # Azure AI Foundry (azure-ai-projects)
    connection_string: str = ""
    subscription_id: str = ""
    resource_group: str = ""
    project_name: str = ""

    # Azure OpenAI (for GPT-4o Vision)
    openai_endpoint: str = ""
    openai_api_key: str = ""
    openai_api_version: str = "2024-05-01-preview"
    model_name: str = "gpt-4o"

    # Agent identity
    agent_name: str = "IBCS-Feedback-Agent"
    agent_instructions_file: str = ""


@dataclass
class AnalysisConfig:
    """Analysis behavior configuration."""

    # Visual analysis
    enable_visual_analysis: bool = True
    max_image_size_px: int = 1920       # Max dimension for slide images sent to Vision
    image_quality: int = 85             # JPEG quality for slide renders
    visual_analysis_timeout_sec: int = 60

    # Metadata analysis
    enable_metadata_analysis: bool = True

    # Limits
    max_pages_per_file: int = 100       # Skip analysis beyond this page count
    max_file_size_mb: float = 50.0

    # Output
    include_raw_text_in_report: bool = False
    top_violations_count: int = 5


@dataclass
class AppConfig:
    """Root configuration object."""

    azure: AzureConfig = field(default_factory=AzureConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    log_level: str = "INFO"


def _load_from_env() -> AppConfig:
    """Build config from environment variables."""
    cfg = AppConfig()

    # Azure AI Foundry
    cfg.azure.connection_string = os.getenv("AZURE_AI_FOUNDRY_CONNECTION_STRING", "")
    cfg.azure.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID", "")
    cfg.azure.resource_group = os.getenv("AZURE_RESOURCE_GROUP", "")
    cfg.azure.project_name = os.getenv("AZURE_AI_PROJECT_NAME", "")

    # Azure OpenAI
    cfg.azure.openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "")
    cfg.azure.openai_api_key = os.getenv("AZURE_OPENAI_API_KEY", "")
    cfg.azure.openai_api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")
    cfg.azure.model_name = os.getenv("AZURE_OPENAI_MODEL_NAME", "gpt-4o")
    cfg.azure.agent_name = os.getenv("AGENT_NAME", "IBCS-Feedback-Agent")

    # Analysis
    cfg.analysis.enable_visual_analysis = os.getenv("ENABLE_VISUAL_ANALYSIS", "true").lower() == "true"
    cfg.analysis.enable_metadata_analysis = os.getenv("ENABLE_METADATA_ANALYSIS", "true").lower() == "true"
    cfg.analysis.max_pages_per_file = int(os.getenv("MAX_PAGES_PER_FILE", "100"))
    cfg.analysis.max_file_size_mb = float(os.getenv("MAX_FILE_SIZE_MB", "50.0"))
    cfg.analysis.top_violations_count = int(os.getenv("TOP_VIOLATIONS_COUNT", "5"))

    # Logging
    cfg.log_level = os.getenv("LOG_LEVEL", "INFO")

    return cfg


_AZURE_DEFAULTS = AzureConfig()
_ANALYSIS_DEFAULTS = AnalysisConfig()


def _load_from_yaml(path: str) -> AppConfig:
    """Build config from a YAML file.

    Priority: explicit env vars (non-default values) > YAML > class defaults.
    An env var is considered "explicit" when its value differs from the class default,
    which allows YAML to override test/CI defaults that happen to equal the class default.
    """
    cfg = AppConfig()  # Start with class defaults

    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    azure_data = data.get("azure", {})
    if azure_data.get("connection_string"):
        cfg.azure.connection_string = azure_data["connection_string"]
    if azure_data.get("subscription_id"):
        cfg.azure.subscription_id = azure_data["subscription_id"]
    if azure_data.get("resource_group"):
        cfg.azure.resource_group = azure_data["resource_group"]
    if azure_data.get("project_name"):
        cfg.azure.project_name = azure_data["project_name"]
    if azure_data.get("openai_endpoint"):
        cfg.azure.openai_endpoint = azure_data["openai_endpoint"]
    if azure_data.get("openai_api_key"):
        cfg.azure.openai_api_key = azure_data["openai_api_key"]
    if azure_data.get("openai_api_version"):
        cfg.azure.openai_api_version = azure_data["openai_api_version"]
    if azure_data.get("model_name"):
        cfg.azure.model_name = azure_data["model_name"]
    if azure_data.get("agent_name"):
        cfg.azure.agent_name = azure_data["agent_name"]

    analysis_data = data.get("analysis", {})
    if "enable_visual_analysis" in analysis_data:
        cfg.analysis.enable_visual_analysis = analysis_data["enable_visual_analysis"]
    if "enable_metadata_analysis" in analysis_data:
        cfg.analysis.enable_metadata_analysis = analysis_data["enable_metadata_analysis"]
    if "max_pages_per_file" in analysis_data:
        cfg.analysis.max_pages_per_file = analysis_data["max_pages_per_file"]
    if "max_file_size_mb" in analysis_data:
        cfg.analysis.max_file_size_mb = analysis_data["max_file_size_mb"]
    if "top_violations_count" in analysis_data:
        cfg.analysis.top_violations_count = analysis_data["top_violations_count"]

    if "log_level" in data:
        cfg.log_level = data["log_level"]

    # Apply env vars that differ from the class default (explicit overrides win over YAML)
    _e = os.getenv
    if (v := _e("AZURE_AI_FOUNDRY_CONNECTION_STRING")) is not None and v != _AZURE_DEFAULTS.connection_string:
        cfg.azure.connection_string = v
    if (v := _e("AZURE_OPENAI_ENDPOINT")) is not None and v != _AZURE_DEFAULTS.openai_endpoint:
        cfg.azure.openai_endpoint = v
    if (v := _e("AZURE_OPENAI_API_KEY")) is not None and v != _AZURE_DEFAULTS.openai_api_key:
        cfg.azure.openai_api_key = v
    if (v := _e("AZURE_OPENAI_MODEL_NAME")) is not None and v != _AZURE_DEFAULTS.model_name:
        cfg.azure.model_name = v
    if (v := _e("AGENT_NAME")) is not None and v != _AZURE_DEFAULTS.agent_name:
        cfg.azure.agent_name = v
    if (v := _e("ENABLE_VISUAL_ANALYSIS")) is not None:
        env_vis = v.lower() == "true"
        if env_vis != _ANALYSIS_DEFAULTS.enable_visual_analysis:
            cfg.analysis.enable_visual_analysis = env_vis
    if (v := _e("MAX_PAGES_PER_FILE")) is not None:
        env_pages = int(v)
        if env_pages != _ANALYSIS_DEFAULTS.max_pages_per_file:
            cfg.analysis.max_pages_per_file = env_pages
    if (v := _e("LOG_LEVEL")) is not None and v != "INFO":
        cfg.log_level = v

    return cfg


def load_config(config_yaml_path: Optional[str] = None) -> AppConfig:
    """
    Load application configuration.

    Priority (highest to lowest):
    1. Environment variables
    2. config.yaml (if path provided or config.yaml exists next to this file)
    3. Defaults

    Args:
        config_yaml_path: Optional explicit path to config.yaml

    Returns:
        AppConfig instance
    """
    # Explicit path provided
    if config_yaml_path and Path(config_yaml_path).exists():
        return _load_from_yaml(config_yaml_path)

    # Auto-discover config.yaml next to this file
    default_yaml = Path(__file__).parent / "config.yaml"
    if default_yaml.exists():
        return _load_from_yaml(str(default_yaml))

    # Fall back to env-only
    return _load_from_env()


def validate_config(cfg: AppConfig) -> list[str]:
    """
    Validate that all required fields are set.

    Returns:
        List of error messages (empty = valid)
    """
    errors = []

    if not cfg.azure.openai_endpoint:
        errors.append("AZURE_OPENAI_ENDPOINT is not set (required for GPT-4o Vision analysis)")
    if not cfg.azure.openai_api_key and not cfg.azure.connection_string:
        errors.append(
            "Either AZURE_OPENAI_API_KEY or AZURE_AI_FOUNDRY_CONNECTION_STRING must be set"
        )
    if cfg.analysis.enable_visual_analysis and not cfg.azure.model_name:
        errors.append("AZURE_OPENAI_MODEL_NAME is not set (required for visual analysis)")

    return errors


# Module-level singleton (lazy loaded)
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Return the global config singleton."""
    global _config
    if _config is None:
        _config = load_config()
    return _config
