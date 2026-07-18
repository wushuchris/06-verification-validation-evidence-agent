from __future__ import annotations

from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class ClaimStatus(StrEnum):
    """Status of a claim after verification."""

    supported = "supported"
    partially_supported = "partially_supported"
    unsupported = "unsupported"
    contradicted = "contradicted"
    not_verifiable = "not_verifiable"


class EvidenceStrength(StrEnum):
    """Strength of the evidence backing a claim."""

    strong = "strong"
    moderate = "moderate"
    weak = "weak"
    none = "none"


class OverallVerdict(StrEnum):
    """Overall outcome of a verification report."""

    pass_ = "pass"
    review = "review"
    fail = "fail"


class EvidenceItem(BaseModel):
    """A single piece of evidence used to verify a claim."""

    evidence_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    source: Optional[str] = None
    source_type: str = Field(default="unknown", min_length=1)
    reliability_score: float = Field(default=0.5, ge=0.0, le=1.0)


class Claim(BaseModel):
    """A claim to be evaluated against evidence."""

    claim_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1)
    cited_evidence_ids: list[str] = Field(default_factory=list)


class EvidenceMatch(BaseModel):
    """A similarity match between a claim and evidence."""

    evidence_id: str = Field(..., min_length=1)
    similarity_score: float = Field(..., ge=0.0, le=1.0)
    lexical_overlap: float = Field(..., ge=0.0, le=1.0)
    combined_score: float = Field(..., ge=0.0, le=1.0)


class ClaimVerification(BaseModel):
    """Verification result for a single claim."""

    claim: Claim
    status: ClaimStatus
    evidence_strength: EvidenceStrength
    matched_evidence: list[EvidenceMatch] = Field(default_factory=list)
    rationale: str = Field(..., min_length=1)
    confidence: float = Field(..., ge=0.0, le=1.0)
    issues: list[str] = Field(default_factory=list)
    human_review_required: bool = False


class VerificationRequest(BaseModel):
    """Input payload for a verification workflow."""

    answer_text: str = Field(..., min_length=1)
    evidence: list[EvidenceItem] = Field(..., min_length=1)


class VerificationReport(BaseModel):
    """Aggregated report for a full verification run."""

    verdict: OverallVerdict
    claim_results: list[ClaimVerification] = Field(..., min_length=1)
    total_claims: int = Field(..., ge=0)
    supported_claims: int = Field(..., ge=0)
    partially_supported_claims: int = Field(..., ge=0)
    unsupported_claims: int = Field(..., ge=0)
    contradicted_claims: int = Field(..., ge=0)
    not_verifiable_claims: int = Field(..., ge=0)
    overall_confidence: float = Field(..., ge=0.0, le=1.0)
    human_review_required: bool
    summary: str = Field(..., min_length=1)
