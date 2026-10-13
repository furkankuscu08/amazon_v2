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
def test_card_question_follows_the_verified_role_and_primary_kind(role, kind, expected):
    question = _grounded_ask(role, kind)
    assert question == NEUTRAL_QUESTIONS[expected]
    assert _safe_question(question)
    assert 5 <= len(question) <= 240


def test_reporter_template_does_not_attribute_personal_work_or_ownership():
    question = NEUTRAL_QUESTIONS["record"]
    assert "clarify about the cited record" in question
    assert "your work" not in question
    assert "owner" not in question


def test_model_is_not_asked_to_write_questions_for_people():
    assert not {"ask", "unverified"} & set(PersonProposal.model_fields)
    prompt = " ".join(PROMPTS["area"].split())
    assert "Do not draft questions or messages for the person" in prompt
    assert not any(question in prompt for question in NEUTRAL_QUESTIONS.values())
