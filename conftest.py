"""Shared test setup. Being at the repository root also lets plain `pytest` import `tests` and `workbot`."""

import pytest


@pytest.fixture(autouse=True)
def offline_test_environment(tmp_path_factory, monkeypatch):
    # workbot.main loads .env on import, so real settings can be in the environment.
    # An empty key, unlike a removed one, also survives a later load_dotenv().
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    monkeypatch.setenv("QDRANT_URL", "http://127.0.0.1:9")
    monkeypatch.setenv(
        "WORKBOT_DB_PATH", str(tmp_path_factory.getbasetemp() / "unset.sqlite3")
    )
