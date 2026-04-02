"""Test fixtures for the FastAPI API layer.

Auth middleware is disabled by setting AZURE_AD_TENANT_ID="" in the test
environment. This ensures tests run without real Azure AD credentials.
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

# Disable auth before importing the app
os.environ.setdefault("AZURE_AD_TENANT_ID", "")
os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://fake.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_MODEL_NAME", "gpt-4o")
os.environ.setdefault("ENABLE_VISUAL_ANALYSIS", "false")


@pytest.fixture(scope="session")
def client() -> TestClient:
    from ibcs_agent.api.main import create_app
    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as c:
        yield c
