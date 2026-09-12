from __future__ import annotations

import app
from src.demo_presentation import APP_CSS, EVIDENCE_BOUNDARY_HTML, HERO_HTML
from src.schemas import (
    Claim,
    ClaimStatus,
    ClaimVerification,
    EvidenceMatch,
    EvidenceStrength,
    OverallVerdict,
    VerificationEvent,
    VerificationReport,
)


def _report() -> VerificationReport:
    claim = Claim(
        claim_id="C1",
        text="The Aurora pilot launched on June 15.",
        cited_evidence_ids=["E1"],
    )
    match = EvidenceMatch(
        evidence_id="E1",
        similarity_score=0.95,
        lexical_overlap=0.90,
        combined_score=0.80,
    )
    result = ClaimVerification(
        claim=claim,
        status=ClaimStatus.supported,
        evidence_strength=EvidenceStrength.strong,
        matched_evidence=[match],
        rationale="Status supported with strongest evidence E1.",
        confidence=0.95,
        issues=[],
        human_review_required=False,
    )
    return VerificationReport(
        verdict=OverallVerdict.pass_,
        claim_results=[result],
        total_claims=1,
        supported_claims=1,
        partially_supported_claims=0,
        unsupported_claims=0,
        contradicted_claims=0,
        not_verifiable_claims=0,
        overall_confidence=0.95,
        human_review_required=False,
        summary="Verdict: pass.",
    )


class StubAgent:
    def verify_iter(self, request):
        claim = _report().claim_results[0].claim
        result = _report().claim_results[0]
        report = _report()
        yield VerificationEvent(
            event="verification_started",
            message="Verification started with 1 supplied evidence item.",
        )
        yield VerificationEvent(
            event="claims_extracted",
            message="Extracted 1 factual claim for review.",
            claims=[claim],
        )
        yield VerificationEvent(
            event="claim_verified",
            message="C1 classified as supported.",
            claim=claim,
            claim_result=result,
        )
        yield VerificationEvent(
            event="report_completed",
            message="Verification complete: PASS.",
            report=report,
        )


def test_business_layout_is_centered_and_explains_evidence_boundary() -> None:
    assert "max-width: 1080px" in APP_CSS
    assert "Can this AI-generated answer clear an evidence review" in HERO_HTML
    assert "does not conclude" in EVIDENCE_BOUNDARY_HTML
    assert "independently true" in EVIDENCE_BOUNDARY_HTML


def test_stream_verification_yields_real_progress_before_final_verdict(monkeypatch) -> None:
    monkeypatch.setattr(app, "agent", StubAgent())
    monkeypatch.setattr(app, "create_audit_package", lambda report: "audit.zip")

    evidence_json = """[
      {
        "evidence_id": "E1",
        "text": "The Aurora pilot launched on June 15.",
        "source": "Synthetic report",
        "source_type": "report",
        "reliability_score": 0.95
      }
    ]"""

    frames = list(
        app.stream_verification(
            "The Aurora pilot launched on June 15 [E1].",
            evidence_json,
        )
    )

    assert len(frames) >= 5
    assert all(len(frame) == 7 for frame in frames)
    assert "RUNNING" in frames[0][0]
    assert "Review started" in frames[1][0]
    assert "Claim classified" in frames[-2][0]
    assert "COMPLETE" in frames[-1][0]
    assert "PASS" in frames[-1][1]
    assert "Evidence-aligned within the supplied record" in frames[-1][1]
    assert "C1" in frames[-1][2]
