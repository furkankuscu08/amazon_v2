"""Shared test setup. Being at the repository root also lets plain `pytest` import `tests` and `workbot`."""

import pytest


@pytest.fixture(autouse=True)
def offline_test_environment(tmp_path_factory, monkeypatch):
    # workbot.main loads .env on import, so real settings can be in the environment.
    # An empty key, unlike a removed one, also survives a later load_dotenv().
    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    # Empty provider settings mean the defaults: Bedrock and its default model.
    monkeypatch.setenv("WORKBOT_MODEL_PROVIDER", "")
    monkeypatch.setenv("WORKBOT_BEDROCK_MODEL", "")
    monkeypatch.setenv("QDRANT_URL", "http://127.0.0.1:9")
    monkeypatch.setenv(
        "WORKBOT_DB_PATH", str(tmp_path_factory.getbasetemp() / "unset.sqlite3")
    )
    # No AWS credentials can be found: no profile files, no keys or tokens, and no
    # instance or container metadata. A Bedrock call then fails as not_configured.
    missing = tmp_path_factory.getbasetemp() / "no-aws-config"
    monkeypatch.setenv("AWS_CONFIG_FILE", str(missing))
    monkeypatch.setenv("AWS_SHARED_CREDENTIALS_FILE", str(missing))
    monkeypatch.setenv("AWS_PROFILE", "workbot-offline-tests")
    monkeypatch.setenv("AWS_EC2_METADATA_DISABLED", "true")
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_WEB_IDENTITY_TOKEN_FILE",
    ):
        monkeypatch.setenv(name, "")
    # botocore uses these whenever they are set, even when empty: an empty Bedrock
    # bearer token still sends the request, and the container endpoint is called.
    for name in (
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_CONTAINER_CREDENTIALS_FULL_URI",
        "AWS_CONTAINER_CREDENTIALS_RELATIVE_URI",
    ):
        monkeypatch.delenv(name, raising=False)
