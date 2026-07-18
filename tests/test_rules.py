from __future__ import annotations

from src.rules import VerificationRules
from src.schemas import (
    Claim,
    ClaimStatus,
    EvidenceItem,
    EvidenceMatch,
    EvidenceStrength,
)


def _make_claim(text: str, cited_evidence_ids: list[str] | None = None) -> Claim:
    return Claim(
        claim_id="C1",
        text=text,
        cited_evidence_ids=cited_evidence_ids or [],
    )


def _make_evidence(evidence_id: str = "E1", text: str = "Evidence text.") -> EvidenceItem:
    return EvidenceItem(evidence_id=evidence_id, text=text, source="Test source", reliability_score=0.95)


def _make_match(
    evidence_id: str = "E1",
    combined_score: float = 0.80,
    similarity_score: float = 0.90,
    lexical_overlap: float = 0.80,
) -> EvidenceMatch:
    return EvidenceMatch(
        evidence_id=evidence_id,
        similarity_score=similarity_score,
        lexical_overlap=lexical_overlap,
        combined_score=combined_score,
    )


def test_strong_match_with_reliable_evidence_is_supported() -> None:
    rules = VerificationRules()
    claim = _make_claim("The project launched on June 15.")
    evidence = [_make_evidence(text="The project officially launched on June 15.")]
    result = rules.verify_claim(claim, evidence, [_make_match(combined_score=0.80)])

    assert result.status == ClaimStatus.supported
    assert result.evidence_strength == EvidenceStrength.strong
    assert result.human_review_required is False


def test_numeric_disagreement_is_marked_contradicted() -> None:
    rules = VerificationRules()
    claim = _make_claim("Revenue increased by 12%.")
    evidence = [_make_evidence(text="Revenue increased by 8%.")]
    result = rules.verify_claim(claim, evidence, [_make_match(combined_score=0.80)])

    assert result.status == ClaimStatus.contradicted
    assert result.human_review_required is True
    assert any("contradict" in issue.lower() or "contradiction" in issue.lower() for issue in result.issues)


def test_missing_cited_evidence_records_issue_and_requests_review() -> None:
    rules = VerificationRules()
    claim = _make_claim("The project launched on June 15.", cited_evidence_ids=["MISSING"])
    evidence = [_make_evidence(text="The project launched on June 15.")]
    result = rules.verify_claim(claim, evidence, [_make_match(combined_score=0.80)])

    assert any("MISSING" in issue for issue in result.issues)
    assert result.human_review_required is True


def test_low_score_match_is_not_verifiable() -> None:
    rules = VerificationRules()
    claim = _make_claim("The project launched on June 15.")
    evidence = [_make_evidence(text="The project launched on June 15.")]
    result = rules.verify_claim(claim, evidence, [_make_match(combined_score=0.10)])

    assert result.status == ClaimStatus.not_verifiable
    assert result.evidence_strength == EvidenceStrength.none
    assert result.human_review_required is True


def test_reliable_partial_score_is_partially_supported() -> None:
    rules = VerificationRules()
    claim = _make_claim("The project launched on June 15.")
    evidence = [_make_evidence(text="The project launched on June 15.")]
    result = rules.verify_claim(claim, evidence, [_make_match(combined_score=0.50)])

    assert result.status == ClaimStatus.partially_supported


def test_primary_support_outweighs_lower_ranked_contradiction() -> None:
    rules = VerificationRules()
    claim = _make_claim("The project launched on June 15.")
    evidence = [
        _make_evidence("E1", "The project officially launched on June 15."),
        _make_evidence("E2", "The project launched on 16."),
    ]
    matches = [
        _make_match("E2", combined_score=0.70, similarity_score=0.90, lexical_overlap=0.80),
        _make_match("E1", combined_score=0.80, similarity_score=0.95, lexical_overlap=0.90),
    ]

    result = rules.verify_claim(claim, evidence, matches)

    assert result.status == ClaimStatus.supported
    assert result.human_review_required is False


def test_citation_mismatch_is_reported_for_unrelated_cited_evidence() -> None:
    rules = VerificationRules()
    claim = _make_claim("The project launched on June 15.", cited_evidence_ids=["E2"])
    evidence = [
        _make_evidence("E1", "The project officially launched on June 15."),
        _make_evidence("E2", "An unrelated equipment inventory update."),
    ]
    matches = [
        _make_match("E1", combined_score=0.80, similarity_score=0.95, lexical_overlap=0.90),
        _make_match("E2", combined_score=0.20, similarity_score=0.20, lexical_overlap=0.10),
    ]

    result = rules.verify_claim(claim, evidence, matches)

    assert result.status == ClaimStatus.supported
    assert result.human_review_required is True
    assert any("E2" in issue and "E1" in issue for issue in result.issues)


def test_relevance_gate_classifies_weak_match_as_not_verifiable() -> None:
    rules = VerificationRules()
    claim = _make_claim("The project launched on June 15.")
    evidence = [_make_evidence("E1", "The project launched on June 15.")]
    result = rules.verify_claim(
        claim,
        evidence,
        [_make_match("E1", combined_score=0.4294, similarity_score=0.5059, lexical_overlap=0.20)],
    )

    assert result.status == ClaimStatus.not_verifiable
    assert result.evidence_strength == EvidenceStrength.none
    assert result.human_review_required is True


def test_numeric_contradiction_is_detected_with_primary_evidence() -> None:
    rules = VerificationRules()
    claim = _make_claim("Revenue increased by 12%.")
    evidence = [_make_evidence("E1", "Revenue increased by 8%.")]
    result = rules.verify_claim(claim, evidence, [_make_match("E1", combined_score=0.80, similarity_score=0.95, lexical_overlap=0.90)])

    assert result.status == ClaimStatus.contradicted
    assert result.human_review_required is True
