from __future__ import annotations

from src.claim_extractor import ClaimExtractor
from src.evidence_matcher import EvidenceMatcher
from src.rules import VerificationRules
from src.schemas import (
    ClaimStatus,
    EvidenceItem,
    OverallVerdict,
    VerificationReport,
    VerificationRequest,
)


class VerificationAgent:
    """Coordinate claim extraction, evidence matching, and rule-based verification."""

    def __init__(
        self,
        claim_extractor: ClaimExtractor | None = None,
        evidence_matcher: EvidenceMatcher | None = None,
        rules: VerificationRules | None = None,
    ) -> None:
        """Store the supplied components or create their default implementations."""
        self.claim_extractor = claim_extractor if claim_extractor is not None else ClaimExtractor()
        self.evidence_matcher = evidence_matcher if evidence_matcher is not None else EvidenceMatcher()
        self.rules = rules if rules is not None else VerificationRules()

    def verify(self, request: VerificationRequest) -> VerificationReport:
        """Verify a full answer against the provided evidence and return an aggregated report."""
        claims = self.claim_extractor.extract(request.answer_text)
        if not claims:
            raise ValueError("No verifiable factual claims were found in the provided answer text.")

        matches_by_claim = self.evidence_matcher.match_claims(claims, request.evidence)
        claim_results = []
        for claim in claims:
            matches = matches_by_claim.get(claim.claim_id, [])
            claim_results.append(self.rules.verify_claim(claim, request.evidence, matches))

        status_counts = {status: 0 for status in ClaimStatus}
        for result in claim_results:
            status_counts[result.status] += 1

        if claim_results:
            overall_confidence = sum(result.confidence for result in claim_results) / len(claim_results)
            overall_confidence = round(overall_confidence, 4)
        else:
            overall_confidence = 0.0
        overall_confidence = min(1.0, max(0.0, overall_confidence))

        human_review_required = any(result.human_review_required for result in claim_results)

        if any(result.status == ClaimStatus.contradicted for result in claim_results) or any(
            result.status == ClaimStatus.unsupported for result in claim_results
        ):
            verdict = OverallVerdict.fail
        elif (
            any(result.status == ClaimStatus.partially_supported for result in claim_results)
            or any(result.status == ClaimStatus.not_verifiable for result in claim_results)
            or human_review_required
        ):
            verdict = OverallVerdict.review
        else:
            verdict = OverallVerdict.pass_

        summary = (
            f"Verdict: {verdict.value}. "
            f"Claims: {len(claim_results)}. "
            f"Supported: {status_counts[ClaimStatus.supported]}, "
            f"Partially supported: {status_counts[ClaimStatus.partially_supported]}, "
            f"Unsupported: {status_counts[ClaimStatus.unsupported]}, "
            f"Contradicted: {status_counts[ClaimStatus.contradicted]}, "
            f"Not verifiable: {status_counts[ClaimStatus.not_verifiable]}. "
            f"Human review required: {str(human_review_required).lower()}."
        )

        return VerificationReport(
            verdict=verdict,
            claim_results=claim_results,
            total_claims=len(claim_results),
            supported_claims=status_counts[ClaimStatus.supported],
            partially_supported_claims=status_counts[ClaimStatus.partially_supported],
            unsupported_claims=status_counts[ClaimStatus.unsupported],
            contradicted_claims=status_counts[ClaimStatus.contradicted],
            not_verifiable_claims=status_counts[ClaimStatus.not_verifiable],
            overall_confidence=overall_confidence,
            human_review_required=human_review_required,
            summary=summary,
        )

    def verify_text(self, answer_text: str, evidence: list[EvidenceItem]) -> VerificationReport:
        """Construct a verification request from plain text and evidence and verify it."""
        request = VerificationRequest(answer_text=answer_text, evidence=evidence)
        return self.verify(request)
