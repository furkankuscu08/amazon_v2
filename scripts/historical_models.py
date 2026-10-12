"""Explicit offline normalization of a field absent from historical captures."""

from workbot.models import AreaEvaluation

CONTRIBUTION_UNOBSERVED = "Historical capture: contribution was not observed or scored."


def historical_evaluation(people: list[dict]) -> AreaEvaluation:
    """Adapt copies for audit-only replay; never repair a live model response.

    The audit does not read contribution. This sentinel is not a generated
    explanation and must not be scored, shown on cards, or passed to priority.
    Explicit captured values, including invalid ones, are never replaced.
    """
    adapted = []
    for person in people:
        copy = dict(person)
        copy.setdefault("contribution", CONTRIBUTION_UNOBSERVED)
        adapted.append(copy)
    return AreaEvaluation.model_validate({"people": adapted})
