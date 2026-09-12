from __future__ import annotations

from collections.abc import Iterator

from src.claim_extractor import ClaimExtractor
from src.evidence_matcher import EvidenceMatcher
from src.rules import VerificationRules
from src.schemas import (
    ClaimStatus,
    ClaimVerification,
    EvidenceItem,
    OverallVerdict,
    VerificationEvent,
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

    def _build_report(self, claim_results: list[ClaimVerification]) -> VerificationReport:
        """Aggregate verified claims into the deterministic final report."""
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

    def verify_iter(self, request: VerificationRequest) -> Iterator[VerificationEvent]:
        """Yield observable events from the real deterministic verification workflow."""
        yield VerificationEvent(
            event="verification_started",
            message=(
                f"Verification started with {len(request.evidence)} supplied evidence item"
                f"{'s' if len(request.evidence) != 1 else ''}."
            ),
        )

        claims = self.claim_extractor.extract(request.answer_text)
        if not claims:
            raise ValueError("No verifiable factual claims were found in the provided answer text.")

        yield VerificationEvent(
            event="claims_extracted",
            message=f"Extracted {len(claims)} factual claim{'s' if len(claims) != 1 else ''} for review.",
            claims=claims,
        )

        yield VerificationEvent(
            event="evidence_matching_started",
            message="Matching each claim against the supplied evidence using semantic and lexical relevance.",
            claims=claims,
        )

        matches_by_claim = self.evidence_matcher.match_claims(claims, request.evidence)
        claim_results: list[ClaimVerification] = []

        for claim in claims:
            matches = matches_by_claim.get(claim.claim_id, [])
            yield VerificationEvent(
                event="evidence_matched",
                message=(
                    f"Matched {len(matches)} evidence item{'s' if len(matches) != 1 else ''} "
                    f"to {claim.claim_id}."
                ),
                claim=claim,
                matches=matches,
            )

            result = self.rules.verify_claim(claim, request.evidence, matches)
            claim_results.append(result)

            yield VerificationEvent(
                event="claim_verified",
                message=(
                    f"{claim.claim_id} classified as {result.status.value.replace('_', ' ')}"
                    f"{' and flagged for human review' if result.human_review_required else ''}."
                ),
                claim=claim,
                matches=matches,
                claim_result=result,
            )

        report = self._build_report(claim_results)

        yield VerificationEvent(
            event="report_completed",
            message=(
                f"Verification complete: {report.verdict.value.upper()}"
                f"{' with human review required' if report.human_review_required else ''}."
            ),
            report=report,
        )

    def verify(self, request: VerificationRequest) -> VerificationReport:
        """Verify a full answer and return the final report from the observable workflow."""
        final_report: VerificationReport | None = None
        for event in self.verify_iter(request):
            if event.report is not None:
                final_report = event.report

        if final_report is None:
            raise RuntimeError("Verification completed without producing a report.")

        return final_report

    def verify_text(self, answer_text: str, evidence: list[EvidenceItem]) -> VerificationReport:
        """Construct a verification request from plain text and evidence and verify it."""
        request = VerificationRequest(answer_text=answer_text, evidence=evidence)
        return self.verify(request)
