from __future__ import annotations

import re
from typing import Any

from src.schemas import (
    Claim,
    ClaimStatus,
    ClaimVerification,
    EvidenceItem,
    EvidenceMatch,
    EvidenceStrength,
)


class VerificationRules:
    """Apply deterministic heuristics to turn evidence matches into claim verification results."""

    _negation_terms = {
        "not",
        "no",
        "never",
        "did not",
        "does not",
        "was not",
        "were not",
        "cannot",
        "failed to",
        "declined",
        "decreased",
    }

    def __init__(
        self,
        supported_threshold: float = 0.62,
        partial_threshold: float = 0.42,
        weak_threshold: float = 0.25,
        strong_reliability: float = 0.80,
        moderate_reliability: float = 0.60,
        semantic_relevance_threshold: float = 0.60,
        lexical_relevance_threshold: float = 0.25,
        citation_score_gap: float = 0.15,
    ) -> None:
        """Validate the rule thresholds and store normalized configuration."""
        if not 0.0 <= supported_threshold <= 1.0:
            raise ValueError("supported_threshold must be between 0.0 and 1.0")
        if not 0.0 <= partial_threshold <= 1.0:
            raise ValueError("partial_threshold must be between 0.0 and 1.0")
        if not 0.0 <= weak_threshold <= 1.0:
            raise ValueError("weak_threshold must be between 0.0 and 1.0")
        if not 0.0 <= strong_reliability <= 1.0:
            raise ValueError("strong_reliability must be between 0.0 and 1.0")
        if not 0.0 <= moderate_reliability <= 1.0:
            raise ValueError("moderate_reliability must be between 0.0 and 1.0")
        if not 0.0 <= semantic_relevance_threshold <= 1.0:
            raise ValueError("semantic_relevance_threshold must be between 0.0 and 1.0")
        if not 0.0 <= lexical_relevance_threshold <= 1.0:
            raise ValueError("lexical_relevance_threshold must be between 0.0 and 1.0")
        if not 0.0 <= citation_score_gap <= 1.0:
            raise ValueError("citation_score_gap must be between 0.0 and 1.0")
        if not (supported_threshold > partial_threshold > weak_threshold):
            raise ValueError("Thresholds must satisfy supported > partial > weak")

        self.supported_threshold = supported_threshold
        self.partial_threshold = partial_threshold
        self.weak_threshold = weak_threshold
        self.strong_reliability = strong_reliability
        self.moderate_reliability = moderate_reliability
        self.semantic_relevance_threshold = semantic_relevance_threshold
        self.lexical_relevance_threshold = lexical_relevance_threshold
        self.citation_score_gap = citation_score_gap

    def _extract_numeric_values(self, text: str) -> list[str]:
        """Extract and normalize numeric values from text into comparable strings."""
        if not text:
            return []

        normalized = text.replace(",", "")
        values = re.findall(r"\$?\d+(?:\.\d+)?%?", normalized)
        return [value for value in values if value]

    def _contains_negation(self, text: str) -> bool:
        """Return True when the text contains a common negation pattern."""
        lowered = text.lower()
        for term in self._negation_terms:
            if term in lowered:
                return True
        return False

    def _is_contradiction(self, claim_text: str, evidence_text: str) -> bool:
        """Return True for a conservative contradiction heuristic."""
        claim_terms = self._tokenize(claim_text)
        evidence_terms = self._tokenize(evidence_text)
        if not claim_terms or not evidence_terms:
            return False

        shared_terms = claim_terms & evidence_terms
        if not shared_terms:
            return False

        numeric_claim = self._extract_numeric_values(claim_text)
        numeric_evidence = self._extract_numeric_values(evidence_text)
        if numeric_claim and numeric_evidence and numeric_claim != numeric_evidence:
            return True

        negation_claim = self._contains_negation(claim_text)
        negation_evidence = self._contains_negation(evidence_text)
        if negation_claim != negation_evidence:
            return True

        return False

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into meaningful lowercase terms for heuristic checks."""
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        return {token for token in tokens if token not in {"the", "and", "of", "to", "in", "on", "for"}}

    def _evidence_strength(self, combined_score: float, reliability_score: float) -> EvidenceStrength:
        """Map score and reliability to a coarse evidence-strength label."""
        if combined_score >= self.supported_threshold and reliability_score >= self.strong_reliability:
            return EvidenceStrength.strong
        if combined_score >= self.partial_threshold and reliability_score >= self.moderate_reliability:
            return EvidenceStrength.moderate
        if combined_score >= self.weak_threshold:
            return EvidenceStrength.weak
        return EvidenceStrength.none

    def _is_relevant_match(self, match: EvidenceMatch) -> bool:
        """Return True when a match is relevant by semantic or lexical signal."""
        return match.similarity_score >= self.semantic_relevance_threshold or match.lexical_overlap >= self.lexical_relevance_threshold

    def verify_claim(
        self,
        claim: Claim,
        evidence: list[EvidenceItem],
        matches: list[EvidenceMatch],
    ) -> ClaimVerification:
        """Turn evidence matches into a deterministic claim verification result."""
        evidence_lookup = {item.evidence_id: item for item in evidence}
        usable_matches = [match for match in matches if match.evidence_id in evidence_lookup]

        if not usable_matches:
            return ClaimVerification(
                claim=claim,
                status=ClaimStatus.not_verifiable,
                evidence_strength=EvidenceStrength.none,
                matched_evidence=matches,
                rationale="No usable evidence matched the claim.",
                confidence=0.20,
                issues=[],
                human_review_required=True,
            )

        usable_matches = sorted(usable_matches, key=lambda match: (-match.combined_score, match.evidence_id))
        strongest = usable_matches[0]
        strongest_evidence = evidence_lookup[strongest.evidence_id]
        issues: list[str] = []
        human_review_required = False

        cited_ids = [cid for cid in claim.cited_evidence_ids if cid]
        missing_citations = [cid for cid in cited_ids if cid not in evidence_lookup]
        if missing_citations:
            issues.append(f"Missing cited evidence IDs: {', '.join(missing_citations)}")
            human_review_required = True

        cited_matches = [match for match in usable_matches if match.evidence_id in cited_ids]
        strongest_cited_match = max(cited_matches, key=lambda match: (match.combined_score, -len(match.evidence_id)), default=None)
        strongest_cited_evidence_id = strongest_cited_match.evidence_id if strongest_cited_match is not None else None
        if claim.cited_evidence_ids and not cited_matches:
            issues.append(f"Cited evidence {', '.join(cited_ids)} may not support the claim; strongest support is {strongest.evidence_id}.")
            human_review_required = True
        elif claim.cited_evidence_ids and strongest_cited_match is not None:
            if not self._is_relevant_match(strongest_cited_match):
                issues.append(
                    f"Cited evidence {strongest_cited_evidence_id} may not support the claim; strongest support is {strongest.evidence_id}."
                )
                human_review_required = True
            elif strongest.combined_score - strongest_cited_match.combined_score >= self.citation_score_gap and strongest.evidence_id not in cited_ids:
                issues.append(
                    f"Cited evidence {', '.join(cited_ids)} may not support the claim; strongest support is {strongest.evidence_id}."
                )
                human_review_required = True

        primary_evidence_item = strongest_evidence
        if self._is_contradiction(claim.text, primary_evidence_item.text):
            return ClaimVerification(
                claim=claim,
                status=ClaimStatus.contradicted,
                evidence_strength=self._evidence_strength(strongest.combined_score, primary_evidence_item.reliability_score),
                matched_evidence=matches,
                rationale=(
                    f"Contradiction detected with evidence {strongest.evidence_id} at combined score {strongest.combined_score:.2f} "
                    f"and reliability {primary_evidence_item.reliability_score:.2f}."
                ),
                confidence=0.20,
                issues=issues + ["Potential contradiction detected"],
                human_review_required=True,
            )

        if not self._is_relevant_match(strongest):
            return ClaimVerification(
                claim=claim,
                status=ClaimStatus.not_verifiable,
                evidence_strength=EvidenceStrength.none,
                matched_evidence=matches,
                rationale=(
                    f"Status not_verifiable with strongest evidence {strongest.evidence_id}. "
                    f"Combined score {strongest.combined_score:.2f} and reliability {strongest_evidence.reliability_score:.2f}."
                ),
                confidence=0.20,
                issues=issues,
                human_review_required=True,
            )

        status = ClaimStatus.not_verifiable
        if strongest.combined_score >= self.supported_threshold:
            status = ClaimStatus.supported
        elif strongest.combined_score >= self.partial_threshold:
            status = ClaimStatus.partially_supported
        elif strongest.combined_score >= self.weak_threshold:
            status = ClaimStatus.unsupported

        if status == ClaimStatus.supported and strongest_evidence.reliability_score < self.moderate_reliability:
            status = ClaimStatus.partially_supported

        if status == ClaimStatus.not_verifiable:
            human_review_required = True

        evidence_strength = self._evidence_strength(strongest.combined_score, strongest_evidence.reliability_score)

        confidence = 0.2 + (0.6 * strongest.combined_score) + (0.2 * strongest_evidence.reliability_score)
        confidence = min(1.0, max(0.0, confidence))
        if issues:
            confidence -= 0.10
        if claim.cited_evidence_ids and (not cited_matches or not self._is_relevant_match(strongest_cited_match) if strongest_cited_match is not None else True):
            confidence -= 0.10

        confidence = min(1.0, max(0.0, confidence))

        rationale_parts = [
            f"Status {status.value} with strongest evidence {strongest.evidence_id}.",
            f"Combined score {strongest.combined_score:.2f} and reliability {strongest_evidence.reliability_score:.2f}.",
        ]
        if issues:
            rationale_parts.append("Citation issue detected.")

        return ClaimVerification(
            claim=claim,
            status=status,
            evidence_strength=evidence_strength,
            matched_evidence=matches,
            rationale=" ".join(rationale_parts),
            confidence=confidence,
            issues=issues,
            human_review_required=human_review_required,
        )
