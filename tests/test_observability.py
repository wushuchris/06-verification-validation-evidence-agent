from __future__ import annotations

from src.schemas import Claim, EvidenceItem, EvidenceMatch, OverallVerdict, VerificationRequest
from src.verifier import VerificationAgent


class StubClaimExtractor:
    def extract(self, answer_text: str) -> list[Claim]:
        return [
            Claim(
                claim_id="C1",
                text="Quarterly revenue increased by 12%.",
                cited_evidence_ids=["E1"],
            )
        ]


class StubEvidenceMatcher:
    def match_claims(self, claims: list[Claim], evidence: list[EvidenceItem]) -> dict[str, list[EvidenceMatch]]:
        return {
            "C1": [
                EvidenceMatch(
                    evidence_id="E1",
                    similarity_score=0.95,
                    lexical_overlap=0.90,
                    combined_score=0.80,
                )
            ]
        }


def _request() -> VerificationRequest:
    return VerificationRequest(
        answer_text="Quarterly revenue increased by 12% [E1].",
        evidence=[
            EvidenceItem(
                evidence_id="E1",
                text="Quarterly revenue increased by 12%.",
                source="Synthetic finance memo",
                source_type="memo",
                reliability_score=0.96,
            )
        ],
    )


def test_verify_iter_emits_real_verification_stages() -> None:
    agent = VerificationAgent(
        claim_extractor=StubClaimExtractor(),
        evidence_matcher=StubEvidenceMatcher(),
    )

    events = list(agent.verify_iter(_request()))

    assert [event.event for event in events] == [
        "verification_started",
        "claims_extracted",
        "evidence_matching_started",
        "evidence_matched",
        "claim_verified",
        "report_completed",
    ]
    assert events[1].claims[0].claim_id == "C1"
    assert events[3].matches[0].evidence_id == "E1"
    assert events[4].claim_result is not None
    assert events[4].claim_result.status.value == "supported"
    assert events[-1].report is not None
    assert events[-1].report.verdict == OverallVerdict.pass_


def test_verify_returns_the_same_final_report_as_verify_iter() -> None:
    agent = VerificationAgent(
        claim_extractor=StubClaimExtractor(),
        evidence_matcher=StubEvidenceMatcher(),
    )

    events = list(agent.verify_iter(_request()))
    streamed_report = events[-1].report
    direct_report = agent.verify(_request())

    assert streamed_report is not None
    assert direct_report == streamed_report
