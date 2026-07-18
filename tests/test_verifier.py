from __future__ import annotations

import pytest

from src.schemas import (
    Claim,
    ClaimStatus,
    EvidenceItem,
    EvidenceMatch,
    OverallVerdict,
    VerificationRequest,
)
from src.verifier import VerificationAgent


class StubClaimExtractor:
    def __init__(self, claims: list[Claim]) -> None:
        self._claims = claims

    def extract(self, answer_text: str) -> list[Claim]:
        return list(self._claims)


class StubEvidenceMatcher:
    def __init__(self, matches_by_claim_id: dict[str, list[EvidenceMatch]]) -> None:
        self._matches_by_claim_id = matches_by_claim_id

    def match_claims(self, claims: list[Claim], evidence: list[EvidenceItem]) -> dict[str, list[EvidenceMatch]]:
        return dict(self._matches_by_claim_id)


def _make_request(answer_text: str, evidence: list[EvidenceItem] | None = None) -> VerificationRequest:
    return VerificationRequest(
        answer_text=answer_text,
        evidence=evidence or [EvidenceItem(evidence_id="E1", text="Evidence text.", source="Test source")],
    )


def test_verification_agent_returns_pass_when_all_claims_are_supported() -> None:
    claims = [
        Claim(claim_id="C1", text="The project launched on June 15.", cited_evidence_ids=["E1"]),
        Claim(claim_id="C2", text="Revenue increased by 12%.", cited_evidence_ids=["E2"]),
    ]
    evidence = [
        EvidenceItem(evidence_id="E1", text="The project launched on June 15.", source="Launch report", reliability_score=0.95),
        EvidenceItem(evidence_id="E2", text="Revenue increased by 12%.", source="Finance report", reliability_score=0.92),
    ]
    matches = {
        "C1": [EvidenceMatch(evidence_id="E1", similarity_score=0.95, lexical_overlap=0.90, combined_score=0.80)],
        "C2": [EvidenceMatch(evidence_id="E2", similarity_score=0.95, lexical_overlap=0.90, combined_score=0.80)],
    }
    agent = VerificationAgent(
        claim_extractor=StubClaimExtractor(claims),
        evidence_matcher=StubEvidenceMatcher(matches),
    )

    report = agent.verify(_make_request("Two claims.", evidence))

    assert report.verdict == OverallVerdict("pass")
    assert report.human_review_required is False
    assert report.total_claims == 2
    assert report.supported_claims == 2


def test_verification_agent_returns_fail_when_a_claim_is_contradicted() -> None:
    claims = [Claim(claim_id="C1", text="Revenue increased by 12%.", cited_evidence_ids=["E1"])]
    evidence = [EvidenceItem(evidence_id="E1", text="Revenue increased by 8%.", source="Finance report", reliability_score=0.92)]
    matches = {
        "C1": [EvidenceMatch(evidence_id="E1", similarity_score=0.95, lexical_overlap=0.90, combined_score=0.80)],
    }
    agent = VerificationAgent(
        claim_extractor=StubClaimExtractor(claims),
        evidence_matcher=StubEvidenceMatcher(matches),
    )

    report = agent.verify(_make_request("Contradiction claim.", evidence))

    assert report.verdict == OverallVerdict("fail")
    assert report.human_review_required is True
    assert any(result.status == ClaimStatus.contradicted for result in report.claim_results)


def test_verification_agent_returns_fail_when_a_claim_is_unsupported() -> None:
    claims = [Claim(claim_id="C1", text="The project launched on June 15.", cited_evidence_ids=["E1"])]
    evidence = [EvidenceItem(evidence_id="E1", text="A different project launched on June 15.", source="Launch report", reliability_score=0.92)]
    matches = {
        "C1": [EvidenceMatch(evidence_id="E1", similarity_score=0.80, lexical_overlap=0.30, combined_score=0.30)],
    }
    agent = VerificationAgent(
        claim_extractor=StubClaimExtractor(claims),
        evidence_matcher=StubEvidenceMatcher(matches),
    )

    report = agent.verify(_make_request("Unsupported claim.", evidence))

    assert report.verdict == OverallVerdict("fail")
    assert any(result.status == ClaimStatus.unsupported for result in report.claim_results)


