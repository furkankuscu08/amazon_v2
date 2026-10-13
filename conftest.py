"""Shared test setup. Being at the repository root also lets plain `pytest` import `tests` and `workbot`."""

import pytest


@pytest.fixture(autouse=True)
def offline_test_environment(tmp_path, monkeypatch):
    # workbot.main loads .env on import, so the real key can be in the environment:
    # remove it, and keep the default database out of reach, for every test.
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("WORKBOT_DB_PATH", str(tmp_path / "unset.sqlite3"))
