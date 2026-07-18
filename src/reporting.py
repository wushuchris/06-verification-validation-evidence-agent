from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from src.schemas import VerificationReport


class ReportFormatter:
    """Format verification reports as Markdown, JSON, and CSV artifacts."""

    def summary_markdown(self, report: VerificationReport) -> str:
        """Return a concise summary of the verification report as Markdown."""
        confidence_percent = report.overall_confidence * 100.0
        return "\n".join(
            [
                "# Verification Report",
                "",
                f"- **Overall verdict:** {report.verdict.value}",
                f"- **Overall confidence:** {confidence_percent:.2f}%",
                f"- **Human review required:** {'Yes' if report.human_review_required else 'No'}",
                f"- **Total claims:** {report.total_claims}",
                f"- **Supported:** {report.supported_claims}",
                f"- **Partially supported:** {report.partially_supported_claims}",
                f"- **Unsupported:** {report.unsupported_claims}",
                f"- **Contradicted:** {report.contradicted_claims}",
                f"- **Not verifiable:** {report.not_verifiable_claims}",
                "",
                f"**Summary:** {report.summary}",
            ]
        )

    def claim_rows(self, report: VerificationReport) -> list[dict[str, object]]:
        """Return a flat row dictionary for each claim result."""
        rows: list[dict[str, object]] = []
        for claim_result in report.claim_results:
            strongest_match_score = 0.0
            if claim_result.matched_evidence:
                strongest_match_score = max(match.combined_score for match in claim_result.matched_evidence)

            rows.append(
                {
                    "claim_id": claim_result.claim.claim_id,
                    "claim_text": claim_result.claim.text,
                    "status": claim_result.status.value,
                    "evidence_strength": claim_result.evidence_strength.value,
                    "confidence": round(claim_result.confidence, 4),
                    "human_review_required": claim_result.human_review_required,
                    "cited_evidence_ids": ", ".join(claim_result.claim.cited_evidence_ids),
                    "matched_evidence_ids": ", ".join(match.evidence_id for match in claim_result.matched_evidence),
                    "strongest_match_score": round(strongest_match_score, 4),
                    "issues": "; ".join(claim_result.issues),
                    "rationale": claim_result.rationale,
                }
            )
        return rows

    def claims_dataframe(self, report: VerificationReport) -> pd.DataFrame:
        """Create a DataFrame from the claim rows while preserving the requested column order."""
        columns = [
            "claim_id",
            "claim_text",
            "status",
            "evidence_strength",
            "confidence",
            "human_review_required",
            "cited_evidence_ids",
            "matched_evidence_ids",
            "strongest_match_score",
            "issues",
            "rationale",
        ]
        return pd.DataFrame(self.claim_rows(report), columns=columns)

    def full_markdown(self, report: VerificationReport) -> str:
        """Return the summary plus a detailed breakdown for each claim."""
        sections = [self.summary_markdown(report), "", "## Claim Results", ""]
        for index, claim_result in enumerate(report.claim_results, start=1):
            sections.extend(
                [
                    f"### Claim {index}: {claim_result.claim.claim_id}",
                    "",
                    f"- **Claim text:** {claim_result.claim.text}",
                    f"- **Status:** {claim_result.status.value}",
                    f"- **Evidence strength:** {claim_result.evidence_strength.value}",
                    f"- **Confidence:** {claim_result.confidence:.4f}",
                    f"- **Cited evidence IDs:** {', '.join(claim_result.claim.cited_evidence_ids) if claim_result.claim.cited_evidence_ids else 'None'}",
                    f"- **Matched evidence IDs:** {', '.join(match.evidence_id for match in claim_result.matched_evidence) if claim_result.matched_evidence else 'None'}",
                    f"- **Human review required:** {'Yes' if claim_result.human_review_required else 'No'}",
                    f"- **Issues:** {'; '.join(claim_result.issues) if claim_result.issues else 'None'}",
                    f"- **Rationale:** {claim_result.rationale}",
                    "",
                ]
            )
        return "\n".join(sections).rstrip() + "\n"

    def save_json(self, report: VerificationReport, output_path: str | Path) -> Path:
        """Serialize the report to JSON and write it to disk."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = report.model_dump(mode="json")
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return path

    def save_csv(self, report: VerificationReport, output_path: str | Path) -> Path:
        """Export claim rows to CSV and write them to disk."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        self.claims_dataframe(report).to_csv(path, index=False, encoding="utf-8")
        return path

    def save_markdown(self, report: VerificationReport, output_path: str | Path) -> Path:
        """Write the full Markdown report to disk."""
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.full_markdown(report), encoding="utf-8")
        return path
