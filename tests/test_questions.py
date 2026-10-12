import pytest

from workbot.llm import PROMPTS
from workbot.models import PersonProposal
from workbot.questions import NEUTRAL_QUESTIONS
from workbot.service import _grounded_ask, _safe_question


@pytest.mark.parametrize(
    ("role", "kind", "expected"),
    [
        ("routing_contact", "manager", "routing"),
        ("routing_contact", "remit", "routing"),
        ("routing_contact", "responsibility", "routing"),
        ("advisor", "responsibility", "responsibility"),
        ("direct_contact", "responsibility", "responsibility"),
        ("direct_contact", "assignee", "work"),
        ("advisor", "author", "work"),
        ("advisor", "contributor", "work"),
        ("advisor", "reporter", "record"),
        ("advisor", "manager", "record"),
        ("advisor", "mention", "record"),
    ],
)
def test_prompt_and_card_share_the_same_neutral_questions(role, kind, expected):
    question = _grounded_ask(role, kind)
    assert question == NEUTRAL_QUESTIONS[expected]
    assert PROMPTS["area"].count(f'"{question}"') == 1
    assert _safe_question(question)
    assert 5 <= len(question) <= 240


def test_question_registry_is_immutable():
    with pytest.raises(TypeError):
        NEUTRAL_QUESTIONS["record"] = "Which undocumented controls already exist?"


def test_reporter_template_does_not_attribute_personal_work_or_ownership():
    question = NEUTRAL_QUESTIONS["record"]
    assert "clarify about the cited record" in question
    assert "your work" not in question
    assert "owner" not in question


def test_ask_schema_is_not_a_template_enum_or_a_semantic_filter():
    schema = PersonProposal.model_json_schema()["properties"]["ask"]
    assert schema == {
        "type": "string",
        "title": "Ask",
        "minLength": 5,
        "maxLength": 240,
    }
    assert "copy EXACTLY ONE" in PROMPTS["area"]
    assert "including reporter" in PROMPTS["area"]
    assert "Do not turn contribution into a customized question" in PROMPTS["area"]
