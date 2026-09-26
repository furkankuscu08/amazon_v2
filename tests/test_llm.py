import json

import httpx
import pytest

from workbot.llm import ModelError, OpenRouter
from workbot.models import Impact


def test_openrouter_sends_reasoning_and_schema_and_validates_locally(monkeypatch):
    requests = []

    def handle(request):
        body = json.loads(request.content)
        requests.append(body)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "content": json.dumps(
                                {"question": "What type of campaign?", "areas": []}
                            )
                        },
                    }
                ]
            },
        )

    client_class = httpx.Client
    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handle)),
    )
    result = OpenRouter("test-only-key").complete(
        "impact", {"idea": "A campaign", "org_units": []}
    )
    assert isinstance(result, Impact)
    assert requests[0]["model"] == "z-ai/glm-5.3-flash"
    assert requests[0]["reasoning"] == {"effort": "high"}
    assert requests[0]["response_format"]["type"] == "json_schema"
    assert requests[0]["response_format"]["json_schema"]["strict"] is True


def test_truncated_openrouter_response_is_not_parsed_as_partial_card(monkeypatch):
    client_class = httpx.Client

    def handle(request):
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "finish_reason": "length",
                        "message": {"content": '{"question":null,"areas":[]}'},
                    }
                ]
            },
        )

    monkeypatch.setattr(
        httpx,
        "Client",
        lambda **kwargs: client_class(transport=httpx.MockTransport(handle)),
    )
    with pytest.raises(ModelError, match="incomplete"):
        OpenRouter("test-only-key").complete("impact", {"idea": "A campaign"})
