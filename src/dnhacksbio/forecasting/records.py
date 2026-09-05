"""Small JSON contracts; observed claims and candidate forecasts stay distinct."""
from typing import Any, NotRequired, TypedDict


class Node(TypedDict):
    id: str
    label: str
    type: str


class Evidence(TypedDict):
    id: str
    title: str
    text: str
    url: str
    available_at: str
    publication_year: int | None
    source_type: NotRequired[str]
    citation_id: NotRequired[str]
    content_sha256: NotRequired[str]
    contexts: NotRequired[list[dict[str, Any]]]


class Claim(TypedDict):
    id: str
    source: str
    target: str
    relation: str
    evidence_ids: list[str]
    contexts: list[dict[str, Any]]


class Candidate(TypedDict):
    id: str
    source: str
    target: str
    query_id: str


class Scenario(TypedDict):
    id: str
    title: str
    dataset: str
    cutoff: str
    horizon: str
    manifest: dict[str, Any]
    nodes: list[Node]
    claims: list[Claim]
    evidence: list[Evidence]
    candidates: list[Candidate]


class Outcome(TypedDict):
    candidate_id: str
    observed: bool
    evidence_ids: list[str]


class OutcomePacket(TypedDict):
    scenario_id: str
    horizon: str
    manifest: dict[str, Any]
    outcomes: list[Outcome]
    evidence: list[Evidence]
