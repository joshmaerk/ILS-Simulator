"""Tests for configuration management."""

import os
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from ibcs_agent.config import (
    AppConfig,
    AzureConfig,
    AnalysisConfig,
    load_config,
    validate_config,
)


class TestConfigDefaults:
    def test_default_azure_config(self):
        cfg = AppConfig()
        assert cfg.azure.model_name == "gpt-4o"
        assert cfg.azure.openai_api_version == "2024-05-01-preview"

    def test_default_analysis_config(self):
        cfg = AppConfig()
        assert cfg.analysis.max_pages_per_file == 100
        assert cfg.analysis.max_file_size_mb == 50.0
        assert cfg.analysis.top_violations_count == 5

    def test_log_level_default(self):
        assert AppConfig().log_level == "INFO"


class TestConfigFromEnv:
    def test_reads_openai_endpoint(self):
        with patch.dict(os.environ, {
            "AZURE_OPENAI_ENDPOINT": "https://myresource.openai.azure.com/",
            "AZURE_OPENAI_API_KEY": "abc123",
        }):
            cfg = load_config()
            assert cfg.azure.openai_endpoint == "https://myresource.openai.azure.com/"
            assert cfg.azure.openai_api_key == "abc123"

    def test_reads_model_name(self):
        with patch.dict(os.environ, {"AZURE_OPENAI_MODEL_NAME": "gpt-4o-mini"}):
            cfg = load_config()
            assert cfg.azure.model_name == "gpt-4o-mini"

    def test_reads_analysis_flags(self):
        with patch.dict(os.environ, {
            "ENABLE_VISUAL_ANALYSIS": "false",
            "MAX_PAGES_PER_FILE": "50",
        }):
            cfg = load_config()
            assert cfg.analysis.enable_visual_analysis is False
            assert cfg.analysis.max_pages_per_file == 50


class TestConfigFromYaml:
    def test_yaml_overrides_defaults(self, tmp_path: Path):
        yaml_content = textwrap.dedent("""\
            azure:
              model_name: gpt-4-turbo
              openai_endpoint: https://yaml-endpoint.openai.azure.com/
            analysis:
              max_pages_per_file: 25
            log_level: DEBUG
        """)
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        cfg = load_config(config_yaml_path=str(config_file))
        assert cfg.azure.model_name == "gpt-4-turbo"
        assert cfg.analysis.max_pages_per_file == 25
        assert cfg.log_level == "DEBUG"

    def test_env_overrides_yaml(self, tmp_path: Path):
        """Environment variables take precedence over YAML."""
        yaml_content = "azure:\n  model_name: gpt-4-turbo\n"
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml_content)

        with patch.dict(os.environ, {"AZURE_OPENAI_MODEL_NAME": "gpt-4o-mini"}):
            cfg = load_config(config_yaml_path=str(config_file))
            # Env var wins
            assert cfg.azure.model_name == "gpt-4o-mini"


class TestValidateConfig:
    def test_valid_config_no_errors(self):
        cfg = AppConfig()
        cfg.azure.openai_endpoint = "https://test.openai.azure.com/"
        cfg.azure.openai_api_key = "test-key"
        cfg.azure.model_name = "gpt-4o"
        errors = validate_config(cfg)
        assert errors == []

    def test_missing_endpoint_error(self):
        cfg = AppConfig()
        cfg.azure.openai_endpoint = ""
        cfg.azure.openai_api_key = "test-key"
        errors = validate_config(cfg)
        assert any("AZURE_OPENAI_ENDPOINT" in e for e in errors)

    def test_missing_credentials_error(self):
        cfg = AppConfig()
        cfg.azure.openai_endpoint = "https://test.openai.azure.com/"
        cfg.azure.openai_api_key = ""
        cfg.azure.connection_string = ""
        errors = validate_config(cfg)
        assert any("API_KEY" in e or "CONNECTION_STRING" in e for e in errors)

    def test_valid_with_connection_string(self):
        cfg = AppConfig()
        cfg.azure.openai_endpoint = "https://test.openai.azure.com/"
        cfg.azure.connection_string = "some-connection-string"
        cfg.azure.openai_api_key = ""
        errors = validate_config(cfg)
        assert errors == []