def test_verification_agent_returns_review_for_partial_support() -> None:
    claims = [
        Claim(claim_id="C1", text="The project launched on June 15.", cited_evidence_ids=["E1"]),
        Claim(claim_id="C2", text="Revenue increased by 12%.", cited_evidence_ids=["E2"]),
    ]
    evidence = [
        EvidenceItem(evidence_id="E1", text="The project launched on June 15.", source="Launch report", reliability_score=0.95),
        EvidenceItem(evidence_id="E2", text="Revenue increased by 12%.", source="Finance report", reliability_score=0.92),
    ]
    matches = {
        "C1": [EvidenceMatch(evidence_id="E1", similarity_score=0.95, lexical_overlap=0.90, combined_score=0.80)],
        "C2": [EvidenceMatch(evidence_id="E2", similarity_score=0.60, lexical_overlap=0.60, combined_score=0.50)],
    }
    agent = VerificationAgent(
        claim_extractor=StubClaimExtractor(claims),
        evidence_matcher=StubEvidenceMatcher(matches),
    )

    report = agent.verify(_make_request("Mixed claims.", evidence))

    assert report.verdict == OverallVerdict("review")
    assert any(result.status == ClaimStatus.partially_supported for result in report.claim_results)


def test_verification_agent_returns_review_for_citation_mismatch() -> None:
    claims = [Claim(claim_id="C1", text="The project launched on June 15.", cited_evidence_ids=["E2"])]
    evidence = [
        EvidenceItem(evidence_id="E1", text="The project launched on June 15.", source="Launch report", reliability_score=0.95),
        EvidenceItem(evidence_id="E2", text="Unrelated equipment inventory update.", source="Inventory log", reliability_score=0.90),
    ]
    matches = {
        "C1": [
            EvidenceMatch(evidence_id="E1", similarity_score=0.95, lexical_overlap=0.90, combined_score=0.80),
            EvidenceMatch(evidence_id="E2", similarity_score=0.20, lexical_overlap=0.10, combined_score=0.20),
        ],
    }
    agent = VerificationAgent(
        claim_extractor=StubClaimExtractor(claims),
        evidence_matcher=StubEvidenceMatcher(matches),
    )

    report = agent.verify(_make_request("Citation mismatch.", evidence))

    assert report.verdict == OverallVerdict("review")
    assert report.claim_results[0].status == ClaimStatus.supported
    assert report.human_review_required is True


def test_verification_agent_raises_when_no_claims_are_extracted() -> None:
    agent = VerificationAgent(
        claim_extractor=StubClaimExtractor([]),
        evidence_matcher=StubEvidenceMatcher({}),
    )

    with pytest.raises(ValueError, match="No verifiable factual claims were found"):
        agent.verify(_make_request("No claims here."))


def test_verification_agent_summary_counts_match_claim_results() -> None:
    claims = [
        Claim(claim_id="C1", text="Supported claim.", cited_evidence_ids=["E1"]),
        Claim(claim_id="C2", text="Partially supported claim.", cited_evidence_ids=["E2"]),
        Claim(claim_id="C3", text="Unsupported claim.", cited_evidence_ids=["E3"]),
    ]
    evidence = [
        EvidenceItem(evidence_id="E1", text="Supported evidence.", source="Source 1", reliability_score=0.95),
        EvidenceItem(evidence_id="E2", text="Partial evidence.", source="Source 2", reliability_score=0.90),
        EvidenceItem(evidence_id="E3", text="Unsupported evidence.", source="Source 3", reliability_score=0.90),
    ]
    matches = {
        "C1": [EvidenceMatch(evidence_id="E1", similarity_score=0.95, lexical_overlap=0.90, combined_score=0.80)],
        "C2": [EvidenceMatch(evidence_id="E2", similarity_score=0.60, lexical_overlap=0.60, combined_score=0.50)],
        "C3": [EvidenceMatch(evidence_id="E3", similarity_score=0.35, lexical_overlap=0.25, combined_score=0.30)],
    }
    agent = VerificationAgent(
        claim_extractor=StubClaimExtractor(claims),
        evidence_matcher=StubEvidenceMatcher(matches),
    )

    report = agent.verify(_make_request("Summary counts.", evidence))

    assert report.total_claims == 3
    assert report.supported_claims == 1
    assert report.partially_supported_claims == 1
    assert report.unsupported_claims == 1
    assert report.contradicted_claims == 0
    assert report.not_verifiable_claims == 0
    assert len(report.claim_results) == report.total_claims
