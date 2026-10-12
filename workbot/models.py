from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class SearchIntent(StrictModel):
    keyword: str = Field(min_length=2, max_length=180)
    semantic: str = Field(min_length=2, max_length=240)


class Area(StrictModel):
    id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,39}$")
    label: str = Field(min_length=2, max_length=100)
    rationale: str = Field(min_length=5, max_length=500)
    consultation_need: str = Field(min_length=5, max_length=300)
    search_intents: list[SearchIntent] = Field(min_length=1, max_length=3)
    mapping: Literal["mapped", "mapping_unresolved"]
    org_unit_id: str | None
    mapping_reason: str | None

    @model_validator(mode="after")
    def mapping_consistent(self) -> Area:
        if self.mapping == "mapped" and (
            not self.org_unit_id or self.mapping_reason is not None
        ):
            raise ValueError("mapped requires only an org_unit_id")
        if self.mapping == "mapping_unresolved" and (
            self.org_unit_id is not None or not self.mapping_reason
        ):
            raise ValueError("mapping_unresolved requires only a reason")
        return self


class Impact(StrictModel):
    question: str | None
    areas: list[Area] = Field(max_length=6)

    @model_validator(mode="after")
    def question_or_areas(self) -> Impact:
        if self.question:
            if len(self.question) > 240 or self.areas:
                raise ValueError("A question must precede the final area list")
        elif not self.areas or len({area.id for area in self.areas}) != len(self.areas):
            raise ValueError("Final output needs unique areas")
        return self


class PersonProposal(StrictModel):
    person_id: str
    # The single source the model relies on for this role, and its own read of how
    # closely that source matches the area's consultation need. Local validation
    # checks that the primary is cited; the direct-contact evidence requirement is
    # enforced in the deterministic audit, not this schema, so an inconsistent
    # role/link does not void a whole area review.
    primary_evidence_id: str
    # Unverified source-to-need summary, not an independent semantic audit. The
    # schema cap is well above the prompt's requested length so a provider that
    # enforces it does not cut a sentence short.
    contribution: str = Field(min_length=5, max_length=600)
    role: Literal["direct_contact", "advisor", "routing_contact"]
    relevance: Literal["direct", "adjacent", "weak"]
    evidence_ids: list[str] = Field(min_length=1, max_length=8)
    confidence: Literal["high", "medium", "low"]

    @model_validator(mode="after")
    def primary_is_cited(self) -> PersonProposal:
        if self.primary_evidence_id not in self.evidence_ids:
            raise ValueError("primary_evidence_id must be one of evidence_ids")
        return self


class AreaEvaluation(StrictModel):
    people: list[PersonProposal] = Field(max_length=22)

    @model_validator(mode="after")
    def unique_people(self) -> AreaEvaluation:
        if len({person.person_id for person in self.people}) != len(self.people):
            raise ValueError("Each person can occur only once per area")
        return self


class Priority(StrictModel):
    order: list[str]
    shared_question: str | None
    # Person IDs already on the audited card, most important first. The service
    # keeps only IDs that are shown; this can neither add a person nor change a role.
    first_conversations: list[str] = Field(max_length=4)
